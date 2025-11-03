# SPDX-FileCopyrightText: 2025 Mark Emila (Caestudy) <https://caestudy.com>
# SPDX-License-Identifier: BSL-1.1

"""
MkDocs build hooks - automatically sync files before build.

This ensures that LICENSE and CLA.md copies in docs/ are always current
when building documentation locally.
"""

import shutil
from pathlib import Path


def on_pre_build(config):
    """
    Sync root files to docs directory before building.

    This hook runs automatically before every mkdocs build/serve.
    """
    repo_root = Path(__file__).parent
    docs_dir = repo_root / "docs"

    print("🔄 Syncing root files to docs directory...")

    # Sync LICENSE to docs/license.md
    license_src = repo_root / "LICENSE"
    license_dst = docs_dir / "license.md"
    if license_src.exists():
        shutil.copy2(license_src, license_dst)
        print("  ✓ LICENSE → docs/license.md")
    else:
        print("  ✗ LICENSE not found!")

    # Sync CLA.md to docs/cla.md
    cla_src = repo_root / "CLA.md"
    cla_dst = docs_dir / "cla.md"
    if cla_src.exists():
        shutil.copy2(cla_src, cla_dst)
        print("  ✓ CLA.md → docs/cla.md")
    else:
        print("  ✗ CLA.md not found!")

    # Sync README.md to docs/index.md with link transformation
    readme_src = repo_root / "README.md"
    index_dst = docs_dir / "index.md"
    if readme_src.exists():
        content = readme_src.read_text()

        # Transform links for docs context
        content = content.replace("](docs/", "](")  # Remove docs/ prefix
        content = content.replace("](LICENSE)", "](license.md)")  # Fix LICENSE link
        content = content.replace("](CLA.md)", "](cla.md)")  # Fix CLA link

        index_dst.write_text(content)
        print("  ✓ README.md → docs/index.md (with link fixes)")
    else:
        print("  ✗ README.md not found!")

    print("✅ File sync complete\n")
