# =========================================
# Project Setup Script for Azure + Terraform
# =========================================

import os

def create_project_structure():
    # Bepaal project root (een level boven dit script)
    script_location = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_location)

    print(f"📍 Script location: {script_location}")
    print(f"📂 Project Root detected: {project_root}\n")

    # --- Folders ---
    directories = [
        ".github/workflows",
        "app",
        "terraform/test",
        "terraform/prod"
    ]

    # --- Files & content placeholders ---
    files = {
        # App folder
        os.path.join("app", "app.py"): "# Placeholder app\nprint('Hello World from Azure App Service')\n",

        # Terraform folders
        os.path.join("terraform/test", "main.tf"): "# Terraform main configuration for TEST\n",
        os.path.join("terraform/test", "variables.tf"): "# Terraform variables for TEST\n",
        os.path.join("terraform/test", "network.tf"): "# Network resources for TEST\n",
        os.path.join("terraform/test", "logging.tf"): "# Logging & monitoring for TEST\n",
        os.path.join("terraform/test", "appservice.tf"): "# App Service resources for TEST\n",
        os.path.join("terraform/test", "terraform.tfvars"): "# Placeholders for TEST variables\n",

        os.path.join("terraform/prod", "main.tf"): "# Terraform main configuration for PROD\n",
        os.path.join("terraform/prod", "variables.tf"): "# Terraform variables for PROD\n",
        os.path.join("terraform/prod", "network.tf"): "# Network resources for PROD\n",
        os.path.join("terraform/prod", "logging.tf"): "# Logging & monitoring for PROD\n",
        os.path.join("terraform/prod", "appservice.tf"): "# App Service resources for PROD\n",
        os.path.join("terraform/prod", "terraform.tfvars"): "# Placeholders for PROD variables\n",

        # GitHub Actions
        os.path.join(".github/workflows", "ci-cd.yml"): "# Placeholder CI/CD workflow\n",

        # .gitignore
        ".gitignore": (
            "# Terraform specific\n"
            ".terraform/\n"
            "*.tfstate\n"
            "*.tfstate.backup\n"
            "*.tfvars\n"
            ".env\n\n"
            "# Python specific\n"
            "__pycache__/\n"
            "*.py[cod]\n"
            "venv/\n"
            "*.conf\n"
        )
    }

    # --- Create directories ---
    for dir_path in directories:
        full_path = os.path.join(project_root, dir_path)
        os.makedirs(full_path, exist_ok=True)
        print(f"✅ Directory checked/created: {dir_path}")

    # --- Create files ---
    for file_path, content in files.items():
        full_path = os.path.join(project_root, file_path)
        if not os.path.exists(full_path):
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"✅ File created: {file_path}")
        else:
            print(f"⚠️  Skipped: {file_path} (File already exists)")

    print("\n🎉 Project setup complete! Ready for Terraform init + CI/CD setup.")

if __name__ == "__main__":
    create_project_structure()
