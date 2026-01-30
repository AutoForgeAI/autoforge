#!/usr/bin/env python3
"""
Version Bump Script
===================

Automatically increments the patch version in VERSION.json.
Called by the pre-commit hook to keep version updated.

Version format: {year}.{major}.{minor}.{patch}
- patch increments on each commit
- minor increments when patch would exceed 99 (resets patch to 0)
- major increments when minor would exceed 99 (resets minor and patch to 0)
- year is manually updated for major releases
"""

import json
import sys
from datetime import datetime
from pathlib import Path


def bump_version(version_file: Path) -> bool:
    """
    Bump the patch version in VERSION.json.

    Returns:
        True if version was bumped, False on error
    """
    try:
        with open(version_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Get current values
        year = data.get('year', 2026)
        major = data.get('major', 1)
        minor = data.get('minor', 0)
        patch = data.get('patch', 0)

        # Increment patch, with rollover logic
        patch += 1
        if patch > 99:
            patch = 0
            minor += 1
        if minor > 99:
            minor = 0
            major += 1

        # Update version string
        version_str = f"{year}.{major}.{minor}.{patch}"

        # Update data
        data['version'] = version_str
        data['year'] = year
        data['major'] = major
        data['minor'] = minor
        data['patch'] = patch
        data['buildDate'] = datetime.now().strftime('%Y-%m-%d')

        # Write back
        with open(version_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
            f.write('\n')  # Add trailing newline

        print(f"Version bumped to {version_str}")
        return True

    except Exception as e:
        print(f"Error bumping version: {e}", file=sys.stderr)
        return False


def main():
    # Find VERSION.json relative to this script
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent
    version_file = repo_root / 'VERSION.json'

    if not version_file.exists():
        print(f"VERSION.json not found at {version_file}", file=sys.stderr)
        sys.exit(1)

    if bump_version(version_file):
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == '__main__':
    main()
