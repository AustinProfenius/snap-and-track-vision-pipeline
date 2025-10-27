#!/usr/bin/env python3
"""
Verify that the test harness is properly set up.

Usage:
    python scripts/verify_setup.py
"""
import sys
from pathlib import Path
from typing import List, Tuple

# Colors for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
RESET = '\033[0m'


def check_file(path: Path, required: bool = True) -> bool:
    """Check if file exists."""
    exists = path.exists()
    status = f"{GREEN}✓{RESET}" if exists else f"{RED}✗{RESET}"
    req_str = "(required)" if required else "(optional)"
    print(f"  {status} {path} {req_str}")
    return exists or not required


def check_directory(path: Path) -> bool:
    """Check if directory exists."""
    exists = path.is_dir()
    status = f"{GREEN}✓{RESET}" if exists else f"{RED}✗{RESET}"
    print(f"  {status} {path}/")
    return exists


def check_import(module: str) -> bool:
    """Check if Python module can be imported."""
    try:
        __import__(module)
        print(f"  {GREEN}✓{RESET} {module}")
        return True
    except ImportError:
        print(f"  {RED}✗{RESET} {module}")
        return False


def main():
    print(f"\n{'='*60}")
    print("NutritionVerse Test Harness - Setup Verification")
    print(f"{'='*60}\n")

    all_checks_passed = True

    # 1. Check directory structure
    print("1. Directory Structure")
    required_dirs = [
        Path("configs"),
        Path("data"),
        Path("runs/logs"),
        Path("runs/results"),
        Path("src/adapters"),
        Path("src/core"),
        Path("src/ui"),
        Path("scripts")
    ]

    for dir_path in required_dirs:
        if not check_directory(dir_path):
            all_checks_passed = False

    # 2. Check configuration files
    print("\n2. Configuration Files")
    config_files = [
        (Path("configs/apis.yaml"), True),
        (Path("configs/tasks.yaml"), True),
        (Path("configs/schema_map.yaml"), False),  # Generated later
        (Path(".env"), False),  # User creates from .env.example
        (Path(".env.example"), True)
    ]

    for file_path, required in config_files:
        if not check_file(file_path, required):
            if required:
                all_checks_passed = False

    # 3. Check core modules
    print("\n3. Core Modules")
    modules = [
        Path("src/__init__.py"),
        Path("src/core/__init__.py"),
        Path("src/core/loader.py"),
        Path("src/core/schema.py"),
        Path("src/core/prompts.py"),
        Path("src/core/evaluator.py"),
        Path("src/core/runner.py"),
        Path("src/core/store.py"),
    ]

    for mod_path in modules:
        if not check_file(mod_path):
            all_checks_passed = False

    # 4. Check adapters
    print("\n4. API Adapters")
    adapters = [
        Path("src/adapters/__init__.py"),
        Path("src/adapters/openai_.py"),
        Path("src/adapters/claude_.py"),
        Path("src/adapters/gemini_.py"),
        Path("src/adapters/ollama_llava.py"),
    ]

    for adapter_path in adapters:
        if not check_file(adapter_path):
            all_checks_passed = False

    # 5. Check UI
    print("\n5. UI Components")
    if not check_file(Path("src/ui/app.py")):
        all_checks_passed = False

    # 6. Check dependencies
    print("\n6. Python Dependencies")
    dependencies = [
        "yaml",
        "dotenv",
        "numpy",
        "pandas",
        "openai",
        "anthropic",
        "google.generativeai",
        "aiohttp",
        "pyarrow",
        "streamlit",
        "plotly"
    ]

    deps_missing = False
    for dep in dependencies:
        if not check_import(dep):
            deps_missing = True
            all_checks_passed = False

    if deps_missing:
        print(f"\n  {YELLOW}→{RESET} Install missing dependencies:")
        print(f"    pip install -r requirements.txt")

    # 7. Check dataset
    print("\n7. Dataset (NutritionVerse-Real)")
    dataset_dir = Path("data/nvreal")
    if dataset_dir.exists():
        images = list(dataset_dir.glob("**/*.jpg")) + list(dataset_dir.glob("**/*.png"))
        annotations = list(dataset_dir.glob("**/*.json"))

        if images and annotations:
            print(f"  {GREEN}✓{RESET} Found {len(images)} images and {len(annotations)} annotations")
        else:
            print(f"  {YELLOW}!{RESET} Directory exists but appears empty")
            print(f"    Images: {len(images)}, Annotations: {len(annotations)}")
    else:
        print(f"  {YELLOW}!{RESET} Dataset directory not found (expected at data/nvreal/)")
        print(f"    This is OK if you haven't downloaded the dataset yet")

    # 8. Check environment variables
    print("\n8. Environment Variables")
    env_file = Path(".env")
    if env_file.exists():
        print(f"  {GREEN}✓{RESET} .env file exists")

        # Read and check for keys
        with open(env_file) as f:
            content = f.read()

        keys_to_check = [
            ("OPENAI_API_KEY", "OpenAI"),
            ("ANTHROPIC_API_KEY", "Anthropic"),
            ("GOOGLE_API_KEY", "Google"),
        ]

        for key, name in keys_to_check:
            if key in content and not content.split(key)[1].split('\n')[0].strip().endswith("_here"):
                print(f"  {GREEN}✓{RESET} {name} API key configured")
            else:
                print(f"  {YELLOW}!{RESET} {name} API key not set (optional)")
    else:
        print(f"  {YELLOW}!{RESET} .env file not found")
        print(f"    {YELLOW}→{RESET} Copy .env.example to .env and add your API keys:")
        print(f"      cp .env.example .env")

    # 9. Summary
    print(f"\n{'='*60}")
    if all_checks_passed:
        print(f"{GREEN}✓ All required checks passed!{RESET}")
        print(f"\nNext steps:")
        print(f"  1. Place NutritionVerse-Real data in data/nvreal/")
        print(f"  2. Run schema discovery:")
        print(f"     python -m src.core.loader --inspect")
        print(f"  3. Try a dry run:")
        print(f"     python -m src.core.runner --api openai --task dish_totals --end 5 --dry-run")
        print(f"  4. Launch UI:")
        print(f"     streamlit run src/ui/app.py")
    else:
        print(f"{RED}✗ Some checks failed{RESET}")
        print(f"\nPlease address the issues above before proceeding.")
        sys.exit(1)

    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
