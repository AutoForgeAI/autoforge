# Migration Guide

This guide explains how to migrate existing Autocoder projects to the new v2 architecture.

## Overview

The v2 architecture introduces a hierarchical structure:

```
Project
└── Phases (development stages with approval gates)
    └── Features (groups of related tasks)
        └── Tasks (individual work items, formerly "features")
```

**Key Changes:**
- What was called "features" is now called "tasks"
- Tasks are grouped into "features" (new concept)
- Features belong to "phases" (e.g., "Foundation", "Core Features", "Polish")
- Tasks can have dependencies on other tasks
- Phases have approval workflows
- Usage tracking monitors API consumption

## Quick Migration

### Single Project

```bash
# Check current status
python -m api.migration /path/to/project --check

# Preview migration (dry run)
python -m api.migration /path/to/project --dry-run

# Perform migration
python -m api.migration /path/to/project
```

### All Registered Projects

```bash
# Preview all migrations
python -m api.migration --all --dry-run

# Migrate all projects
python -m api.migration --all
```

## What Gets Migrated

### From Legacy Schema
- `features` table → `tasks` table
- Priority, category, name, description, steps preserved
- Pass/fail status preserved
- In-progress status preserved

### Created Automatically
- **Default Phase**: "Phase 1: Initial Development"
- **Default Feature**: "Core Features"
- All tasks linked to the default feature
- Backup created: `features.db.backup.<timestamp>`

## Customizing Migration

### Custom Phase/Feature Names

```bash
python -m api.migration /path/to/project \
  --phase-name "Phase 1: Foundation" \
  --feature-name "User Authentication"
```

### Programmatic Migration

```python
from pathlib import Path
from api.migration import migrate_to_v2, check_migration_status

project_dir = Path("/path/to/project")

# Check status first
status = check_migration_status(project_dir)
print(f"Schema version: {status['schema_version']}")

# Migrate with custom names
result = migrate_to_v2(
    project_dir=project_dir,
    project_name="my-app",
    phase_name="Foundation",
    feature_name="Initial Features",
)

if result["status"] == "success":
    print(f"Migrated {result['migrated_count']} tasks")
```

## Post-Migration Organization

After migration, you can reorganize tasks:

### 1. Create Additional Phases

```python
from api.database import create_database, Phase

engine, session_maker = create_database(project_dir)
db = session_maker()

# Add phases for your project structure
phases = [
    ("Phase 2: Core Features", "Main application functionality", 2),
    ("Phase 3: Polish", "UI improvements and bug fixes", 3),
]

for name, description, order in phases:
    phase = Phase(
        project_name="my-app",
        name=name,
        description=description,
        order=order,
        status="pending",
    )
    db.add(phase)

db.commit()
```

### 2. Create Features Within Phases

```python
from api.database import Feature

# Group related tasks into features
auth_feature = Feature(
    phase_id=phase_id,
    name="User Authentication",
    description="Login, registration, and session management",
    status="pending",
    priority=1,
)
db.add(auth_feature)
db.commit()
```

### 3. Move Tasks to Features

```python
from api.database import Task

# Update tasks to belong to specific features
db.query(Task).filter(
    Task.name.like("%login%")
).update({"feature_id": auth_feature.id})

db.commit()
```

### 4. Add Task Dependencies

```python
# Task B depends on Task A completing first
task_b = db.query(Task).filter(Task.name == "Implement dashboard").first()
task_a = db.query(Task).filter(Task.name == "Create user model").first()

task_b.depends_on = [task_a.id]
db.commit()
```

## Verifying Migration

### Check Schema Version

```bash
python -m api.migration /path/to/project --check
```

Expected output for v2:
```json
{
  "exists": true,
  "path": "/path/to/project/features.db",
  "schema_version": "v2",
  "phases": 1,
  "features": 1,
  "tasks": 15,
  "tasks_passing": 8
}
```

### UI Verification

After migration, the UI will show:
- Phases with progress bars
- Expandable features showing tasks
- Task dependency indicators
- Phase approval buttons

## Rollback

If migration fails, the backup is automatically restored. To manually rollback:

```bash
# Find your backup
ls /path/to/project/features.db.backup.*

# Restore it
cp /path/to/project/features.db.backup.TIMESTAMP /path/to/project/features.db
```

## Troubleshooting

### "Already migrated to v2 schema"

The project has already been migrated. Use `--check` to verify the current state.

### "Database does not exist"

The project doesn't have a `features.db` file yet. Run the initializer agent first.

### "Empty database, no migration needed"

The database exists but has no data. This is normal for new projects.

### Tasks Not Showing in UI

Ensure the MCP server is restarted after migration to pick up the new schema:
```bash
# Stop and restart the agent
# The UI will automatically refresh
```

## New Features Post-Migration

### Phase Workflow

Phases support an approval workflow:
```
pending → in_progress → awaiting_approval → completed
```

Submit phases for approval when all tasks pass, then approve to finalize.

### Task Dependencies

Create dependencies to ensure tasks run in order:
```python
# In the UI: Use the dependency graph view
# Programmatically: Set depends_on field
```

### Usage Monitoring

Track API usage with the new dashboard:
- Daily/monthly token limits
- Cost tracking
- Smart scheduling based on usage levels

### Multi-Agent Support

The v2 architecture supports multiple agent types:
- Architect Agent
- Coding Agent
- Reviewer Agent
- Testing Agent

Enable in your project's configuration to use specialized agents.

## Questions?

See [CLAUDE.md](./CLAUDE.md) for detailed architecture documentation.
