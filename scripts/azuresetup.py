# --- AZURE TERRAFORM STATE BOOTSTRAP – 100% CMK-FIX (Officiële Syntax) ---
# Volgorde: UAMI → KV → Key → Storage met CMK + UAMI bij creatie | Zero secrets

import os, subprocess, time, random, sys, re

# ---------- Functies ----------
def get_concise_cmd_name(command):
    tokens = command.split()
    return " ".join(tokens[:3]) if tokens else "Leeg"

def run_az_cmd(command):
    name = get_concise_cmd_name(command)
    try:
        result = subprocess.run(command, shell=True, check=True,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"\n❌ FOUT bij {name}:\n{e.stderr.strip()}\n🛑 Stoppen.")
        sys.exit(1)

def run_az_cmd_with_retry(command, max_retries=6, delay=10):
    name = get_concise_cmd_name(command)
    for attempt in range(max_retries):
        try:
            print(f"{name} (poging {attempt+1})...")
            result = subprocess.run(command, shell=True, check=True,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            return result.stdout.strip(), True
        except subprocess.CalledProcessError as e:
            err = e.stderr.strip()
            if any(x in err for x in ["ResourceNotFound", "ConnectionAbortedError", "RequestDisallowedByPolicy"]) and attempt < max_retries-1:
                print(f" ⚠️ tijdelijke fout – wacht {delay}s...")
                time.sleep(delay); delay += 5
                continue
            elif any(x in err for x in ["RoleAssignmentExists", "already exists", "Subscription is not registered"]):
                return "ℹ️ bestaat al / registreren loopt (genegeerd).", True
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

# ---------- Start Bootstrap ----------
print("\n --- 🐍 Azure Terraform State Bootstrap ---\n")

# Login + Subscription
try:
    current_sub_name = run_az_cmd("az account show --query name -o tsv")
    active_sub_id = run_az_cmd("az account show --query id -o tsv")
    print(f"✅ Ingelogd op abonnement: {current_sub_name}")
except:
    print("⚠️ Niet ingelogd, open browser...")
    run_az_cmd("az login -o none")
    current_sub_name = run_az_cmd("az account show --query name -o tsv")
    active_sub_id = run_az_cmd("az account show --query id -o tsv")

if ask_user("Subscription wisselen? (j/n)", "n").lower() == 'j':
    sub_id_input = ask_user("Subscription ID:")
    run_az_cmd(f"az account set --subscription {sub_id_input}")
    active_sub_id = run_az_cmd("az account show --query id -o tsv")

current_object_id = run_az_cmd("az ad signed-in-user show --query id -o tsv")

# ---------- RESOURCE PROVIDERS ----------
print("\n⚙️ Controleren Resource Provider...")
run_az_cmd_with_retry("az provider register --namespace Microsoft.Storage --wait -o none")
run_az_cmd_with_retry("az provider register --namespace Microsoft.KeyVault --wait -o none")
run_az_cmd_with_retry("az provider register --namespace Microsoft.ManagedIdentity --wait -o none")
print("Alle providers klaar!\n")
time.sleep(10)

# ---------- User input ----------
rg_name   = ask_user("Resource Group naam", "rg-tfstate")
location  = ask_user("Regio", "westeurope")
container = ask_user("Blob container naam", "tfstate")

while True:
    prefix = ask_user("Storage Account prefix (3-20 lowercase)", "tfstate")
    storage_account_name = f"{prefix}{random.randint(10000,99999)}"
    if 3 <= len(storage_account_name) <= 24 and re.match("^[a-z0-9]+$", storage_account_name):
        break
    print("❌ Ongeldige naam – alleen kleine letters en cijfers, 3-24 tekens totaal.")

mi_name = ask_user("Managed Identity naam", "mi-tfstate")
kv_name = f"kvtfstate{random.randint(100000,999999)}{random.choice('abcdefghijklmnopqrstuvwxyz')}{random.choice('abcdefghijklmnopqrstuvwxyz')}"

if ask_user("\nDoorgaan? (j/n)", "j").lower() != 'j':
    sys.exit(0)

# ---------- Resources aanmaken (FIX: UAMI eerst + juiste CLI-syntax) ----------
print(f"\n🚀 Start uitrol in {location}...")

# 1. Resource Group
run_az_cmd(f"az group create --name {rg_name} --location {location} -o none")

# 2. UAMI eerst (prereq)
print(f"→ UAMI '{mi_name}' aanmaken...")
run_az_cmd_with_retry(f'az identity create --name {mi_name} --resource-group {rg_name} --location {location} -o none')

# 3. Propagation
print("🔐 Setup; Wachten op Entra ID propagation...")
mi_principal_id = ""
for attempt in range(12):
    try:
        mi_principal_id = run_az_cmd(f'az identity show --name {mi_name} --resource-group {rg_name} --query principalId -o tsv')
        if mi_principal_id:
            print(f"Principal ID gevonden: {mi_principal_id}")
            break
    except:
        pass
    print(f"   nog even geduld... (poging {attempt+1}/12)")
    time.sleep(25)
else:
    print("Timeout → check portal")
    sys.exit(1)

mi_client_id = run_az_cmd(f'az identity show --name {mi_name} --resource-group {rg_name} --query clientId -o tsv')
uami_resource_id = f"/subscriptions/{active_sub_id}/resourceGroups/{rg_name}/providers/Microsoft.ManagedIdentity/userAssignedIdentities/{mi_name}"

# 4. Key Vault
print(f"→ Key Vault '{kv_name}' aanmaken...")
run_az_cmd(f'az keyvault create --name {kv_name} --resource-group {rg_name} --location {location} \
            --enable-rbac-authorization true --enable-purge-protection true --retention-days 90 -o none')
time.sleep(20)

# 5. RBAC voor Key Vault (Crypto Officer + Service Encryption User)
kv_scope = f"/subscriptions/{active_sub_id}/resourceGroups/{rg_name}/providers/Microsoft.KeyVault/vaults/{kv_name}"
for assignee in [current_object_id, mi_principal_id]:
    run_az_cmd_with_retry(f'az role assignment create --role "Key Vault Crypto Officer" \
        --assignee {assignee} --scope {kv_scope} -o none')
    run_az_cmd_with_retry(f'az role assignment create --role "Key Vault Crypto Service Encryption User" \
        --assignee {assignee} --scope {kv_scope} -o none')

# 6. CMK
key_name = "tfstate-cmk"
print(f"→ CMK '{key_name}' aanmaken...")
run_az_cmd(f'az keyvault key create --vault-name {kv_name} --name {key_name} --kty RSA --size 2048 -o none')

# 7. Storage Account met CMK + UAMI bij creatie (FIXXED SYNTAX)
print(f"→ Storage Account '{storage_account_name}' met CMK + UAMI aanmaken...")
key_vault_uri = run_az_cmd(f'az keyvault show --name {kv_name} --query properties.vaultUri -o tsv').strip()

storage_create_cmd = f"""az storage account create \
    --name {storage_account_name} \
    --resource-group {rg_name} \
    --location {location} \
    --sku Standard_LRS \
    --kind StorageV2 \
    --allow-blob-public-access false \
    --min-tls-version TLS1_2 \
    --https-only true \
    --encryption-key-source Microsoft.Keyvault \
    --encryption-key-vault {key_vault_uri} \
    --encryption-key-name {key_name} \
    --encryption-services blob \
    --identity-type UserAssigned \
    --user-identity-id {uami_resource_id} \
    --key-vault-user-identity-id {uami_resource_id} \
    -o none"""

run_az_cmd(storage_create_cmd)
time.sleep(60)  # CMK-propagation

# 8. Blob hardening
run_az_cmd_with_retry(f"""az storage account blob-service-properties update \
--account-name {storage_account_name} --resource-group {rg_name} \
--enable-versioning true --enable-delete-retention true --delete-retention-days 7 \
--enable-container-delete-retention true --container-delete-retention-days 7 -o none""")

# 9. RBAC voor Storage
scope = f"/subscriptions/{active_sub_id}/resourceGroups/{rg_name}/providers/Microsoft.Storage/storageAccounts/{storage_account_name}"
for assignee in [current_object_id, mi_principal_id]:
    run_az_cmd_with_retry(f'az role assignment create --role "Storage Blob Data Owner" --assignee {assignee} --scope "{scope}" -o none')

# 10. Container
time.sleep(15)
run_az_cmd(f"az storage container create --name {container} --account-name {storage_account_name} --auth-mode login -o none")

print("45s wachten op propagations...")
time.sleep(45)

# ========== GITHUB SECRET ==========
if ask_user("\nMI Client ID als GitHub Secret? (j/n)", "j").lower() == 'j':
    repo = ask_user("GitHub repo (bijv. Youssef/project):")
    cmd = f'gh secret set AZURE_CLIENT_ID -b"{mi_client_id}" --repo {repo}'
    result = subprocess.run(cmd, shell=True)
    if result.returncode == 0:
        print(f"AZURE_CLIENT_ID gezet in {repo}!")
    else:
        print("gh CLI niet gevonden → kopieer handmatig:")
        print(f"   Secret: AZURE_CLIENT_ID\n   Waarde: {mi_client_id}")

# ========== SAMENVATTING ==========
print("\n🎉 SUCCESVOL: Backend klaar voor alle omgevingen!")
print(f"   RG          : {rg_name}")
print(f"   Storage     : {storage_account_name}")
print(f"   Container   : {container}")
print(f"   KV          : {kv_name}")
print(f"   CMK         : {key_name}")
print(f"   UAMI        : {mi_name}")
print(f"   Client ID   : {mi_client_id}")

# ========== backend.conf ==========
for env in ["dev", "test", "prod"]:
    with open(f"backend.{env}.conf", "w", encoding="utf-8") as f:
        f.write(f"""resource_group_name  = "{rg_name}"
storage_account_name = "{storage_account_name}"
container_name       = "{container}"
key                  = "{env}/terraform.tfstate"
use_azuread_auth     = true
""")
    print(f"✅ backend.{env}.conf aangemaakt")

print("\nGebruik bij Terraform init: terraform init -backend-config=backend.dev.conf (of test/prod)")
