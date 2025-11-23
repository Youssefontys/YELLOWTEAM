# INITIAL RUN, RUN ONCE, SET UP AZURE FOR TERRAFORM STATE
import os
import subprocess
import time
import random
import sys

def run_az_cmd(command):
    """Voert een Azure CLI commando uit en vangt fouten af."""
    try:
        result = subprocess.run(
            command, 
            shell=True, 
            check=True, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            text=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Fout bij commando: {command}")
        print(f"Error message: {e.stderr}")
        sys.exit(1)

def ask_user(question, default_value=None):
    """Vraagt de gebruiker om input, met een optionele default."""
    if default_value:
        user_input = input(f"{question} [{default_value}]: ").strip()
        return user_input if user_input else default_value
    else:
        # Blijven vragen tot er iets is ingevuld
        while True:
            user_input = input(f"{question}: ").strip()
            if user_input:
                return user_input

print("--- 🐍 Azure Terraform State Bootstrap (Interactive) ---")
print("Dit script maakt de benodigde Azure resources aan voor je Terraform state.\n")

# --- STAP 1: Check Login & Subscription ---
print("🔍 Controleren van Azure login...")
try:
    current_sub = run_az_cmd("az account show --query name -o tsv")
    print(f"✅ Ingelogd op subscription: '{current_sub}'")
except:
    print("⚠️ Niet ingelogd. Browser wordt geopend...")
    run_az_cmd("az login -o none")
    current_sub = run_az_cmd("az account show --query name -o tsv")

# Vraag of we op deze subscription moeten blijven
change_sub = ask_user("Wil je van subscription wisselen? (j/n)", "n")
if change_sub.lower() == 'j':
    sub_id_input = ask_user("Voer het Subscription ID in waar je naartoe wilt")
    run_az_cmd(f"az account set --subscription {sub_id_input}")
    print(f"✅ Subscription gewijzigd.")

# --- STAP 2: User Input verzamelen ---
print("\n--- Configuratie ---")
rg_name   = ask_user("Naam voor Resource Group", "rg-terraform-state")
location  = ask_user("Locatie (regio)", "westeurope")
container = ask_user("Naam voor Blob Container", "tfstate")
prefix    = ask_user("Prefix voor Storage Account (moet uniek zijn, kleine letters)", "tfstate")

# Genereer unieke naam (Azure eis: kleine letters/cijfers, max 24 chars)
random_suffix = random.randint(1000, 9999)
storage_account_name = f"{prefix}{random_suffix}"
print(f"ℹ️  Gegenereerde Storage Account naam: {storage_account_name}")

confirm = ask_user("\nWil je doorgaan met aanmaken? (j/n)", "j")
if confirm.lower() != 'j':
    print("Geannuleerd.")
    sys.exit(0)

# --- STAP 3: Uitvoeren ---
print(f"\n🚀 Start uitrol in {location}...")

# 1. Resource Group
print(f"📦 Resource Group '{rg_name}' aanmaken/updaten...")
run_az_cmd(f"az group create --name {rg_name} --location {location} -o none")

# 2. Storage Account (Secure)
print(f"💾 Storage Account '{storage_account_name}' aanmaken...")
run_az_cmd(f"""
    az storage account create \
    --name {storage_account_name} \
    --resource-group {rg_name} \
    --location {location} \
    --sku Standard_LRS \
    --kind StorageV2 \
    --allow-blob-public-access false \
    --min-tls-version TLS1_2 \
    --https-only true \
    -o none
""")

# 3. Properties (Versioning)
print("🛡️ Beveiliging (Versioning & Soft Delete) instellen...")
run_az_cmd(f"""
    az storage account blob-service-properties update \
    --account-name {storage_account_name} \
    --resource-group {rg_name} \
    --enable-versioning true \
    --enable-delete-retention true \
    --delete-retention-days 7 \
    --enable-container-delete-retention true \
    --container-delete-retention-days 7 \
    -o none
""")

# 4. RBAC
print("🔑 Jouw account ophalen en 'Storage Blob Data Owner' toewijzen...")
current_user_id = run_az_cmd("az ad signed-in-user show --query id -o tsv")
sub_id = run_az_cmd("az account show --query id -o tsv")
scope = f"/subscriptions/{sub_id}/resourceGroups/{rg_name}/providers/Microsoft.Storage/storageAccounts/{storage_account_name}"

# We negeren errors hier als de rol al bestaat, maar voor veiligheid vangen we het ruim af
try:
    run_az_cmd(f"""
        az role assignment create \
        --role "Storage Blob Data Owner" \
        --assignee {current_user_id} \
        --scope {scope} \
        -o none
    """)
except:
    print("⚠️ Kon rol niet toewijzen (bestaat hij al?). We gaan door.")

# 5. Container
print(f"file_folder Container '{container}' aanmaken (wacht 15s op rechten)...")
time.sleep(15) # RBAC propagatie duurt soms even

run_az_cmd(f"""
    az storage container create \
    --name {container} \
    --account-name {storage_account_name} \
    --auth-mode login \
    -o none
""")

# --- STAP 4: Bestanden Genereren ---
print("\n📝 Bestanden genereren...")

# De  config aanmaken (backend.conf)
backend_conf_content = f"""resource_group_name  = "{rg_name}"
storage_account_name = "{storage_account_name}"
container_name       = "{container}"
key                  = "prod.terraform.tfstate"
use_azuread_auth     = true
"""

with open("backend.conf", "w") as f:
    f.write(backend_conf_content)
print(f"✅ 'backend.conf' is aangemaakt.")


# --- KLAAR ---
print("\n✅ --- SUCCESVOL AFGEROND ---")
print(f"Je backend is klaar voor gebruik in '{storage_account_name}'.")
print("Je kunt nu direct dit draaien:")
print("\n    terraform init -backend-config=backend.conf\n")
