#!/usr/bin/env python3
"""
Environment Snapshot Generator

Creates a .env.snapshot file with current versions of all critical packages
for debugging and reproducibility purposes.

Usage:
    python scripts/generate_env_snapshot.py

Output:
    .env.snapshot in project root with package versions
"""

import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Critical packages to track
CRITICAL_PACKAGES = [
    "torch",
    "transformers",
    "tokenizers",
    "numpy",
    "spacy",
    "fsspec",
    "sentence-transformers",
]

# Additional packages that are often useful for debugging
ADDITIONAL_PACKAGES = [
    "accelerate",
    "bitsandbytes",
    # 'weaviate-client',  # REMOVED: Migrated to Qdrant
    "fastapi",
    "flask",
    "scikit-learn",
    "requests",
    "python-dotenv",
    "psutil",
    "rich",
    "discord.py",
    "aiohttp",
    "pydantic",
    "pillow",
]


def get_package_version(package_name):
    """Get version of a package using pip show."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "show", package_name],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode == 0:
            lines = result.stdout.strip().split("\n")
            for line in lines:
                if line.startswith("Version:"):
                    return line.split(":", 1)[1].strip()
        return "NOT_INSTALLED"
    except Exception as e:
        print(f"Error checking {package_name}: {e}")
        return "ERROR"


def get_python_version():
    """Get Python version."""
    return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"


def get_system_info():
    """Get basic system information."""
    import platform

    try:
        import torch

        cuda_available = torch.cuda.is_available()
        cuda_version = torch.version.cuda if cuda_available else "N/A"
        torch_version = torch.__version__
    except ImportError:
        cuda_available = False
        cuda_version = "N/A"
        torch_version = "NOT_INSTALLED"

    return {
        "python_version": get_python_version(),
        "platform": platform.platform(),
        "architecture": platform.architecture()[0],
        "cuda_available": cuda_available,
        "cuda_version": cuda_version,
        "torch_version": torch_version,
    }


def generate_snapshot():
    """Generate the environment snapshot file."""

    # Get current timestamp
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")

    # Get system info
    system_info = get_system_info()

    # Collect package versions
    print("Collecting package versions...")

    snapshot_content = [
        "# Environment Snapshot",
        f"# Generated: {timestamp}",
        f"# Python: {system_info['python_version']}",
        f"# Platform: {system_info['platform']}",
        f"# Architecture: {system_info['architecture']}",
        f"# CUDA Available: {system_info['cuda_available']}",
        f"# CUDA Version: {system_info['cuda_version']}",
        "",
        "# === CRITICAL PACKAGES ===",
        "# Core ML/NLP dependencies for Axiom AI",
    ]

    # Add critical packages
    for package in CRITICAL_PACKAGES:
        version = get_package_version(package)
        snapshot_content.append(f"{package}=={version}")
        print(f"  {package}: {version}")

    snapshot_content.extend(
        ["", "# === ADDITIONAL PACKAGES ===", "# Supporting dependencies"]
    )

    # Add additional packages
    for package in ADDITIONAL_PACKAGES:
        version = get_package_version(package)
        snapshot_content.append(f"{package}=={version}")
        print(f"  {package}: {version}")

    # Add pip freeze output for completeness
    print("\nGenerating complete package list...")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "freeze"],
            capture_output=True,
            text=True,
            check=True,
        )

        snapshot_content.extend(
            [
                "",
                "# === COMPLETE PACKAGE LIST ===",
                "# Full pip freeze output for complete reproducibility",
                "",
            ]
        )

        # Filter and sort the pip freeze output
        freeze_lines = sorted(
            [line.strip() for line in result.stdout.strip().split("\n") if line.strip()]
        )
        snapshot_content.extend(freeze_lines)

    except subprocess.CalledProcessError as e:
        print(f"Warning: Could not get pip freeze output: {e}")
        snapshot_content.extend(
            [
                "",
                "# === COMPLETE PACKAGE LIST ===",
                "# Error: Could not retrieve full package list",
            ]
        )

    # Write to .env.snapshot
    project_root = Path(__file__).parent.parent
    snapshot_path = project_root / ".env.snapshot"

    with open(snapshot_path, "w") as f:
        f.write("\n".join(snapshot_content))
        f.write("\n")  # Final newline

    print(f"\n✅ Environment snapshot written to: {snapshot_path}")
    print(f"📊 Tracked {len(CRITICAL_PACKAGES)} critical packages")
    print(f"📦 Tracked {len(ADDITIONAL_PACKAGES)} additional packages")

    return snapshot_path


def main():
    """Main entry point."""
    print("🔍 Generating environment snapshot...")
    print("=" * 50)

    try:
        snapshot_path = generate_snapshot()
        print("=" * 50)
        print("✅ Snapshot generation complete!")
        print(f"📁 File: {snapshot_path}")
        print("\nUse this snapshot for:")
        print("  • Debugging environment issues")
        print("  • Reproducing bugs")
        print("  • Sharing environment state")
        print("  • Version tracking")

    except Exception as e:
        print(f"❌ Error generating snapshot: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
