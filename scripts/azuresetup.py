# =====================================================
# Azure Terraform State Bootstrap (FINAL Version)
# Automatisch:
# - Resource Group
# - Storage Account (secure settings)
# - Blob container
# - RBAC
# - backend.conf genereren
# =====================================================

import os, subprocess, time, random, sys, re

# ------------------- HELPER FUNCTIES -------------------

def concise(command):
    tokens = command.split()
    return " ".join(tokens[:3]) if tokens else "cmd"

def run(command):
    name = concise(command)
    print(f"-> {name}...")
    try:
        result = subprocess.run(
            command, shell=True, check=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"\n❌ FOUT bij {name}:\n{e.stderr.strip()}\n🛑 Stoppen.")
        sys.exit(1)

def run_retry(command, retries=5, delay=10):
    name = concise(command)
    for i in range(retries):
        try:
            print(f"-> {name} (poging {i+1})...")
            result = subprocess.run(
                command, shell=True, check=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            err = e.stderr.strip()
            # Retry scenarios
            if ("ResourceNotFound" in err or "ConnectionAbortedError" in err) and i < retries-1:
                print(f"⚠️ {name} faalde ({err}). Wachten {delay}s…")
                time.sleep(delay)
                delay += 5
                continue
            if "RoleAssignmentExists" in err:
                print("ℹ️ RBAC bestaat al, ga door...")
                return
            print(f"\n❌ Fatale fout:\n{err}\n🛑 Stoppen.")
            sys.exit(1)

def ask(question, default=None):
    prompt = f"{question} [{default}]: " if default else f"{question}: "
    while True:
        ans = input(prompt).strip()
        if ans: return ans
        if default: return default

def validate_sa(name):
    if not 3 <= len(name) <= 24: return False, "3-24 chars"
    if not re.match("^[a-z0-9]+$", name): return False, "alleen lowercase/cijfers"
    return True, ""

# ------------------- START -------------------

print("\n=== 🐍 Azure Terraform State Bootstrap ===")

# Login check
try:
    sub_name = run("az account show --query name -o tsv")
    sub_id   = run("az account show --query id -o tsv")
    run(f"az account set --subscription {sub_id}")
    try:
        user_id = run("az ad signed-in-user show --query id -o tsv")
    except:
        user_id = ask("Azure UPN (RBAC)", "")
except:
    print("⚠️ Niet ingelogd. Open nu browser…")
    run("az login -o none")
    sub_name = run("az account show --query name -o tsv")
    sub_id   = run("az account show --query id -o tsv")
    user_id  = run("az ad signed-in-user show --query id -o tsv")

print(f"✅ Ingelogd op subscription: {sub_name}")

# Provider check
print("⚙️ Provider Microsoft.Storage registreren…")
run("az provider register --namespace Microsoft.Storage --wait -o none")

# ------------------- INPUT -------------------

rg_name   = ask("Resource Group naam", "rg-terraform-state")
location  = ask("Regio", "westeurope")
container = ask("Blob container naam", "tfstate")

while True:
    prefix = ask("Storage Account prefix (3-20 lowercase)", "tfstate")
    sa_name = f"{prefix}{random.randint(10000,99999)}"
    ok, reason = validate_sa(sa_name)
    if ok: break
    print(f"❌ Ongeldige naam: {reason}")

if ask("Doorgaan met aanmaken? (j/n)", "j").lower() != "j":
    sys.exit(0)

# ------------------- AANMAKEN -------------------

print(f"\n🚀 Uitrollen in {location}…")

# 1. Resource group
run(f"az group create --name {rg_name} --location {location} -o none")

# 2. Storage Account
run(f"""
az storage account create
    --name {sa_name}
    --resource-group {rg_name}
    --location {location}
    --sku Standard_LRS
    --kind StorageV2
    --allow-blob-public-access false
    --min-tls-version TLS1_2
    --https-only true
    -o none
""")

print("⏳ Wachten 45s voor ARM propagation…")
time.sleep(45)

# 3. Storage security settings
run_retry(f"""
az storage account blob-service-properties update
    --account-name {sa_name}
    --resource-group {rg_name}
    --enable-versioning true
    --enable-delete-retention true
    --delete-retention-days 7
    --enable-container-delete-retention true
    --container-delete-retention-days 7
    -o none
""")

# 4. RBAC
scope = f"/subscriptions/{sub_id}/resourceGroups/{rg_name}/providers/Microsoft.Storage/storageAccounts/{sa_name}"

run_retry(
    f'az role assignment create --role "Storage Blob Data Owner" '
    f'--assignee "{user_id}" --scope "{scope}" -o none'
)

print("⏳ RBAC propagatie 10s…")
time.sleep(10)

# 5. Container
run(f"az storage container create --name {container} --account-name {sa_name} --auth-mode login -o none")

# ------------------- BACKEND CONFIG -------------------

backend_conf = f"""
resource_group_name  = "{rg_name}"
storage_account_name = "{sa_name}"
container_name       = "{container}"
key                  = "prod.terraform.tfstate"
use_azuread_auth     = true
""".strip()

with open("backend.conf", "w") as f:
    f.write(backend_conf)

print("\n🎉 SUCCES! Terraform backend klaar.")
print("➡️ Run nu: terraform init -backend-config=backend.conf")
