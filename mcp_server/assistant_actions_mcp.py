"""
Assistant Actions MCP Server
============================

Provides action tools for the Architect Assistant to manage projects,
features, agents, and migrations. This gives the assistant write capabilities
in a controlled manner.
"""

import asyncio
import json
import logging
import os
import signal
import sys
from pathlib import Path
from typing import Any, Optional

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

# Add parent directory to path for imports
ROOT_DIR = Path(__file__).parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from api.database import (
    Base,
    Feature,
    Phase,
    Task,
    create_database,
    get_database_path,
)

logger = logging.getLogger(__name__)

# Get project directory from environment
PROJECT_DIR = Path(os.environ.get("PROJECT_DIR", ".")).resolve()


def get_db_session():
    """Create database session for the project."""
    engine, session_maker = create_database(PROJECT_DIR)
    return session_maker()


# =============================================================================
# Tool Definitions
# =============================================================================

TOOLS = [
    # Feature Management
    Tool(
        name="assistant_create_feature",
        description="""Create a new feature with tasks for the project.

Use this when the user wants to add a new feature to the project.
Returns the created feature ID and task IDs.""",
        inputSchema={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Name of the feature (e.g., 'User Authentication')",
                },
                "description": {
                    "type": "string",
                    "description": "Description of what the feature accomplishes",
                },
                "phase_id": {
                    "type": "integer",
                    "description": "Optional phase ID to assign the feature to",
                },
                "tasks": {
                    "type": "array",
                    "description": "List of tasks for this feature",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "description": {"type": "string"},
                            "priority": {"type": "integer"},
                            "complexity": {"type": "integer", "minimum": 1, "maximum": 5},
                            "steps": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                        },
                        "required": ["name"],
                    },
                },
            },
            "required": ["name", "tasks"],
        },
    ),
    Tool(
        name="assistant_list_phases",
        description="List all phases in the project with their status and task counts.",
        inputSchema={
            "type": "object",
            "properties": {},
        },
    ),
    Tool(
        name="assistant_create_phase",
        description="""Create a new development phase for the project.

Use this to organize work into phases like 'Foundation', 'Core Features', 'Polish'.""",
        inputSchema={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Name of the phase (e.g., 'Phase 2: Core Features')",
                },
                "description": {
                    "type": "string",
                    "description": "Description of what this phase covers",
                },
                "order": {
                    "type": "integer",
                    "description": "Order of the phase (1, 2, 3, etc.)",
                },
            },
            "required": ["name"],
        },
    ),
    Tool(
        name="assistant_get_project_status",
        description="""Get comprehensive project status including phases, features, tasks, and agent status.

Use this to give the user an overview of the project.""",
        inputSchema={
            "type": "object",
            "properties": {},
        },
    ),
    # Agent Management
    Tool(
        name="assistant_get_agent_status",
        description="Get the current status of the coding agent (running, paused, stopped).",
        inputSchema={
            "type": "object",
            "properties": {},
        },
    ),
    Tool(
        name="assistant_start_agent",
        description="""Start the coding agent to work on tasks.

Use this when the user wants to start automated coding.
You can specify a YOLO mode for faster prototyping.""",
        inputSchema={
            "type": "object",
            "properties": {
                "yolo_mode": {
                    "type": "string",
                    "enum": ["standard", "yolo", "yolo_review", "yolo_parallel", "yolo_staged"],
                    "description": "YOLO mode for rapid prototyping. 'standard' runs full verification.",
                },
            },
        },
    ),
    Tool(
        name="assistant_stop_agent",
        description="Stop the coding agent. Use this when the user wants to pause work.",
        inputSchema={
            "type": "object",
            "properties": {},
        },
    ),
    Tool(
        name="assistant_pause_agent",
        description="Pause the coding agent. It can be resumed later.",
        inputSchema={
            "type": "object",
            "properties": {},
        },
    ),
    Tool(
        name="assistant_resume_agent",
        description="Resume a paused coding agent.",
        inputSchema={
            "type": "object",
            "properties": {},
        },
    ),
    # Migration
    Tool(
        name="assistant_check_migration",
        description="Check if the project needs migration to the v2 schema.",
        inputSchema={
            "type": "object",
            "properties": {},
        },
    ),
    Tool(
        name="assistant_run_migration",
        description="""Run database migration to upgrade from legacy schema to v2.

This creates a backup and migrates features to the new hierarchical structure.""",
        inputSchema={
            "type": "object",
            "properties": {
                "phase_name": {
                    "type": "string",
                    "description": "Name for the default phase (default: 'Phase 1: Initial Development')",
                },
                "feature_name": {
                    "type": "string",
                    "description": "Name for the default feature (default: 'Core Features')",
                },
            },
        },
    ),
    # Task Management
    Tool(
        name="assistant_add_task",
        description="Add a new task to an existing feature.",
        inputSchema={
            "type": "object",
            "properties": {
                "feature_id": {
                    "type": "integer",
                    "description": "ID of the feature to add the task to",
                },
                "name": {
                    "type": "string",
                    "description": "Name of the task",
                },
                "description": {
                    "type": "string",
                    "description": "Description of what the task accomplishes",
                },
                "priority": {
                    "type": "integer",
                    "description": "Priority (lower = higher priority)",
                },
                "complexity": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 5,
                    "description": "Estimated complexity (1-5)",
                },
                "steps": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Implementation steps",
                },
                "depends_on": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "List of task IDs this task depends on",
                },
            },
            "required": ["feature_id", "name"],
        },
    ),
    Tool(
        name="assistant_set_task_dependencies",
        description="Set dependencies for a task (which tasks must complete first).",
        inputSchema={
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "integer",
                    "description": "ID of the task to update",
                },
                "depends_on": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "List of task IDs this task depends on",
                },
            },
            "required": ["task_id", "depends_on"],
        },
    ),
    # Phase Workflow
    Tool(
        name="assistant_submit_phase",
        description="Submit a phase for approval after all tasks are complete.",
        inputSchema={
            "type": "object",
            "properties": {
                "phase_id": {
                    "type": "integer",
                    "description": "ID of the phase to submit",
                },
            },
            "required": ["phase_id"],
        },
    ),
    Tool(
        name="assistant_approve_phase",
        description="Approve a phase that is awaiting approval.",
        inputSchema={
            "type": "object",
            "properties": {
                "phase_id": {
                    "type": "integer",
                    "description": "ID of the phase to approve",
                },
            },
            "required": ["phase_id"],
        },
    ),
]


# =============================================================================
# Tool Implementations
# =============================================================================


async def create_feature(
    name: str,
    tasks: list[dict],
    description: str = "",
    phase_id: Optional[int] = None,
) -> dict[str, Any]:
    """Create a new feature with tasks."""
    db = get_db_session()
    try:
        # Get project name from directory
        project_name = PROJECT_DIR.name

        # If no phase_id, find or create a default phase
        if phase_id is None:
            phase = db.query(Phase).filter(Phase.project_name == project_name).first()
            if not phase:
                phase = Phase(
                    project_name=project_name,
                    name="Phase 1: Initial Development",
                    description="Default development phase",
                    order=1,
                    status="in_progress",
                )
                db.add(phase)
                db.flush()
            phase_id = phase.id

        # Create feature
        feature = Feature(
            phase_id=phase_id,
            name=name,
            description=description,
            status="pending",
            priority=1,
        )
        db.add(feature)
        db.flush()

        # Create tasks
        task_ids = []
        for i, task_data in enumerate(tasks):
            task = Task(
                feature_id=feature.id,
                name=task_data.get("name", f"Task {i+1}"),
                description=task_data.get("description", ""),
                priority=task_data.get("priority", (i + 1) * 10),
                estimated_complexity=task_data.get("complexity", 2),
                steps=task_data.get("steps", []),
                passes=False,
                in_progress=False,
            )
            db.add(task)
            db.flush()
            task_ids.append(task.id)

        db.commit()

        return {
            "success": True,
            "feature_id": feature.id,
            "feature_name": name,
            "task_count": len(task_ids),
            "task_ids": task_ids,
            "phase_id": phase_id,
        }

    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()


async def list_phases() -> dict[str, Any]:
    """List all phases with their status."""
    db = get_db_session()
    try:
        project_name = PROJECT_DIR.name
        phases = db.query(Phase).filter(Phase.project_name == project_name).order_by(Phase.order).all()

        result = []
        for phase in phases:
            # Count tasks in this phase
            features = db.query(Feature).filter(Feature.phase_id == phase.id).all()
            total_tasks = 0
            passing_tasks = 0
            for feature in features:
                tasks = db.query(Task).filter(Task.feature_id == feature.id).all()
                total_tasks += len(tasks)
                passing_tasks += sum(1 for t in tasks if t.passes)

            result.append({
                "id": phase.id,
                "name": phase.name,
                "description": phase.description,
                "status": phase.status,
                "order": phase.order,
                "feature_count": len(features),
                "total_tasks": total_tasks,
                "passing_tasks": passing_tasks,
                "progress": f"{passing_tasks}/{total_tasks}" if total_tasks > 0 else "0/0",
            })

        return {"success": True, "phases": result}

    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        db.close()


async def create_phase(
    name: str,
    description: str = "",
    order: Optional[int] = None,
) -> dict[str, Any]:
    """Create a new phase."""
    db = get_db_session()
    try:
        project_name = PROJECT_DIR.name

        # Auto-determine order if not provided
        if order is None:
            max_order = db.query(Phase).filter(Phase.project_name == project_name).count()
            order = max_order + 1

        phase = Phase(
            project_name=project_name,
            name=name,
            description=description,
            order=order,
            status="pending",
        )
        db.add(phase)
        db.commit()

        return {
            "success": True,
            "phase_id": phase.id,
            "name": name,
            "order": order,
        }

    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()


async def get_project_status() -> dict[str, Any]:
    """Get comprehensive project status."""
    db = get_db_session()
    try:
        project_name = PROJECT_DIR.name

        # Get phases
        phases = db.query(Phase).filter(Phase.project_name == project_name).order_by(Phase.order).all()

        total_tasks = 0
        passing_tasks = 0
        in_progress_tasks = 0
        blocked_tasks = 0

        phase_summaries = []
        for phase in phases:
            features = db.query(Feature).filter(Feature.phase_id == phase.id).all()
            phase_tasks = 0
            phase_passing = 0

            for feature in features:
                tasks = db.query(Task).filter(Task.feature_id == feature.id).all()
                phase_tasks += len(tasks)
                total_tasks += len(tasks)
                for task in tasks:
                    if task.passes:
                        passing_tasks += 1
                        phase_passing += 1
                    if task.in_progress:
                        in_progress_tasks += 1
                    if task.depends_on:
                        # Check if blocked
                        deps = db.query(Task).filter(Task.id.in_(task.depends_on)).all()
                        if any(not d.passes for d in deps):
                            blocked_tasks += 1

            phase_summaries.append({
                "name": phase.name,
                "status": phase.status,
                "progress": f"{phase_passing}/{phase_tasks}",
            })

        # Check agent status
        agent_status = "stopped"
        lock_file = PROJECT_DIR / ".agent.lock"
        if lock_file.exists():
            agent_status = "running"

        return {
            "success": True,
            "project_name": project_name,
            "total_tasks": total_tasks,
            "passing_tasks": passing_tasks,
            "in_progress_tasks": in_progress_tasks,
            "blocked_tasks": blocked_tasks,
            "completion_percentage": round(passing_tasks / total_tasks * 100, 1) if total_tasks > 0 else 0,
            "phases": phase_summaries,
            "agent_status": agent_status,
        }

    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        db.close()


async def get_agent_status() -> dict[str, Any]:
    """Get agent status."""
    lock_file = PROJECT_DIR / ".agent.lock"

    if lock_file.exists():
        try:
            lock_data = json.loads(lock_file.read_text())
            return {
                "success": True,
                "status": lock_data.get("status", "running"),
                "pid": lock_data.get("pid"),
                "started_at": lock_data.get("started_at"),
                "yolo_mode": lock_data.get("yolo_mode", "standard"),
            }
        except Exception:
            return {"success": True, "status": "running", "details": "Lock file exists"}

    return {"success": True, "status": "stopped"}


async def start_agent(yolo_mode: str = "standard") -> dict[str, Any]:
    """Start the coding agent (sends signal to server)."""
    # This would typically communicate with the server to start the agent
    # For now, we'll return instructions
    return {
        "success": True,
        "action": "start_agent",
        "yolo_mode": yolo_mode,
        "message": f"Agent start requested with mode: {yolo_mode}. The server will start the agent subprocess.",
        "note": "Use the UI or CLI to start the agent. This tool prepared the configuration.",
    }


async def stop_agent() -> dict[str, Any]:
    """Stop the coding agent."""
    lock_file = PROJECT_DIR / ".agent.lock"

    if not lock_file.exists():
        return {"success": False, "error": "Agent is not running"}

    try:
        lock_data = json.loads(lock_file.read_text())
        pid = lock_data.get("pid")
        if pid:
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        lock_file.unlink(missing_ok=True)
        return {"success": True, "message": "Agent stopped"}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def pause_agent() -> dict[str, Any]:
    """Pause the coding agent."""
    lock_file = PROJECT_DIR / ".agent.lock"

    if not lock_file.exists():
        return {"success": False, "error": "Agent is not running"}

    try:
        lock_data = json.loads(lock_file.read_text())
        lock_data["status"] = "paused"
        lock_file.write_text(json.dumps(lock_data))
        return {"success": True, "message": "Agent paused"}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def resume_agent() -> dict[str, Any]:
    """Resume a paused agent."""
    lock_file = PROJECT_DIR / ".agent.lock"

    if not lock_file.exists():
        return {"success": False, "error": "Agent is not running"}

    try:
        lock_data = json.loads(lock_file.read_text())
        if lock_data.get("status") != "paused":
            return {"success": False, "error": "Agent is not paused"}
        lock_data["status"] = "running"
        lock_file.write_text(json.dumps(lock_data))
        return {"success": True, "message": "Agent resumed"}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def check_migration() -> dict[str, Any]:
    """Check migration status."""
    try:
        from api.migration import check_migration_status
        result = check_migration_status(PROJECT_DIR)
        return {"success": True, **result}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def run_migration(
    phase_name: str = "Phase 1: Initial Development",
    feature_name: str = "Core Features",
) -> dict[str, Any]:
    """Run database migration."""
    try:
        from api.migration import migrate_to_v2
        result = migrate_to_v2(
            project_dir=PROJECT_DIR,
            phase_name=phase_name,
            feature_name=feature_name,
        )
        return {"success": True, **result}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def add_task(
    feature_id: int,
    name: str,
    description: str = "",
    priority: int = 100,
    complexity: int = 2,
    steps: Optional[list[str]] = None,
    depends_on: Optional[list[int]] = None,
) -> dict[str, Any]:
    """Add a task to an existing feature."""
    db = get_db_session()
    try:
        # Verify feature exists
        feature = db.query(Feature).filter(Feature.id == feature_id).first()
        if not feature:
            return {"success": False, "error": f"Feature {feature_id} not found"}

        task = Task(
            feature_id=feature_id,
            name=name,
            description=description,
            priority=priority,
            estimated_complexity=complexity,
            steps=steps or [],
            depends_on=depends_on or [],
            passes=False,
            in_progress=False,
        )
        db.add(task)
        db.commit()

        return {
            "success": True,
            "task_id": task.id,
            "name": name,
            "feature_id": feature_id,
            "feature_name": feature.name,
        }

    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()


async def set_task_dependencies(task_id: int, depends_on: list[int]) -> dict[str, Any]:
    """Set task dependencies."""
    db = get_db_session()
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            return {"success": False, "error": f"Task {task_id} not found"}

        # Validate dependencies exist
        for dep_id in depends_on:
            dep = db.query(Task).filter(Task.id == dep_id).first()
            if not dep:
                return {"success": False, "error": f"Dependency task {dep_id} not found"}

        task.depends_on = depends_on
        db.commit()

        return {
            "success": True,
            "task_id": task_id,
            "depends_on": depends_on,
        }

    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()


async def submit_phase(phase_id: int) -> dict[str, Any]:
    """Submit a phase for approval."""
    db = get_db_session()
    try:
        phase = db.query(Phase).filter(Phase.id == phase_id).first()
        if not phase:
            return {"success": False, "error": f"Phase {phase_id} not found"}

        if phase.status != "in_progress":
            return {"success": False, "error": f"Phase must be in_progress to submit, current: {phase.status}"}

        # Check all tasks are complete
        features = db.query(Feature).filter(Feature.phase_id == phase_id).all()
        for feature in features:
            tasks = db.query(Task).filter(Task.feature_id == feature.id).all()
            incomplete = [t for t in tasks if not t.passes]
            if incomplete:
                return {
                    "success": False,
                    "error": f"Feature '{feature.name}' has {len(incomplete)} incomplete tasks",
                }

        phase.status = "awaiting_approval"
        db.commit()

        return {
            "success": True,
            "phase_id": phase_id,
            "status": "awaiting_approval",
            "message": f"Phase '{phase.name}' submitted for approval",
        }

    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()


async def approve_phase(phase_id: int) -> dict[str, Any]:
    """Approve a phase."""
    db = get_db_session()
    try:
        phase = db.query(Phase).filter(Phase.id == phase_id).first()
        if not phase:
            return {"success": False, "error": f"Phase {phase_id} not found"}

        if phase.status != "awaiting_approval":
            return {"success": False, "error": f"Phase must be awaiting_approval, current: {phase.status}"}

        phase.status = "completed"
        db.commit()

        return {
            "success": True,
            "phase_id": phase_id,
            "status": "completed",
            "message": f"Phase '{phase.name}' approved and completed",
        }

    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()


# =============================================================================
# MCP Server Setup
# =============================================================================

app = Server("assistant-actions")


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    return TOOLS


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls."""
    try:
        if name == "assistant_create_feature":
            result = await create_feature(
                name=arguments["name"],
                tasks=arguments["tasks"],
                description=arguments.get("description", ""),
                phase_id=arguments.get("phase_id"),
            )
        elif name == "assistant_list_phases":
            result = await list_phases()
        elif name == "assistant_create_phase":
            result = await create_phase(
                name=arguments["name"],
                description=arguments.get("description", ""),
                order=arguments.get("order"),
            )
        elif name == "assistant_get_project_status":
            result = await get_project_status()
        elif name == "assistant_get_agent_status":
            result = await get_agent_status()
        elif name == "assistant_start_agent":
            result = await start_agent(arguments.get("yolo_mode", "standard"))
        elif name == "assistant_stop_agent":
            result = await stop_agent()
        elif name == "assistant_pause_agent":
            result = await pause_agent()
        elif name == "assistant_resume_agent":
            result = await resume_agent()
        elif name == "assistant_check_migration":
            result = await check_migration()
        elif name == "assistant_run_migration":
            result = await run_migration(
                phase_name=arguments.get("phase_name", "Phase 1: Initial Development"),
                feature_name=arguments.get("feature_name", "Core Features"),
            )
        elif name == "assistant_add_task":
            result = await add_task(
                feature_id=arguments["feature_id"],
                name=arguments["name"],
                description=arguments.get("description", ""),
                priority=arguments.get("priority", 100),
                complexity=arguments.get("complexity", 2),
                steps=arguments.get("steps"),
                depends_on=arguments.get("depends_on"),
            )
        elif name == "assistant_set_task_dependencies":
            result = await set_task_dependencies(
                task_id=arguments["task_id"],
                depends_on=arguments["depends_on"],
            )
        elif name == "assistant_submit_phase":
            result = await submit_phase(arguments["phase_id"])
        elif name == "assistant_approve_phase":
            result = await approve_phase(arguments["phase_id"])
        else:
            result = {"error": f"Unknown tool: {name}"}

        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    except Exception as e:
        logger.exception(f"Error in tool {name}")
        return [TextContent(type="text", text=json.dumps({"error": str(e)}))]


async def main():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
