# --- AZURE TERRAFORM STATE BOOTSTRAP ---
# Features:
# - User Assigned Managed Identity (UAMI)
# - Key Vault met Purge Protection
# - Customer Managed Keys (CMK) voor Storage Encryptie
# - GitHub Secrets integratie 
# - Volledige RBAC setup (Zero Trust)

import os
import subprocess
import time
import random
import sys
import re
import shutil

# ---------- Configuratie ----------
# Je kunt dit aanpassen of hardcoden als standaard
DEFAULT_LOCATION = "westeurope"
DEFAULT_RG_NAME = "rg-tfstate-mgmt"
RETRY_DELAY = 10
MAX_RETRIES = 10

# ---------- Functies ----------
def get_concise_cmd_name(command):
    """Geeft een korte naam terug voor log-doeleinden."""
    tokens = command.split()
    return " ".join(tokens[:3]) + "..." if tokens else "Leeg Commando"

def run_az_cmd(command, ignore_error=False):
    """Voert een Azure CLI commando uit en returnt de output."""
    try:
        result = subprocess.run(command, shell=True, check=True,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        if not ignore_error:
            cmd_name = get_concise_cmd_name(command)
            print(f"\n❌ FOUT bij {cmd_name}:\n{e.stderr.strip()}\n🛑 Stoppen.")
            sys.exit(1)
        return None

def run_az_cmd_with_retry(command, max_retries=MAX_RETRIES, delay=RETRY_DELAY):
    """Voert een commando uit met retry logica voor specifieke Azure fouten."""
    name = get_concise_cmd_name(command)
    
    # Lijst met errors die we kunnen retrien (Azure propagation issues)
    retryable_errors = [
        "ResourceNotFound", 
        "ConnectionAbortedError", 
        "RequestDisallowedByPolicy",
        "PrincipalNotFound", # Belangrijk: als de identiteit net is aangemaakt
        "AuthorizationFailed" # Soms duurt het even voor de rechten zijn toegekend
    ]
    
    # Lijst met errors die we negeren (omdat het resultaat al in lijn is)
    ignorable_errors = [
        "RoleAssignmentExists", 
        "already exists", 
        "Subscription is not registered"
    ]

    for attempt in range(max_retries):
        try:
            print(f"   ⏳ {name} (poging {attempt+1})...")
            result = subprocess.run(command, shell=True, check=True,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            return result.stdout.strip(), True
        except subprocess.CalledProcessError as e:
            err = e.stderr.strip()
            
            # Check of we het kunnen negeren
            if any(x in err for x in ignorable_errors):
                return f"ℹ️ Reeds gedaan/genegeerd.", True
            
            # Check of we moeten wachten en opnieuw proberen
            if any(x in err for x in retryable_errors) and attempt < max_retries-1:
                print(f"    ⚠️ Tijdelijke Azure fout. Wachten {delay}s...")
                time.sleep(delay)
                delay += 5 # Exponential backoff light
                continue
            
            # Echte fout
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
print("\n╔════════════════════════════════════════╗")
print("║   🛡️  Azure Terraform Secure Setup      ║")
print("╚════════════════════════════════════════╝\n")

# 1. Login Check & Account Info
try:
    print("🔍 Controleren Azure login...")
    current_sub_name = run_az_cmd("az account show --query name -o tsv")
    active_sub_id = run_az_cmd("az account show --query id -o tsv")
    print(f"✅ Ingelogd op: {current_sub_name} ({active_sub_id})")
except:
    print("⚠️ Niet ingelogd, browser wordt geopend...")
    run_az_cmd("az login -o none")
    current_sub_name = run_az_cmd("az account show --query name -o tsv")
    active_sub_id = run_az_cmd("az account show --query id -o tsv")

# Optioneel wisselen
if ask_user("Wil je van subscription wisselen? (j/n)", "n").lower() == 'j':
    sub_id_input = ask_user("Nieuw Subscription ID:")
    run_az_cmd(f"az account set --subscription {sub_id_input}")
    active_sub_id = run_az_cmd("az account show --query id -o tsv")
    print(f"✅ Gewisseld naar ID: {active_sub_id}")

# Haal eigen Object ID op (nodig voor Key Vault access)
current_object_id = run_az_cmd("az ad signed-in-user show --query id -o tsv")

# 2. Providers Registreren
print("\n⚙️  Providers controleren (Storage, KeyVault, Identity)...")
providers = ["Microsoft.Storage", "Microsoft.KeyVault", "Microsoft.ManagedIdentity"]
for p in providers:
    run_az_cmd_with_retry(f"az provider register --namespace {p} --wait -o none", max_retries=2, delay=2)
print("✅ Providers gereed.\n")

# 3. User Input & Naming
rg_name   = ask_user("Resource Group naam", DEFAULT_RG_NAME)
location  = ask_user("Regio", DEFAULT_LOCATION)
container = ask_user("Blob container naam", "tfstate")

# Unieke namen genereren
while True:
    prefix = ask_user("Storage prefix (3-10 chars, lowercase)", "tfstate")
    storage_account_name = f"{prefix}{random.randint(1000,9999)}" # Korter is veiliger voor 24 char limiet
    if 3 <= len(storage_account_name) <= 24 and re.match("^[a-z0-9]+$", storage_account_name):
        break
    print("❌ Naam te lang of ongeldige tekens.")

suffix_random = f"{random.randint(1000,9999)}"
mi_name = f"mi-{prefix}-{suffix_random}"
kv_name = f"kv-{prefix}-{suffix_random}" # Keyvaults moeten ook globaal uniek zijn vaak
key_name = "tfstate-cmk"

print(f"\n📋 PLAN VAN AANPAK:")
print(f"   📍 Regio:    {location}")
print(f"   📦 RG:       {rg_name}")
print(f"   👤 UAMI:     {mi_name}")
print(f"   🔑 KeyVault: {kv_name}")
print(f"   💾 Storage:  {storage_account_name} (CMK Encrypted)")

if ask_user("\nStarten met uitrol? (j/n)", "j").lower() != 'j':
    print("Geannuleerd.")
    sys.exit(0)

# ---------- UITROL START ----------
print(f"\n🚀 Start uitrol...")

# A. Resource Group
run_az_cmd(f"az group create --name {rg_name} --location {location} -o none")

# B. Managed Identity (CRITICAL STEP 1)
print(f"→ Managed Identity '{mi_name}' aanmaken...")
run_az_cmd_with_retry(f'az identity create --name {mi_name} --resource-group {rg_name} --location {location} -o none')

# Identity props ophalen (met retry loop voor propagation)
print("   ⏳ Wachten op ID propagation...")
mi_principal_id = ""
for _ in range(12):
    try:
        mi_principal_id = run_az_cmd(f'az identity show --name {mi_name} --resource-group {rg_name} --query principalId -o tsv')
        if mi_principal_id: break
    except: pass
    time.sleep(5)
mi_client_id = run_az_cmd(f'az identity show --name {mi_name} --resource-group {rg_name} --query clientId -o tsv')
uami_resource_id = f"/subscriptions/{active_sub_id}/resourceGroups/{rg_name}/providers/Microsoft.ManagedIdentity/userAssignedIdentities/{mi_name}"

# C. Key Vault (CRITICAL STEP 2)
# Let op: purge-protection betekent dat je hem niet hard kan deleten voor X dagen.
print(f"→ Key Vault '{kv_name}' aanmaken...")
run_az_cmd(f'az keyvault create --name {kv_name} --resource-group {rg_name} --location {location} \
            --enable-rbac-authorization true --enable-purge-protection true --retention-days 90 -o none')

# D. RBAC op Key Vault (Voor JOU en voor de UAMI)
# Jij moet keys kunnen maken (Crypto Officer)
# UAMI moet keys kunnen gebruiken (Crypto Service Encryption User)
print("→ Key Vault RBAC toewijzen...")
kv_scope = f"/subscriptions/{active_sub_id}/resourceGroups/{rg_name}/providers/Microsoft.KeyVault/vaults/{kv_name}"

assignments = [
    (current_object_id, "Key Vault Crypto Officer"),           # Jij (om de key te maken)
    (mi_principal_id, "Key Vault Crypto Service Encryption User"), # UAMI (om de key te lezen)
    (mi_principal_id, "Key Vault Crypto Officer")              # UAMI (veiligheidshalve, soms nodig voor wrap/unwrap)
]

for assignee, role in assignments:
    run_az_cmd_with_retry(f'az role assignment create --role "{role}" --assignee {assignee} --scope {kv_scope} -o none')

# E. CMK Key Aanmaken
print(f"→ CMK '{key_name}' genereren...")
# Check of huidige user al rechten heeft (propagation kan even duren)
time.sleep(15) 
run_az_cmd_with_retry(f'az keyvault key create --vault-name {kv_name} --name {key_name} --kty RSA --size 2048 -o none')

# F. Storage Account met CMK (CRITICAL STEP 3 - De koppeling)
print(f"→ Storage Account '{storage_account_name}' aanmaken met CMK...")
key_vault_uri = run_az_cmd(f'az keyvault show --name {kv_name} --query properties.vaultUri -o tsv').strip()

# Dit commando koppelt alles in één keer bij creatie
storage_cmd = f"""az storage account create \
    --name {storage_account_name} \
    --resource-group {rg_name} \
    --location {location} \
    --sku Standard_LRS \
    --kind StorageV2 \
    --allow-blob-public-access false \
    --min-tls-version TLS1_2 \
    --https-only true \
    --identity-type UserAssigned \
    --user-identity-id {uami_resource_id} \
    --encryption-key-source Microsoft.Keyvault \
    --encryption-key-vault {key_vault_uri} \
    --encryption-key-name {key_name} \
    --key-vault-user-identity-id {uami_resource_id} \
    -o none"""

run_az_cmd_with_retry(storage_cmd)

# G. Storage Hardening & Container
print("→ Storage hardening & Container...")
run_az_cmd_with_retry(f"""az storage account blob-service-properties update \
    --account-name {storage_account_name} --resource-group {rg_name} \
    --enable-versioning true --enable-delete-retention true --delete-retention-days 7 \
    --enable-container-delete-retention true --container-delete-retention-days 7 -o none""")

# Rol voor JOU en UAMI op storage (zodat Terraform erbij kan)
storage_scope = f"/subscriptions/{active_sub_id}/resourceGroups/{rg_name}/providers/Microsoft.Storage/storageAccounts/{storage_account_name}"
for assignee in [current_object_id, mi_principal_id]:
    run_az_cmd_with_retry(f'az role assignment create --role "Storage Blob Data Owner" --assignee {assignee} --scope "{storage_scope}" -o none')

# Container aanmaken
time.sleep(10) # Even wachten op RBAC
run_az_cmd_with_retry(f"az storage container create --name {container} --account-name {storage_account_name} --auth-mode login -o none")

# ---------- GITHUB SECRETS (Optioneel) ----------
print("\n🐱 GitHub Integration")
if shutil.which('gh') and ask_user("GitHub Secrets instellen? (j/n)", "n").lower() == 'j':
    repo = ask_user("GitHub repo (bijv. user/repo)")
    print(f"   Setting secrets in {repo}...")
    
    secrets = {
        "AZURE_CLIENT_ID": mi_client_id,
        "AZURE_SUBSCRIPTION_ID": active_sub_id,
        "AZURE_TENANT_ID": run_az_cmd("az account show --query tenantId -o tsv"),
        "BACKEND_RG_NAME": rg_name,
        "BACKEND_STORAGE_ACCOUNT": storage_account_name,
        "BACKEND_CONTAINER_NAME": container
    }
    
    for key, value in secrets.items():
        subprocess.run(f'gh secret set {key} -b"{value}" --repo {repo}', shell=True)
    print("✅ Secrets gezet!")
elif not shutil.which('gh'):
    print("⚠️  'gh' CLI tool niet gevonden. Sla dit over.")
    print(f"ℹ️  Handmatig instellen: AZURE_CLIENT_ID = {mi_client_id}")

# ---------- CONFIG FILES ----------
print("\n📝 Config bestanden genereren...")
for env in ["dev", "test", "prod"]:
    with open(f"backend.{env}.conf", "w", encoding="utf-8") as f:
        f.write(f"""resource_group_name  = "{rg_name}"
storage_account_name = "{storage_account_name}"
container_name       = "{container}"
key                  = "{env}/terraform.tfstate"
use_azuread_auth     = true
""")

print("\n🎉 BOOTSTRAP SUCCESVOL VOLTOOID!")
print(f"Gebruik: terraform init -backend-config=backend.dev.conf (of test/prod)")

