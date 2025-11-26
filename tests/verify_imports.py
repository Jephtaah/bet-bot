#!/usr/bin/env python3
"""
Import Validation Script for bet-bot

This script verifies that all required dependencies are properly installed
and can be imported without errors. Used during development setup to validate
the virtual environment.

Run: python tests/verify_imports.py
Expected: All imports succeed with no errors
"""

import sys
from pathlib import Path


def verify_imports():
    """Verify all required packages are importable."""
    print("Verifying imports for bet-bot dependencies...\n")

    # Define all packages to verify
    core_packages = {
        "typer": "CLI framework with type hints",
        "pydantic": "Data validation with type hints",
        "httpx": "Async HTTP client with connection pooling",
        "pandas": "Data manipulation and analysis",
        "rich": "Beautiful terminal formatting",
        "dotenv": "Environment variable management",
        "openai": "OpenAI API SDK",
        "tenacity": "Retry logic with exponential backoff",
        "bs4": "Web scraping (beautifulsoup4)",
    }

    dev_packages = {
        "pytest": "Testing framework",
        "pytest_asyncio": "Async test support",
        "mypy": "Static type checking",
        "ruff": "Fast Python linter",
    }

    all_packages = {**core_packages, **dev_packages}
    failed_imports = []
    successful_imports = []

    # Try importing each package
    for package_name, description in all_packages.items():
        try:
            __import__(package_name)
            successful_imports.append((package_name, description))
            print(f"✓ {package_name:20} - {description}")
        except ImportError as e:
            failed_imports.append((package_name, str(e)))
            print(f"✗ {package_name:20} - FAILED: {str(e)}")

    # Print summary
    print("\n" + "=" * 70)
    print(f"Summary: {len(successful_imports)}/{len(all_packages)} packages imported successfully")
    print("=" * 70)

    if failed_imports:
        print("\nFailed Imports:")
        for package_name, error in failed_imports:
            print(f"  - {package_name}: {error}")
        return False
    else:
        print("\nAll imports successful! Virtual environment is properly configured.")
        return True


def verify_python_version():
    """Verify Python version meets minimum requirement."""
    print("Checking Python version...\n")

    min_major, min_minor = 3, 10
    current_major, current_minor = sys.version_info.major, sys.version_info.minor

    version_string = f"{current_major}.{current_minor}"
    min_version_string = f"{min_major}.{min_minor}"

    print(f"Current Python: {version_string}")
    print(f"Minimum Required: {min_version_string}+")

    if current_major > min_major or (current_major == min_major and current_minor >= min_minor):
        print("✓ Python version meets requirement\n")
        return True
    else:
        print(f"⚠ WARNING: Python {version_string} detected, but {min_version_string}+ is required")
        print("Modern syntax and type hints require Python 3.10+")
        print("Consider upgrading Python to avoid compatibility issues\n")
        return False


def verify_package_versions():
    """Display installed versions of key packages."""
    print("Key Package Versions:")
    print("-" * 50)

    packages_to_check = [
        ("typer", "typer"),
        ("pydantic", "pydantic"),
        ("httpx", "httpx"),
        ("pandas", "pandas"),
        ("pytest", "pytest"),
        ("mypy", "mypy"),
    ]

    for import_name, display_name in packages_to_check:
        try:
            module = __import__(import_name)
            version = getattr(module, "__version__", "unknown")
            print(f"  {display_name:15} {version}")
        except Exception as e:
            print(f"  {display_name:15} (error: {str(e)})")

    print()


if __name__ == "__main__":
    # Run all verifications
    python_ok = verify_python_version()
    imports_ok = verify_imports()
    verify_package_versions()

    # Exit with appropriate code
    if imports_ok:
        print("✓ All validations passed. Virtual environment is ready!")
        sys.exit(0)
    else:
        print("✗ Some validations failed. Check errors above.")
        sys.exit(1)
