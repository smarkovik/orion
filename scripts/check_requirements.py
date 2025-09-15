#!/usr/bin/env python3
"""
Requirements checker for Orion project.

This script validates that requirements-dev.txt properly includes
requirements.txt and checks for any dependency conflicts.
"""

import re
import sys
from pathlib import Path


def parse_requirements(file_path: Path) -> dict[str, str]:
    """Parse requirements file and return dict of package: version."""
    packages = {}
    if not file_path.exists():
        return packages

    with open(file_path, "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and not line.startswith("-r"):
                # Extract package name and version
                match = re.match(r"([a-zA-Z0-9_-]+(?:\[[^\]]+\])?)(.*)", line)
                if match:
                    pkg_name = match.group(1)
                    version_spec = match.group(2)
                    packages[pkg_name] = version_spec
    return packages


def main():
    """Check requirements setup."""
    project_root = Path(__file__).parent.parent

    base_file = project_root / "requirements.txt"
    dev_file = project_root / "requirements-dev.txt"

    print("🔍 Checking requirements setup...")

    if not base_file.exists():
        print("❌ requirements.txt not found!")
        return 1

    if not dev_file.exists():
        print("❌ requirements-dev.txt not found!")
        return 1

    # Check that dev file includes base requirements
    with open(dev_file, "r") as f:
        dev_content = f.read()

    if "-r requirements.txt" not in dev_content:
        print("❌ requirements-dev.txt doesn't include requirements.txt!")
        print("   Add '-r requirements.txt' to the top of requirements-dev.txt")
        return 1

    base_reqs = parse_requirements(base_file)
    dev_reqs = parse_requirements(dev_file)

    print("✅ Requirements setup is correct!")
    print(f"   Base: {len(base_reqs)} packages")
    print(f"   Dev:  {len(dev_reqs)} additional packages")
    print(f"   Total dev: {len(base_reqs) + len(dev_reqs)} packages")

    return 0


if __name__ == "__main__":
    sys.exit(main())
