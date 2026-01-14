#!/usr/bin/env python3
"""
Create features from JSON file.

This script is used by the /expand-project Claude Code CLI command
to persist features to the SQLite database.

Usage:
    python scripts/create_features_from_json.py <project_dir> <json_file>

Example:
    python scripts/create_features_from_json.py /home/user/my-app /tmp/features.json

The JSON file should contain an array of feature objects:
[
    {
        "category": "functional",
        "name": "User can login",
        "description": "Verify login flow works",
        "steps": ["Navigate to login", "Enter credentials", "Click submit"]
    },
    ...
]
"""
import json
import sys
from pathlib import Path

# Add project root to path for imports
root = Path(__file__).parent.parent
sys.path.insert(0, str(root))

from api.database import Feature, create_database


def main():
    if len(sys.argv) != 3:
        print("Usage: create_features_from_json.py <project_dir> <json_file>")
        print("  project_dir: Path to the Autocoder project")
        print("  json_file:   Path to JSON file with features array")
        sys.exit(1)

    project_dir = Path(sys.argv[1])
    json_file = Path(sys.argv[2])

    # Validate inputs
    if not project_dir.exists():
        print(f"ERROR: Project directory does not exist: {project_dir}")
        sys.exit(1)

    if not json_file.exists():
        print(f"ERROR: JSON file does not exist: {json_file}")
        sys.exit(1)

    # Load features from JSON
    try:
        with open(json_file, encoding="utf-8") as f:
            features = json.load(f)
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON in {json_file}: {e}")
        sys.exit(1)

    if not isinstance(features, list):
        print("ERROR: JSON must contain an array of features")
        sys.exit(1)

    if not features:
        print("WARNING: No features to create (empty array)")
        sys.exit(0)

    # Create database session
    _, SessionLocal = create_database(project_dir)
    session = SessionLocal()

    try:
        # Get max priority to append after existing features
        max_priority_feature = (
            session.query(Feature).order_by(Feature.priority.desc()).first()
        )
        current_priority = (
            (max_priority_feature.priority + 1) if max_priority_feature else 1
        )

        created = 0
        for f in features:
            # Validate required fields
            name = f.get("name")
            if not name:
                print(f"WARNING: Skipping feature without name: {f}")
                continue

            db_feature = Feature(
                priority=current_priority,
                category=f.get("category", "functional"),
                name=name,
                description=f.get("description", ""),
                steps=f.get("steps", []),
                passes=False,
            )
            session.add(db_feature)
            current_priority += 1
            created += 1

        session.commit()
        print(f"SUCCESS: Created {created} features in {project_dir}/features.db")
        print(f"Features are now in the pending queue (priority {current_priority - created} to {current_priority - 1})")

    except Exception as e:
        session.rollback()
        print(f"ERROR: Failed to create features: {e}")
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    main()
