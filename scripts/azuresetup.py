# --- AZURE TERRAFORM STATE BOOTSTRAP (SECURE & ROBUST) ---
import os, subprocess, time, random, sys, re

# ---------- Functies ----------
def get_concise_cmd_name(command):
    tokens = command.split()
    return " ".join(tokens[:3]) if tokens else "Leeg commando"

def run_az_cmd(command):
    name = get_concise_cmd_name(command)
    print(f"-> Uitvoeren: {name}...")
    try:
        result = subprocess.run(command, shell=True, check=True,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"\n❌ FOUT bij {name}:\n{e.stderr.strip()}\n🛑 Stoppen.")
        sys.exit(1)

def run_az_cmd_with_retry(command, max_retries=5, delay=10):
    name = get_concise_cmd_name(command)
    for attempt in range(max_retries):
        try:
            print(f"-> Uitvoeren: {name} (poging {attempt+1})...")
            result = subprocess.run(command, shell=True, check=True,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            return result.stdout.strip(), True
        except subprocess.CalledProcessError as e:
            err = e.stderr.strip()
            if ("ResourceNotFound" in err or "ConnectionAbortedError" in err) and attempt < max_retries-1:
                print(f"⚠️ {name} faalde ({err}). Wachten {delay}s en opnieuw proberen...")
                time.sleep(delay); delay += 5
                continue
            elif "RoleAssignmentExists" in err:
                return "ℹ️ RBAC rol bestaat al (genegeerd).", True
            else:
                print(f"❌ FATALE FOUT bij {name}:\n{err}\n🛑 Stoppen.")
                sys.exit(1)
    return "", False

def ask_user(question, default=None):
    prompt = f"{question} [{default}]: " if default else f"{question}: "
    while True:
        ans = input(prompt).strip()
        if ans: return ans
        if default: return default

def validate_sa_name(name):
    if not 3 <= len(name) <= 24: return False, "3-24 karakters lang"
    if not re.match("^[a-z0-9]+$", name): return False, "alleen kleine letters/cijfers"
    return True, ""

# ---------- Start Bootstrap ----------
print("--- 🐍 Azure Terraform State Bootstrap ---")

# Login + Subscription
try:
    current_sub_name = run_az_cmd("az account show --query name -o tsv")
    active_sub_id = run_az_cmd("az account show --query id -o tsv")
    run_az_cmd(f"az account set --subscription {active_sub_id}")
    try: current_user_id = run_az_cmd("az ad signed-in-user show --query id -o tsv")
    except: current_user_id = ask_user("Azure UPN voor RBAC", "")
    print(f"✅ Ingelogd op {current_sub_name}")
except:
    print("⚠️ Niet ingelogd, open browser...")
    run_az_cmd("az login -o none")
    current_sub_name = run_az_cmd("az account show --query name -o tsv")
    active_sub_id = run_az_cmd("az account show --query id -o tsv")
    run_az_cmd(f"az account set --subscription {active_sub_id}")
    current_user_id = run_az_cmd("az ad signed-in-user show --query id -o tsv")

if ask_user("Wil je van subscription wisselen? (j/n)", "n").lower() == 'j':
    sub_id_input = ask_user("Subscription ID: ")
    run_az_cmd(f"az account set --subscription {sub_id_input}")

# Provider registreren
print("⚙️ Controleren Resource Provider Microsoft.Storage...")
run_az_cmd("az provider register --namespace Microsoft.Storage --wait -o none")

# ---------- User input ----------
rg_name   = ask_user("Resource Group naam", "rg-terraform-state")
location  = ask_user("Regio", "westeurope")
container = ask_user("Blob container naam", "tfstate")
while True:
    prefix = ask_user("Storage Account prefix (3-20 letters)", "tfstate")
    storage_account_name = f"{prefix}{random.randint(10000,99999)}"
    valid, reason = validate_sa_name(storage_account_name)
    if valid: break
    print(f"❌ Ongeldige naam: {reason}")

if ask_user("Doorgaan met aanmaken? (j/n)", "j").lower() != 'j': sys.exit(0)

# ---------- Resources aanmaken ----------
print(f"\n🚀 Start uitrol in {location}...")

# 1. Resource Group
run_az_cmd(f"az group create --name {rg_name} --location {location} -o none")

# 2. Storage Account
run_az_cmd(f"""az storage account create --name {storage_account_name} --resource-group {rg_name} \
--location {location} --sku Standard_LRS --kind StorageV2 --allow-blob-public-access false \
--min-tls-version TLS1_2 --https-only true -o none""")
time.sleep(60) # ARM propagation

# 3. Storage Properties: versioning + soft delete
command_storage_props = f"""
az storage account blob-service-properties update \
--account-name {storage_account_name} \
--resource-group {rg_name} \
--enable-versioning true \
--enable-delete-retention true \
--delete-retention-days 7 \
--enable-container-delete-retention true \
--container-delete-retention-days 7 \
-o none
"""
run_az_cmd_with_retry(command_storage_props)

# 4. Role Assignment
role_name = "Storage Blob Data Owner"
scope = f"/subscriptions/{active_sub_id}/resourceGroups/{rg_name}/providers/Microsoft.Storage/storageAccounts/{storage_account_name}"
command_rbac = f'az role assignment create --role "{role_name}" --assignee "{current_user_id}" --scope "{scope}" -o none'
run_az_cmd_with_retry(command_rbac)

# 5. Container aanmaken
time.sleep(15) # RBAC propagation
run_az_cmd(f"az storage container create --name {container} --account-name {storage_account_name} --auth-mode login -o none")

# 6. Backend conf genereren
backend_conf_content = f"""resource_group_name  = "{rg_name}"
storage_account_name = "{storage_account_name}"
container_name       = "{container}"
key                  = "prod.terraform.tfstate"
use_azuread_auth     = true
"""
with open("backend.conf", "w") as f: f.write(backend_conf_content)

print("\n✅ SUCCESVOL: Backend klaar voor gebruik!")
print("Run nu: terraform init -backend-config=backend.conf")

//
