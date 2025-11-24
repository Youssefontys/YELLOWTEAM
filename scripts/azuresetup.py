# --- INITIAL RUN, RUN ONCE, SET UP AZURE FOR TERRAFORM STATE ---
import os
import subprocess
import time
import random
import sys
import re

# Functie om de eerste paar tokens van het commando te krijgen voor betere logging
def get_concise_cmd_name(command):
    """Haalt de eerste 3 tokens op voor duidelijke log-uitvoer."""
    tokens = command.split()
    if not tokens:
        return "Leeg commando"
    # Toon de eerste 3 tokens (e.g., 'az group create')
    return " ".join(tokens[:3])

# Functie om Azure CLI commando's uit te voeren en fouten af te handelen
def run_az_cmd(command):
    """Voert een Azure CLI commando uit en vangt fouten af, stopt bij fout."""
    command_name = get_concise_cmd_name(command)
    print(f"-> Uitvoeren: {command_name}...")
    try:
        result = subprocess.run(
            command, 
            shell=True, 
            check=True, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            text=True # Zorgt ervoor dat stdout/stderr strings zijn, niet bytes
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        # Dit is de generieke foutafhandeling voor commando's die moeten slagen
        print(f"\n❌ FOUT: Het commando hierboven is mislukt.")
        print(f"❌ Error code: {e.returncode}")
        print(f"❌ Foutmelding van Azure CLI: \n{e.stderr.strip()}")
        print("\n🛑 De uitvoering wordt gestopt. Controleer de foutmelding.")
        sys.exit(1)


# Functie om Azure CLI commando's uit te voeren met retry op ResourceNotFound en ConnectionErrors
def run_az_cmd_with_retry(command, max_retries=5, delay=10): # AANTAL RETRIES VERHOOGD NAAR 5
    """Voert een Azure CLI commando uit met retries op ResourceNotFound en netwerkfouten."""
    command_name = get_concise_cmd_name(command)
    
    for attempt in range(max_retries):
        try:
            print(f"-> Uitvoeren: {command_name}...")
            # We voeren dit commando handmatig uit om de stderr te kunnen inspecteren
            result = subprocess.run(
                command,
                shell=True,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            return result.stdout.strip(), True # Succes
        
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.strip()
            
            # Check op de specifieke ResourceNotFound fout (ARM Timing)
            if "ResourceNotFound" in error_msg and attempt < max_retries - 1:
                print(f"⚠️ {command_name} is mislukt met ResourceNotFound. Wachten {delay}s en opnieuw proberen...")
                time.sleep(delay)
                delay += 5 # Maak de volgende wachtperiode langer
                continue

            # NIEUWE CHECK: Check op Client-Side Connectie fouten (b.v. WinError 10053)
            elif "ConnectionAbortedError" in error_msg and attempt < max_retries - 1:
                print(f"⚠️ {command_name} mislukt door Client-Netwerkfout (10053). Wachten {delay}s en opnieuw proberen...")
                time.sleep(delay)
                delay += 5
                continue
            
            # Check op RoleAssignmentExists fout (deze mag genegeerd worden)
            elif "RoleAssignmentExists" in error_msg:
                return "ℹ️  RBAC rol bestaat al (genegeerd).", True
            
            # Alle andere fouten zijn fatal
            else:
                print(f"\n❌ FOUT: Het commando hierboven is mislukt na {attempt+1} pogingen.")
                print(f"❌ Foutmelding van Azure CLI: \n{error_msg}")
                print("\n🛑 De uitvoering wordt gestopt.")
                sys.exit(1)
    
    return "", False # Mocht het onverhoopt toch mislukken

# Functie om gebruikersinput te vragen
def ask_user(question, default_value=None):
    """Vraagt de gebruiker om input, met een optionele default."""
    if default_value:
        user_input = input(f"{question} [{default_value}]: ").strip()
        return user_input if user_input else default_value
    else:
        while True:
            user_input = input(f"{question}: ").strip()
            if user_input:
                return user_input

# Functie om Storage Account naam te valideren
def validate_sa_name(name):
    """Controleert of de naam voldoet aan Azure Storage Account eisen."""
    if not 3 <= len(name) <= 24:
        return False, "Naam moet tussen de 3 en 24 karakters lang zijn."
    if not re.match("^[a-z0-9]+$", name):
        return False, "Naam mag alleen kleine letters en cijfers bevatten."
    return True, ""

print("--- 🐍 Azure Terraform State Bootstrap (Interactive) ---")
print("Dit script maakt de benodigde Azure resources aan voor je Terraform state.\n")

# --- STAP 1: Check Login & Subscription ---
print("🔍 Controleren van Azure login...")
try:
    # Haal de Subscription ID en Naam op.
    current_sub_name = run_az_cmd("az account show --query name -o tsv")
    active_sub_id = run_az_cmd("az account show --query id -o tsv") 
    
    # Zet de actieve context expliciet naar de ID van de succesvol ingelogde subscription.
    run_az_cmd(f"az account set --subscription {active_sub_id}")
    
    print(f"✅ Ingelogd op subscription: '{current_sub_name}' (ID: {active_sub_id})")
    # Probeer de user ID op te halen, dit commando faalt vaak als rechten ontbreken
    try:
        current_user_id = run_az_cmd("az ad signed-in-user show --query id -o tsv")
    except subprocess.CalledProcessError:
        print("⚠️ WAARSCHUWING: Kan uw Azure AD user ID niet ophalen. Gebruik uw emailadres als fallback voor RBAC.")
        current_user_id = ask_user("Voer uw Azure emailadres (UPN) in voor RBAC toewijzing")
        
except subprocess.CalledProcessError:
    # Dit gebeurt alleen als de initiele logincheck mislukt, we proberen in te loggen
    print("⚠️ Niet ingelogd. Browser wordt geopend voor 'az login'...")
    try:
        run_az_cmd("az login -o none")
        current_sub_name = run_az_cmd("az account show --query name -o tsv")
        active_sub_id = run_az_cmd("az account show --query id -o tsv") # NIEUW: Haal ID op
        run_az_cmd(f"az account set --subscription {active_sub_id}") # FIX: Zet actieve context
        current_user_id = run_az_cmd("az ad signed-in-user show --query id -o tsv")
        print(f"✅ Succesvol ingelogd op: '{current_sub_name}' (ID: {active_sub_id})")
    except:
        print("\n❌ FATALE FOUT: Inloggen bij Azure is mislukt. Controleer je credentials.")
        sys.exit(1)


# Vraag of we op deze subscription moeten blijven
change_sub = ask_user("Wil je van subscription wisselen? (j/n)", "n")
if change_sub.lower() == 'j':
    sub_id_input = ask_user("Voer het Subscription ID in waar je naartoe wilt")
    run_az_cmd(f"az account set --subscription {sub_id_input}")
    print("✅ Subscription gewijzigd.")


# --- STAP 1.5: Registreer Resource Providers (NIEUWE STAP) ---
# Dit lost vaak de SubscriptionNotFound/ResourceNotFound fouten op.
PROVIDER_NAME = "Microsoft.Storage"
print(f"\n⚙️ Controleren en registreren van Resource Provider '{PROVIDER_NAME}'...")
run_az_cmd(f"az provider register --namespace {PROVIDER_NAME} --wait -o none")
print(f"✅ Resource Provider '{PROVIDER_NAME}' is nu geregistreerd.")


# --- STAP 2: User Input verzamelen ---
print("\n--- Configuratie ---")
rg_name   = ask_user("Naam voor Resource Group", "rg-terraform-state")
location  = ask_user("Locatie (regio)", "westeurope")
container = ask_user("Naam voor Blob Container", "tfstate")

# Naming loop met validatie
while True:
    prefix = ask_user("Prefix voor Storage Account (kleine letters, 3-20 karakters)", "tfstate")
    # Gebruik een groter random bereik om unieke namen te garanderen, wat Azure vereist
    random_suffix = random.randint(10000, 99999) # 5 cijfers
    storage_account_name = f"{prefix}{random_suffix}"
    
    is_valid, reason = validate_sa_name(storage_account_name)
    
    if is_valid:
        print(f"ℹ️  Gegenereerde Storage Account naam: {storage_account_name}")
        break
    else:
        print(f"❌ FOUT: De naam '{storage_account_name}' is ongeldig. {reason}. Probeer opnieuw.")

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
# Op verzoek van de gebruiker naar een enkele regel gezet. Beveiligingsvlaggen zijn behouden.
run_az_cmd(f"az storage account create --name {storage_account_name} --resource-group {rg_name} --location {location} --sku Standard_LRS --kind StorageV2 --allow-blob-public-access false --min-tls-version TLS1_2 --https-only true -o none")

# Nieuwe, kritieke wachttijd ingevoegd om ARM de tijd te geven
print("⏳ Wachten 60 seconden totdat Storage Account volledig beschikbaar is in ARM...")
time.sleep(60) # VERANDERD: 30 seconden naar 60 seconden
print("✅ Wachttijd voltooid.")


# 3. Properties (Versioning) - Gebruik retry voor ARM-propagatie
print("🛡️ Beveiliging (Versioning & Soft Delete) instellen (met retry)...")
command_versioning = f"""
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
output, success = run_az_cmd_with_retry(command_versioning)
if not success:
    print("🛑 FATALE FOUT bij instellen beveiligingsproperties. Stoppen.")
    sys.exit(1)
print("✅ Beveiligingseigenschappen ingesteld.")


# 4. RBAC - Gebruik retry voor ARM-propagatie
print("🔑 Jouw account ('Storage Blob Data Owner') toewijzen (met retry)...")
sub_id = run_az_cmd("az account show --query id -o tsv")
scope = f"/subscriptions/{sub_id}/resourceGroups/{rg_name}/providers/Microsoft.Storage/storageAccounts/{storage_account_name}"

command_rbac = f"""az role assignment create \
    --role "Storage Blob Data Owner" \
    --assignee "{current_user_id}" \
    --scope {scope} \
    -o none"""

output, success = run_az_cmd_with_retry(command_rbac)

if not success and "RBAC rol bestaat al" not in output:
    print("⚠️ WAARSCHUWING: Roltoewijzing is mislukt.")
    print("\nLET OP: Dit duidt vaak op onvoldoende rechten ('User Access Administrator') op de Resource Group.")
else:
    # Print succesmelding als het gelukt is of de rol al bestond
    print(output.replace('ℹ️', '✅').replace('WARNING', '✅') or "✅ RBAC rol succesvol toegewezen.")


# 5. Container
# De wachttijd voor RBAC propagatie is hier nog steeds belangrijk (meestal 15 seconden)
print(f"file_folder Container '{container}' aanmaken (wacht 15s op rechten)...")
time.sleep(15) 

run_az_cmd(f"""
    az storage container create \
    --name {container} \
    --account-name {storage_account_name} \
    --auth-mode login \
    -o none
""")

# --- STAP 4: Bestanden Genereren ---
print("\n📝 Bestanden genereren...")

# De config aanmaken (backend.conf)
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
print("\n    terraform init -backend-config='backend.conf'\n")