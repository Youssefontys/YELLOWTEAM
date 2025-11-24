# INITIAL RUN, ONLY FOR DEVELOPER FOR SETTING UP PROJECT
import os
import sys

def create_project_structure():
    # 1. Determine the Project Root
    # Because this script is inside 'scripts/', we need to go one level up.
    script_location = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_location)

    print(f"📍 Script location: {script_location}")
    print(f"📂 Project Root detected: {project_root}\n")

    # 2. Define directory structure (Relative to Project Root)
    directories = [
        os.path.join(".github", "workflows"),
        "app",
        "terraform"
    ]

    # 3. Define files and content
    files = {
        os.path.join("app", "app.py"): 
            "# (Placeholder)\n"
            "print('Hello World from Azure App Service')\n",

        os.path.join("terraform", "main.tf"): 
            "# Infrastructure (IaC)\n"
            "# Define your resources here (App Service, Front Door)\n",

        os.path.join("terraform", "variables.tf"): 
            "# Variables (e.g., locations, naming conventions)\n",

        os.path.join("terraform", "providers.tf"): 
            "# Azure Connection Configuration\n"
            "terraform {\n"
            "  required_providers {\n"
            "    azurerm = {\n"
            "      source  = \"hashicorp/azurerm\"\n"
            "      version = \"~> 3.0\"\n"
            "    }\n"
            "  }\n"
            "}\n\n"
            "provider \"azurerm\" {\n"
            "  features {}\n"
            "}\n",

        os.path.join("terraform", "backend.tf"): 
            "# State File Configuration (IMPORTANT)\n"
            "# Configure where the .tfstate is stored (e.g., Azure Storage Account)\n",

        ".gitignore": 
            "# Terraform specific\n"
            ".terraform/\n"
            "*.tfstate\n"
            "*.tfstate.backup\n"
            "*.tfvars\n"
            ".env\n"
            "\n"
            "# Python specific\n"
            "__pycache__/\n"
            "*.py[cod]\n"
            "venv/\n"
    }

    print("🚀 Starting project setup from subdirectory...")

    # Create Directories
    for relative_dir in directories:
        # Combine project_root with the relative directory
        full_path = os.path.join(project_root, relative_dir)
        try:
            os.makedirs(full_path, exist_ok=True)
            print(f"✅ Directory checked/created: {relative_dir}")
        except OSError as e:
            print(f"❌ Error creating directory {relative_dir}: {e}")

    # Create Files
    for relative_path, content in files.items():
        # Combine project_root with the relative file path
        full_path = os.path.join(project_root, relative_path)
        try:
            if os.path.exists(full_path):
                print(f"⚠️  Skipped: {relative_path} (File already exists)")
            else:
                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(content)
                print(f"✅ File created: {relative_path}")
        except OSError as e:
            print(f"❌ Error writing file {relative_path}: {e}")

    print("\n🎉 Done! Project setup complete.")
    print(f"Files have been created in: {project_root}")

if __name__ == "__main__":
    create_project_structure()


    #Zorg dat .gitignore goed word aangemaakt, + remove backend.tf from creation, word via azuresetup gefixt. 
    ///
    # --- PROJECT STRUCTURE SETUP ---
import os

def create_project_structure():
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    print(f"📂 Project Root: {project_root}")

    directories = [
        ".github/workflows",
        "app",
        "terraform"
    ]

    # Terraform segmented files
    terraform_files = {
        "main.tf": "# main entrypoint, call modules here\n",
        "variables.tf": "# Terraform variables\n",
        "providers.tf": (
            "terraform {\n"
            "  required_providers {\n"
            "    azurerm = { source = \"hashicorp/azurerm\" version = \"~> 4.0\" }\n"
            "  }\n"
            "}\n\n"
            "provider \"azurerm\" {\n"
            "  features {}\n"
            "}\n"
        ),
        "network.tf": "# Network resources (VNet, NSG, Subnets)\n",
        "appservice.tf": "# App Service resources\n",
        "logging.tf": "# Log Analytics, Monitoring\n",
        "security.tf": "# WAF, NSG, Storage security settings\n"
    }

    files = {
        **{os.path.join("terraform", k): v for k,v in terraform_files.items()},
        os.path.join("app", "app.py"): "print('Hello World from Azure App Service')\n",
        ".gitignore": (
            "# Terraform specific\n"
            ".terraform/\n"
            "*.tfstate\n"
            "*.tfstate.backup\n"
            "*.tfvars\n"
            ".env\n"
            "*.conf\n"
            "\n"
            "# Python specific\n"
            "__pycache__/\n"
            "*.py[cod]\n"
            "venv/\n"
        )
    }

    # Create directories
    for d in directories:
        os.makedirs(os.path.join(project_root, d), exist_ok=True)
        print(f"✅ Directory ready: {d}")

    # Create files
    for path, content in files.items():
        full_path = os.path.join(project_root, path)
        if os.path.exists(full_path):
            print(f"⚠️ Skipped: {path} (already exists)")
        else:
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"✅ File created: {path}")

if __name__ == "__main__":
    create_project_structure()

//

