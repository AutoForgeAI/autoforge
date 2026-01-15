# Autocoder Enhancement Plan

## Overview

This document outlines a comprehensive redesign of the Autocoder system to support:

### Core Architecture Changes
1. **Hierarchical structure**: Projects → Phases → Features → Tasks
2. **Renamed terminology**: "Features" become "Tasks", new "Features" concept added
3. **Phase-based workflows** with approval gates
4. **Drill-down UI** for project navigation
5. **Usage monitoring** with smart task prioritization

### Multi-Agent System
6. **Three+ Agent Architecture**: Architect, Initializer, Coding, Reviewer, Testing agents
7. **Agent Orchestration**: Message queue, shared context, intelligent routing
8. **Parallel Execution**: Independent features run on separate agents

### Advanced Features
9. **Task Dependencies**: `depends_on` relationships, dependency graphs, blocked task detection
10. **YOLO Mode Enhancements**: YOLO+Review, Parallel YOLO, Staged YOLO modes
11. **Enhanced MCP Tools**: Dependency management, orchestration, agent coordination

---

## 1. New Terminology & Hierarchy

### Current Model (Flat)
```
Project
  └── Features (flat list, 200+ items)
```

### Proposed Model (Hierarchical)
```
Project
  └── Phases (major milestones)
        └── Features (major work items requiring spec)
              └── Tasks (actionable items the agent works on)
```

### Terminology Changes

| Old Term | New Term | Description |
|----------|----------|-------------|
| Feature | **Task** | Small, actionable item the agent completes |
| (new) | **Feature** | Major work item that triggers spec creation |
| (new) | **Phase** | Collection of features representing a milestone |

---

## 2. New Database Schema

### File: `api/database.py`

```python
from sqlalchemy import Boolean, Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.types import JSON
from datetime import datetime

Base = declarative_base()


class Phase(Base):
    """Phase represents a major milestone in the project."""

    __tablename__ = "phases"

    id = Column(Integer, primary_key=True, index=True)
    project_name = Column(String(255), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    order = Column(Integer, nullable=False, default=0)  # Sort order
    status = Column(String(50), default="pending")  # pending, in_progress, awaiting_approval, completed
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    features = relationship("Feature", back_populates="phase", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "project_name": self.project_name,
            "name": self.name,
            "description": self.description,
            "order": self.order,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "feature_count": len(self.features) if self.features else 0,
        }


class Feature(Base):
    """Feature represents a major work item requiring spec creation."""

    __tablename__ = "features"

    id = Column(Integer, primary_key=True, index=True)
    phase_id = Column(Integer, ForeignKey("phases.id"), nullable=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    spec = Column(Text, nullable=True)  # Generated spec for this feature
    status = Column(String(50), default="pending")  # pending, speccing, ready, in_progress, completed
    priority = Column(Integer, default=0)
    agent_id = Column(String(100), nullable=True)  # Which agent is assigned
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    phase = relationship("Phase", back_populates="features")
    tasks = relationship("Task", back_populates="feature", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "phase_id": self.phase_id,
            "name": self.name,
            "description": self.description,
            "spec": self.spec,
            "status": self.status,
            "priority": self.priority,
            "agent_id": self.agent_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "task_count": len(self.tasks) if self.tasks else 0,
            "tasks_completed": sum(1 for t in self.tasks if t.passes) if self.tasks else 0,
        }


class Task(Base):
    """Task represents an actionable item the agent works on (formerly 'Feature')."""

    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    feature_id = Column(Integer, ForeignKey("features.id"), nullable=True, index=True)
    priority = Column(Integer, nullable=False, default=999, index=True)
    category = Column(String(100), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    steps = Column(JSON, nullable=False)  # Stored as JSON array
    passes = Column(Boolean, default=False, index=True)
    in_progress = Column(Boolean, default=False, index=True)
    estimated_complexity = Column(Integer, default=1)  # 1-5 scale for usage estimation

    # Relationships
    feature = relationship("Feature", back_populates="tasks")

    def to_dict(self):
        return {
            "id": self.id,
            "feature_id": self.feature_id,
            "priority": self.priority,
            "category": self.category,
            "name": self.name,
            "description": self.description,
            "steps": self.steps,
            "passes": self.passes,
            "in_progress": self.in_progress,
            "estimated_complexity": self.estimated_complexity,
        }


class UsageLog(Base):
    """Track Claude API usage for monitoring and smart scheduling."""

    __tablename__ = "usage_logs"

    id = Column(Integer, primary_key=True, index=True)
    project_name = Column(String(255), nullable=False, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    cache_read_tokens = Column(Integer, default=0)
    cache_write_tokens = Column(Integer, default=0)
    task_id = Column(Integer, nullable=True)  # Which task triggered this
    session_id = Column(String(100), nullable=True)  # Agent session

    def to_dict(self):
        return {
            "id": self.id,
            "project_name": self.project_name,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cache_read_tokens": self.cache_read_tokens,
            "cache_write_tokens": self.cache_write_tokens,
            "total_tokens": self.input_tokens + self.output_tokens,
            "task_id": self.task_id,
        }
```

---

## 3. Phase-Based Workflow

### Phase Statuses

```
pending → in_progress → awaiting_approval → completed
    ↑                         │
    └─────── rejected ────────┘
```

### Workflow Description

1. **pending**: Phase not started yet
2. **in_progress**: Agent actively working on tasks in this phase
3. **awaiting_approval**: All tasks complete, waiting for user to review
4. **completed**: User approved, ready to move to next phase

### Agent Notification System

When a phase completes, the agent will:

```python
# In agent.py - after marking last task passing
def check_phase_completion(project_dir: Path, feature_id: int):
    """Check if completing this task finishes a phase."""
    # Get the feature and its phase
    feature = get_feature(feature_id)
    if not feature.phase_id:
        return

    phase = get_phase(feature.phase_id)

    # Check if all tasks in this phase's features are complete
    all_complete = all(
        task.passes
        for f in phase.features
        for task in f.tasks
    )

    if all_complete:
        # Update phase status
        phase.status = "awaiting_approval"

        # Notify user
        print(f"\n{'='*60}")
        print(f"PHASE COMPLETE: {phase.name}")
        print(f"{'='*60}")
        print(f"All tasks in this phase have been completed.")
        print(f"Please review and approve to continue to the next phase.")
        print(f"{'='*60}\n")

        # Send webhook notification if configured
        notify_phase_complete(phase)

        # Agent should pause and wait for approval
        return "pause_for_approval"
```

---

## 4. Drill-Down UI Architecture

### Navigation Structure

```
┌─────────────────────────────────────────────────────────────────┐
│  AUTOCODER                                    [Usage: 75%] ⚡   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Breadcrumb: Projects > MyApp > Phase 1: Foundation > Auth      │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                                                         │   │
│  │   CURRENT VIEW (contextual based on drill level)        │   │
│  │                                                         │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### View Levels

#### Level 1: Projects List
```
┌────────────────────────────────────────────────────────────┐
│ MY PROJECTS                                    [+ New]     │
├────────────────────────────────────────────────────────────┤
│ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐        │
│ │ E-Commerce   │ │ Blog Engine  │ │ Dashboard    │        │
│ │              │ │              │ │              │        │
│ │ Phase 2/4    │ │ Phase 1/3    │ │ Completed    │        │
│ │ ████████░░   │ │ ██░░░░░░░░   │ │ ██████████   │        │
│ │ 45/60 tasks  │ │ 12/80 tasks  │ │ 120/120      │        │
│ │              │ │              │ │              │        │
│ │ [▶ Resume]   │ │ [▶ Start]    │ │ [View]       │        │
│ └──────────────┘ └──────────────┘ └──────────────┘        │
└────────────────────────────────────────────────────────────┘
```

#### Level 2: Project Phases (Timeline View)
```
┌────────────────────────────────────────────────────────────────┐
│ E-COMMERCE APP                                 [+ Add Phase]   │
│ ← Back to Projects                                             │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  Phase 1          Phase 2          Phase 3          Phase 4    │
│  Foundation       Core Features    Polish            Launch    │
│  ✓ COMPLETED      ▶ IN PROGRESS   ○ PENDING         ○ PENDING │
│                                                                │
│  ┌─────────┐      ┌─────────┐      ┌─────────┐      ┌───────┐ │
│  │ Auth    │      │ Cart    │      │ Search  │      │ Deploy│ │
│  │ ✓ Done  │      │ ▶ 3/10  │      │ ○ 0/8   │      │ ○ 0/5 │ │
│  ├─────────┤      ├─────────┤      ├─────────┤      ├───────┤ │
│  │ Users   │      │ Payment │      │ Reviews │      │ Docs  │ │
│  │ ✓ Done  │      │ ○ 0/12  │      │ ○ 0/6   │      │ ○ 0/3 │ │
│  ├─────────┤      ├─────────┤      └─────────┘      └───────┘ │
│  │ Products│      │ Orders  │                                  │
│  │ ✓ Done  │      │ ○ 0/15  │                                  │
│  └─────────┘      └─────────┘                                  │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

#### Level 3: Feature Tasks (Kanban View)
```
┌────────────────────────────────────────────────────────────────┐
│ FEATURE: Shopping Cart                         [+ Add Task]    │
│ ← Phase 2: Core Features                                       │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  PENDING (5)         IN PROGRESS (2)        DONE (3)          │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐       │
│  │ Add to cart  │   │ Cart persist │   │ Cart UI      │       │
│  │ button       │   │ to storage   │   │ component    │       │
│  │              │   │              │   │              │       │
│  │ Steps: 4     │   │ Steps: 6     │   │ ✓ Passed     │       │
│  └──────────────┘   └──────────────┘   └──────────────┘       │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐       │
│  │ Remove item  │   │ Quantity     │   │ Cart icon    │       │
│  │              │   │ update       │   │ badge        │       │
│  │ Steps: 3     │   │ Steps: 5     │   │ ✓ Passed     │       │
│  └──────────────┘   └──────────────┘   └──────────────┘       │
│  ...               ...                  ...                    │
└────────────────────────────────────────────────────────────────┘
```

### New React Components

```
ui/src/components/
├── navigation/
│   ├── Breadcrumb.tsx           # Navigation breadcrumb
│   └── DrillDownContainer.tsx   # Container managing navigation state
│
├── projects/
│   ├── ProjectGrid.tsx          # Level 1: Project cards
│   └── ProjectCard.tsx          # Individual project summary
│
├── phases/
│   ├── PhaseTimeline.tsx        # Level 2: Phase timeline view
│   ├── PhaseCard.tsx            # Individual phase card
│   ├── PhaseApprovalModal.tsx   # Approval dialog
│   └── AddPhaseModal.tsx        # Create new phase
│
├── features/
│   ├── FeatureList.tsx          # Features within a phase
│   ├── FeatureCard.tsx          # Individual feature card
│   ├── AddFeatureModal.tsx      # Create new feature (triggers spec)
│   └── FeatureSpecChat.tsx      # Spec creation for new feature
│
├── tasks/
│   ├── TaskKanban.tsx           # Level 3: Task kanban board
│   ├── TaskCard.tsx             # Individual task card
│   ├── TaskModal.tsx            # Task details
│   └── AddTaskForm.tsx          # Quick add task
│
└── usage/
    ├── UsageDashboard.tsx       # Usage monitoring panel
    ├── UsageChart.tsx           # Usage over time chart
    └── UsageWarning.tsx         # Low usage alert banner
```

---

## 5. Usage Monitoring System

### API Integration

The Claude API returns usage information in responses. We need to capture this:

```python
# In agent.py - after each API call
async def track_usage(response, project_name: str, task_id: int = None):
    """Track API usage from Claude response."""
    usage = response.usage

    log = UsageLog(
        project_name=project_name,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        cache_read_tokens=getattr(usage, 'cache_read_input_tokens', 0),
        cache_write_tokens=getattr(usage, 'cache_creation_input_tokens', 0),
        task_id=task_id,
        session_id=current_session_id,
    )

    db.add(log)
    db.commit()
```

### Usage Dashboard UI

```
┌────────────────────────────────────────────────────────────────┐
│ USAGE MONITOR                                                  │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  Current Period: Jan 1 - Jan 31, 2025                         │
│                                                                │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │                    TOKEN USAGE                          │  │
│  │                                                         │  │
│  │  ████████████████████████░░░░░░░░░░  75% Used          │  │
│  │  750,000 / 1,000,000 tokens                            │  │
│  │                                                         │  │
│  │  ⚠️ At current rate, limit reached in ~3 days          │  │
│  └─────────────────────────────────────────────────────────┘  │
│                                                                │
│  Today's Usage: 45,230 tokens                                 │
│  Average/Day:   32,150 tokens                                 │
│  Remaining:     250,000 tokens                                │
│                                                                │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │  USAGE BY PROJECT                                       │  │
│  │                                                         │  │
│  │  E-Commerce    ████████████████  450,000 (60%)         │  │
│  │  Blog Engine   ████████          200,000 (27%)         │  │
│  │  Dashboard     ████              100,000 (13%)         │  │
│  └─────────────────────────────────────────────────────────┘  │
│                                                                │
│  [📊 Detailed Report]  [⚙️ Settings]                          │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

### Smart Task Prioritization

```python
# In agent.py - task selection logic
class SmartTaskScheduler:
    """Schedules tasks based on usage and complexity."""

    THRESHOLDS = {
        "critical": 0.05,   # 5% remaining - stop new tasks
        "low": 0.10,        # 10% remaining - only simple tasks
        "moderate": 0.25,   # 25% remaining - prioritize completion
    }

    def get_next_task(self, project_dir: Path) -> Task | None:
        """Get the next task considering usage constraints."""
        usage_remaining = self.get_remaining_usage_percentage()

        if usage_remaining <= self.THRESHOLDS["critical"]:
            # Don't start any new tasks - let current ones complete
            logger.warning(
                f"Usage critical ({usage_remaining:.1%}). "
                "Not starting new tasks."
            )
            return None

        if usage_remaining <= self.THRESHOLDS["low"]:
            # Only get simple tasks (complexity 1-2)
            return self._get_simple_task(project_dir)

        if usage_remaining <= self.THRESHOLDS["moderate"]:
            # Prioritize tasks that are close to completion
            # or that complete a feature/phase
            return self._get_completion_priority_task(project_dir)

        # Normal operation - get highest priority task
        return self._get_highest_priority_task(project_dir)

    def _get_simple_task(self, project_dir: Path) -> Task | None:
        """Get a low-complexity task."""
        return db.query(Task).filter(
            Task.passes == False,
            Task.in_progress == False,
            Task.estimated_complexity <= 2,
        ).order_by(Task.priority).first()

    def _get_completion_priority_task(self, project_dir: Path) -> Task | None:
        """Get a task that would complete a feature or phase."""
        # Find features with only 1-2 tasks remaining
        for feature in db.query(Feature).filter(Feature.status == "in_progress"):
            remaining = [t for t in feature.tasks if not t.passes]
            if len(remaining) <= 2:
                # Prioritize completing this feature
                return remaining[0] if remaining else None

        # Fall back to normal priority
        return self._get_highest_priority_task(project_dir)
```

### Usage Settings

```python
# New config in server/config.py
USAGE_CONFIG = {
    "monthly_limit": 1_000_000,  # Token limit (can be set by user)
    "warn_at_percentage": 0.20,  # Show warning at 20% remaining
    "pause_at_percentage": 0.05, # Auto-pause at 5% remaining
    "reset_day": 1,              # Day of month when usage resets
    "track_by": "project",       # "project" or "global"
}
```

---

## 6. New API Endpoints

### Phases API

```
GET    /api/projects/{name}/phases              # List all phases
POST   /api/projects/{name}/phases              # Create phase
GET    /api/projects/{name}/phases/{id}         # Get phase details
PUT    /api/projects/{name}/phases/{id}         # Update phase
DELETE /api/projects/{name}/phases/{id}         # Delete phase
POST   /api/projects/{name}/phases/{id}/approve # Approve phase completion
POST   /api/projects/{name}/phases/{id}/reject  # Reject, return to in_progress
```

### Features API (Enhanced)

```
GET    /api/projects/{name}/features                    # List all features
GET    /api/projects/{name}/phases/{phase_id}/features  # Features in phase
POST   /api/projects/{name}/features                    # Create feature (triggers spec)
GET    /api/projects/{name}/features/{id}               # Get feature details
PUT    /api/projects/{name}/features/{id}               # Update feature
DELETE /api/projects/{name}/features/{id}               # Delete feature
POST   /api/projects/{name}/features/{id}/assign        # Assign to agent
```

### Tasks API (Renamed from Features)

```
GET    /api/projects/{name}/tasks                       # List all tasks
GET    /api/projects/{name}/features/{feature_id}/tasks # Tasks in feature
POST   /api/projects/{name}/tasks                       # Create task (simple add)
GET    /api/projects/{name}/tasks/{id}                  # Get task details
PATCH  /api/projects/{name}/tasks/{id}                  # Update task
DELETE /api/projects/{name}/tasks/{id}                  # Delete task
PATCH  /api/projects/{name}/tasks/{id}/skip             # Skip task
```

### Usage API

```
GET    /api/usage                              # Global usage stats
GET    /api/usage/projects/{name}              # Project-specific usage
GET    /api/usage/history                      # Usage over time
GET    /api/usage/settings                     # Get usage settings
PUT    /api/usage/settings                     # Update usage settings
```

---

## 7. New MCP Tools

### Phase Management Tools

```python
@server.tool()
async def phase_get_current() -> dict:
    """Get the currently active phase."""

@server.tool()
async def phase_mark_complete(phase_id: int) -> dict:
    """Mark a phase as ready for approval."""

@server.tool()
async def phase_check_status(phase_id: int) -> dict:
    """Check if all features in a phase are complete."""
```

### Feature Management Tools

```python
@server.tool()
async def feature_create(
    phase_id: int,
    name: str,
    description: str,
) -> dict:
    """Create a new feature (triggers spec creation workflow)."""

@server.tool()
async def feature_get_spec(feature_id: int) -> dict:
    """Get the spec for a feature."""

@server.tool()
async def feature_create_tasks(
    feature_id: int,
    tasks: list[dict],
) -> dict:
    """Create tasks for a feature (used after spec generation)."""
```

### Task Management Tools (Renamed)

```python
@server.tool()
async def task_get_next() -> dict:
    """Get the highest priority pending task."""

@server.tool()
async def task_mark_passing(task_id: int) -> dict:
    """Mark a task as complete/passing."""

@server.tool()
async def task_get_for_regression(limit: int = 3) -> list[dict]:
    """Get random passing tasks for regression testing."""
```

### Usage Tools

```python
@server.tool()
async def usage_get_remaining() -> dict:
    """Get remaining usage for current period."""

@server.tool()
async def usage_should_continue() -> dict:
    """Check if agent should continue or pause for usage limits."""
```

---

## 8. Migration Strategy

### Database Migration

```python
# api/migrations/001_add_phases_and_rename.py

def upgrade(engine):
    """Migrate from flat features to hierarchical structure."""

    # 1. Create new tables
    create_table("phases")
    create_table("usage_logs")

    # 2. Rename features table to tasks
    rename_table("features", "tasks")

    # 3. Create new features table
    create_table("features")

    # 4. Add foreign keys to tasks
    add_column("tasks", "feature_id", Integer, nullable=True)

    # 5. Create default phase and feature for existing tasks
    create_default_phase_and_feature()

def create_default_phase_and_feature():
    """Wrap existing tasks in a default feature and phase."""

    # Create "Phase 1: Initial Development" for each project
    # Create "Core Features" feature within it
    # Link all existing tasks to this feature
    pass
```

### UI Migration

The React app can be updated incrementally:

1. **Phase 1**: Add new types and API client methods
2. **Phase 2**: Add navigation components (Breadcrumb, DrillDownContainer)
3. **Phase 3**: Build new phase/feature views
4. **Phase 4**: Rename components (Feature → Task)
5. **Phase 5**: Add usage monitoring
6. **Phase 6**: Wire everything together

---

## 9. Multi-Agent Support

### Agent Assignment

Features can be assigned to different agents:

```python
class AgentManager:
    """Manages multiple agents working on a project."""

    def __init__(self, project_name: str):
        self.project_name = project_name
        self.agents: dict[str, AgentProcessManager] = {}

    def assign_feature(self, feature_id: int, agent_id: str = None):
        """Assign a feature to an agent."""
        if agent_id is None:
            agent_id = self._create_new_agent()

        feature = get_feature(feature_id)
        feature.agent_id = agent_id

        # Start the agent if not running
        if agent_id not in self.agents:
            self.agents[agent_id] = AgentProcessManager(
                project_name=self.project_name,
                project_dir=self.project_dir,
                agent_id=agent_id,
            )

    def can_run_independently(self, feature: Feature) -> bool:
        """Check if a feature can run on its own agent."""
        # Features in the same phase might have dependencies
        # Features in different phases should be sequential
        # Features with no task overlap can run in parallel
        pass
```

### Agent Communication

```python
# Agents communicate via shared database
# Each agent has its own scope (feature_id filter)

# In task selection:
def get_next_task_for_agent(agent_id: str) -> Task | None:
    """Get next task scoped to this agent's assigned features."""
    assigned_features = db.query(Feature).filter(
        Feature.agent_id == agent_id
    ).all()

    feature_ids = [f.id for f in assigned_features]

    return db.query(Task).filter(
        Task.feature_id.in_(feature_ids),
        Task.passes == False,
        Task.in_progress == False,
    ).order_by(Task.priority).first()
```

---

## 10. Three+ Agent Architecture

### Agent Types

The system expands from 2 agents to 5+ specialized agents:

```
┌─────────────────────────────────────────────────────────────────────┐
│                     MULTI-AGENT ARCHITECTURE                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────┐                                                   │
│  │  ARCHITECT   │  Session 0: Designs system architecture           │
│  │    AGENT     │  - Creates file/folder structure                  │
│  │              │  - Defines API contracts                          │
│  │              │  - Plans component relationships                  │
│  └──────┬───────┘                                                   │
│         ▼                                                            │
│  ┌──────────────┐                                                   │
│  │ INITIALIZER  │  Session 1: Creates tasks from spec               │
│  │    AGENT     │  - Parses app_spec.txt                            │
│  │              │  - Generates 200+ detailed tasks                  │
│  │              │  - Assigns priorities and categories              │
│  └──────┬───────┘                                                   │
│         ▼                                                            │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐          │
│  │   CODING     │    │   CODING     │    │   CODING     │          │
│  │   AGENT 1    │    │   AGENT 2    │    │   AGENT N    │          │
│  │              │    │              │    │              │          │
│  │  Feature A   │    │  Feature B   │    │  Feature N   │          │
│  │  (Auth)      │    │  (Cart)      │    │  (Search)    │          │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘          │
│         │                   │                   │                   │
│         └───────────────────┼───────────────────┘                   │
│                             ▼                                        │
│  ┌──────────────┐    ┌──────────────┐                               │
│  │   REVIEWER   │    │   TESTING    │                               │
│  │    AGENT     │    │    AGENT     │                               │
│  │              │    │              │                               │
│  │ Code quality │    │ Integration  │                               │
│  │ Refactoring  │    │ E2E tests    │                               │
│  │ Security     │    │ Regression   │                               │
│  └──────────────┘    └──────────────┘                               │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Agent Prompts

New prompt templates in `.claude/templates/`:

```
templates/
├── architect_prompt.template.md      # System design, file structure
├── initializer_prompt.template.md    # Task creation from spec
├── coding_prompt.template.md         # Feature implementation
├── coding_prompt_yolo.template.md    # YOLO mode implementation
├── reviewer_prompt.template.md       # Code review and refactoring
└── testing_prompt.template.md        # Integration/E2E testing
```

### Agent Selection Logic

```python
# In agent.py - enhanced agent selection
def determine_agent_type(project_dir: Path) -> str:
    """Determine which agent to run based on project state."""

    # Check for architecture files
    if not has_architecture(project_dir):
        return "architect"

    # Check for tasks
    if not has_tasks(project_dir):
        return "initializer"

    # Check for pending reviews
    if has_pending_reviews(project_dir):
        return "reviewer"

    # Check for pending integration tests
    if phase_needs_testing(project_dir):
        return "testing"

    # Default: coding agent
    return "coding"


def has_architecture(project_dir: Path) -> bool:
    """Check if architecture has been defined."""
    arch_file = project_dir / "architecture.md"
    return arch_file.exists() and arch_file.stat().st_size > 0


def has_pending_reviews(project_dir: Path) -> bool:
    """Check if any completed tasks need review."""
    return db.query(Task).filter(
        Task.passes == True,
        Task.reviewed == False,
    ).count() > 0


def phase_needs_testing(project_dir: Path) -> bool:
    """Check if current phase needs integration testing."""
    phase = get_current_phase(project_dir)
    return (
        phase.status == "awaiting_testing" and
        all(t.passes for f in phase.features for t in f.tasks)
    )
```

### Architect Agent

The Architect agent runs first to establish project structure:

```python
# architect_prompt.template.md responsibilities:
ARCHITECT_TASKS = [
    "Analyze app_spec.txt requirements",
    "Design folder/file structure",
    "Define API contracts and interfaces",
    "Create architecture.md documentation",
    "Identify component dependencies",
    "Plan database schema",
    "Define shared types/interfaces",
]

# Output: architecture.md with:
ARCHITECTURE_OUTPUT = {
    "folder_structure": "Tree of directories and files",
    "api_contracts": "Interface definitions for each component",
    "component_diagram": "How components interact",
    "database_schema": "Tables and relationships",
    "dependency_graph": "What depends on what",
    "implementation_order": "Suggested build sequence",
}
```

### Reviewer Agent

The Reviewer agent checks completed work:

```python
# reviewer_prompt.template.md responsibilities:
REVIEWER_TASKS = [
    "Review recently completed tasks",
    "Check code quality and patterns",
    "Identify refactoring opportunities",
    "Verify security best practices",
    "Ensure consistency with architecture",
    "Suggest performance improvements",
]

# New database fields for review tracking
class Task(Base):
    # ... existing fields ...
    reviewed = Column(Boolean, default=False, index=True)
    review_notes = Column(Text, nullable=True)
    review_score = Column(Integer, nullable=True)  # 1-5 quality score
```

### Testing Agent

The Testing agent runs integration tests:

```python
# testing_prompt.template.md responsibilities:
TESTING_TASKS = [
    "Run integration tests for completed features",
    "Create E2E test scenarios",
    "Verify feature interactions",
    "Test edge cases and error handling",
    "Validate API contracts",
    "Check regression across features",
]

# Triggered when phase completes all coding tasks
```

---

## 11. Task Dependencies

### Database Schema Addition

```python
class Task(Base):
    # ... existing fields ...

    # Dependency tracking
    depends_on = Column(JSON, nullable=True)  # Array of task IDs
    blocks = Column(JSON, nullable=True)      # Computed: tasks blocked by this

    # Dependency status
    is_blocked = Column(Boolean, default=False, index=True)
    blocked_reason = Column(String(255), nullable=True)

    def to_dict(self):
        return {
            # ... existing fields ...
            "depends_on": self.depends_on or [],
            "blocks": self.blocks or [],
            "is_blocked": self.is_blocked,
            "blocked_reason": self.blocked_reason,
        }
```

### Dependency Management MCP Tools

```python
@server.tool()
async def task_set_dependencies(
    task_id: int,
    depends_on: list[int],
) -> dict:
    """Set dependencies for a task."""
    task = get_task(task_id)
    task.depends_on = depends_on

    # Update blocked status
    update_blocked_status(task)

    # Update 'blocks' field on dependent tasks
    for dep_id in depends_on:
        dep_task = get_task(dep_id)
        blocks = dep_task.blocks or []
        if task_id not in blocks:
            blocks.append(task_id)
            dep_task.blocks = blocks

    db.commit()
    return {"success": True, "task": task.to_dict()}


@server.tool()
async def task_get_blocked() -> list[dict]:
    """Get all tasks that are currently blocked by dependencies."""
    blocked = db.query(Task).filter(
        Task.is_blocked == True,
        Task.passes == False,
    ).all()
    return [t.to_dict() for t in blocked]


@server.tool()
async def task_get_ready() -> list[dict]:
    """Get tasks that are ready to work on (dependencies satisfied)."""
    ready = db.query(Task).filter(
        Task.is_blocked == False,
        Task.passes == False,
        Task.in_progress == False,
    ).order_by(Task.priority).all()
    return [t.to_dict() for t in ready]


@server.tool()
async def task_get_dependency_graph(feature_id: int = None) -> dict:
    """Get the full dependency graph for visualization."""
    if feature_id:
        tasks = db.query(Task).filter(Task.feature_id == feature_id).all()
    else:
        tasks = db.query(Task).all()

    nodes = []
    edges = []

    for task in tasks:
        nodes.append({
            "id": task.id,
            "name": task.name,
            "status": "done" if task.passes else ("blocked" if task.is_blocked else "pending"),
        })

        for dep_id in (task.depends_on or []):
            edges.append({
                "from": dep_id,
                "to": task.id,
            })

    return {"nodes": nodes, "edges": edges}


def update_blocked_status(task: Task):
    """Update whether a task is blocked based on its dependencies."""
    if not task.depends_on:
        task.is_blocked = False
        task.blocked_reason = None
        return

    # Check if all dependencies are complete
    deps = db.query(Task).filter(Task.id.in_(task.depends_on)).all()
    incomplete = [d for d in deps if not d.passes]

    if incomplete:
        task.is_blocked = True
        task.blocked_reason = f"Waiting on: {', '.join(d.name for d in incomplete)}"
    else:
        task.is_blocked = False
        task.blocked_reason = None


def propagate_completion(task_id: int):
    """When a task completes, unblock dependent tasks."""
    task = get_task(task_id)

    for blocked_id in (task.blocks or []):
        blocked_task = get_task(blocked_id)
        update_blocked_status(blocked_task)

    db.commit()
```

### Dependency UI Components

```typescript
// ui/src/components/tasks/DependencyGraph.tsx
interface DependencyGraphProps {
  featureId?: number;
  onTaskClick?: (taskId: number) => void;
}

// Visual representation of task dependencies
// Uses a DAG (Directed Acyclic Graph) layout
// Color-coded by status: pending (yellow), blocked (red), done (green)
// Click on node to view task details
// Edges show dependency direction
```

### Automatic Dependency Detection

The Initializer agent can suggest dependencies:

```python
# In initializer_prompt.template.md
DEPENDENCY_HINTS = """
When creating tasks, identify dependencies:
- Database schema tasks must complete before API endpoints
- API endpoints must complete before frontend components
- Shared utilities must complete before features using them
- Authentication must complete before protected features

Use task_set_dependencies() to establish these relationships.
"""
```

---

## 12. YOLO Mode Enhancements

### Current YOLO Mode

YOLO mode skips testing for rapid prototyping:
- No Playwright MCP server
- No regression testing via `task_get_for_regression`
- Tasks marked passing after lint/type-check

### New YOLO Variants

#### YOLO+Review Mode

Fast iteration with code review:

```python
# coding_prompt_yolo_review.template.md
YOLO_REVIEW_MODE = {
    "skip_browser_testing": True,
    "skip_regression": True,
    "enable_review": True,  # NEW: Reviewer agent runs periodically
    "review_frequency": 5,   # Review every 5 completed tasks
}
```

```python
def should_run_review(project_dir: Path) -> bool:
    """Check if it's time for a review in YOLO+Review mode."""
    if not is_yolo_review_mode():
        return False

    # Count tasks since last review
    last_review = get_last_review_timestamp(project_dir)
    tasks_since = db.query(Task).filter(
        Task.passes == True,
        Task.completed_at > last_review,
    ).count()

    return tasks_since >= YOLO_REVIEW_MODE["review_frequency"]
```

#### Parallel YOLO Mode

Run multiple coding agents on independent features:

```python
# In server/services/parallel_agent_manager.py
class ParallelYoloManager:
    """Manage multiple YOLO agents working in parallel."""

    def __init__(self, project_name: str, max_agents: int = 3):
        self.project_name = project_name
        self.max_agents = max_agents
        self.agents: dict[str, AgentProcessManager] = {}

    def start(self):
        """Start parallel YOLO agents on independent features."""
        independent_features = self.get_independent_features()

        for i, feature in enumerate(independent_features[:self.max_agents]):
            agent_id = f"yolo-{i+1}"
            self.agents[agent_id] = AgentProcessManager(
                project_name=self.project_name,
                project_dir=self.project_dir,
                agent_id=agent_id,
                yolo_mode=True,
                feature_scope=feature.id,  # Only work on this feature
            )
            self.agents[agent_id].start()

    def get_independent_features(self) -> list[Feature]:
        """Get features that can run in parallel (no dependencies between them)."""
        features = db.query(Feature).filter(
            Feature.status == "ready",
        ).all()

        # Filter to features with no cross-dependencies
        independent = []
        for feature in features:
            task_ids = {t.id for t in feature.tasks}
            has_external_deps = any(
                dep_id not in task_ids
                for t in feature.tasks
                for dep_id in (t.depends_on or [])
            )
            if not has_external_deps:
                independent.append(feature)

        return independent
```

#### Staged YOLO Mode

YOLO for early phases, full testing for later phases:

```python
# In agent.py
def get_yolo_mode_for_phase(phase: Phase) -> str:
    """Determine YOLO mode based on phase."""

    phase_percentage = phase.order / total_phases

    if phase_percentage <= 0.5:
        # First 50% of phases: full YOLO
        return "yolo"
    elif phase_percentage <= 0.75:
        # 50-75%: YOLO with review
        return "yolo_review"
    else:
        # Final 25%: full testing
        return "standard"
```

### YOLO Mode UI Toggle

```typescript
// Enhanced YOLO mode selector in AgentControl.tsx
type YoloMode = 'off' | 'yolo' | 'yolo_review' | 'yolo_parallel' | 'yolo_staged';

interface YoloModeOption {
  value: YoloMode;
  label: string;
  description: string;
  icon: string;
}

const YOLO_OPTIONS: YoloModeOption[] = [
  { value: 'off', label: 'Standard', description: 'Full testing', icon: '🛡️' },
  { value: 'yolo', label: 'YOLO', description: 'Skip testing', icon: '⚡' },
  { value: 'yolo_review', label: 'YOLO+Review', description: 'Skip testing, add reviews', icon: '⚡👀' },
  { value: 'yolo_parallel', label: 'Parallel YOLO', description: 'Multiple agents', icon: '⚡⚡⚡' },
  { value: 'yolo_staged', label: 'Staged', description: 'YOLO early, test late', icon: '📈' },
];
```

---

## 13. Agent Orchestration System

### Orchestrator Service

Central coordinator for multi-agent workflows:

```python
# server/services/orchestrator.py
from enum import Enum
from dataclasses import dataclass
from typing import Optional
import asyncio


class AgentType(Enum):
    ARCHITECT = "architect"
    INITIALIZER = "initializer"
    CODING = "coding"
    REVIEWER = "reviewer"
    TESTING = "testing"


@dataclass
class AgentMessage:
    """Message passed between agents."""
    from_agent: str
    to_agent: str
    message_type: str  # "task_complete", "review_needed", "blocked", etc.
    payload: dict
    timestamp: datetime


class Orchestrator:
    """Coordinates multiple agents working on a project."""

    def __init__(self, project_name: str):
        self.project_name = project_name
        self.message_queue: asyncio.Queue[AgentMessage] = asyncio.Queue()
        self.agents: dict[str, AgentProcessManager] = {}
        self.running = False

    async def start(self):
        """Start the orchestrator loop."""
        self.running = True

        while self.running:
            # Determine what agents should be running
            needed_agents = self.determine_needed_agents()

            # Start/stop agents as needed
            await self.reconcile_agents(needed_agents)

            # Process any messages
            await self.process_messages()

            # Check for phase transitions
            await self.check_phase_transitions()

            await asyncio.sleep(1)

    def determine_needed_agents(self) -> list[tuple[AgentType, str]]:
        """Determine which agents should be running."""
        needed = []

        # Always need at most one architect (if architecture missing)
        if not has_architecture(self.project_dir):
            needed.append((AgentType.ARCHITECT, "architect-1"))
            return needed  # Only architect until it's done

        # Need initializer if no tasks
        if not has_tasks(self.project_dir):
            needed.append((AgentType.INITIALIZER, "initializer-1"))
            return needed

        # Can run multiple coding agents on independent features
        independent_features = self.get_assignable_features()
        for i, feature in enumerate(independent_features[:3]):  # Max 3
            if not feature.agent_id:
                needed.append((AgentType.CODING, f"coding-{feature.id}"))

        # Need reviewer periodically
        if self.should_run_review():
            needed.append((AgentType.REVIEWER, "reviewer-1"))

        # Need testing agent when phase awaits testing
        if self.phase_needs_testing():
            needed.append((AgentType.TESTING, "testing-1"))

        return needed

    async def reconcile_agents(self, needed: list[tuple[AgentType, str]]):
        """Start needed agents, stop unneeded ones."""
        needed_ids = {agent_id for _, agent_id in needed}

        # Stop agents that are no longer needed
        for agent_id in list(self.agents.keys()):
            if agent_id not in needed_ids:
                await self.stop_agent(agent_id)

        # Start agents that are needed but not running
        for agent_type, agent_id in needed:
            if agent_id not in self.agents:
                await self.start_agent(agent_type, agent_id)

    async def start_agent(self, agent_type: AgentType, agent_id: str):
        """Start a new agent."""
        manager = AgentProcessManager(
            project_name=self.project_name,
            project_dir=self.project_dir,
            agent_id=agent_id,
            agent_type=agent_type.value,
        )
        await manager.start()
        self.agents[agent_id] = manager

        # Send started message
        await self.broadcast_message(AgentMessage(
            from_agent="orchestrator",
            to_agent="*",
            message_type="agent_started",
            payload={"agent_id": agent_id, "type": agent_type.value},
            timestamp=datetime.utcnow(),
        ))

    async def process_messages(self):
        """Process pending messages between agents."""
        while not self.message_queue.empty():
            message = await self.message_queue.get()
            await self.route_message(message)

    async def route_message(self, message: AgentMessage):
        """Route a message to its destination."""
        if message.message_type == "task_complete":
            # Notify reviewer if review mode is on
            if self.is_review_mode():
                await self.queue_for_review(message.payload["task_id"])

            # Check if this unblocks other tasks
            propagate_completion(message.payload["task_id"])

        elif message.message_type == "feature_complete":
            # Check if phase is complete
            await self.check_phase_completion(message.payload["feature_id"])

        elif message.message_type == "review_complete":
            # Update task with review results
            await self.apply_review(message.payload)
```

### Shared Context Manager

Agents share context through a centralized system:

```python
# server/services/shared_context.py
class SharedContext:
    """Shared context accessible by all agents."""

    def __init__(self, project_name: str):
        self.project_name = project_name
        self.context_file = self.project_dir / ".agent_context.json"

    def get(self, key: str, default=None):
        """Get a value from shared context."""
        context = self._load()
        return context.get(key, default)

    def set(self, key: str, value):
        """Set a value in shared context."""
        context = self._load()
        context[key] = value
        context["_updated_at"] = datetime.utcnow().isoformat()
        self._save(context)

    def get_architecture(self) -> dict:
        """Get the project architecture defined by architect agent."""
        return self.get("architecture", {})

    def get_completed_interfaces(self) -> list[str]:
        """Get list of completed API interfaces."""
        return self.get("completed_interfaces", [])

    def add_completed_interface(self, interface_name: str):
        """Mark an interface as implemented."""
        interfaces = self.get_completed_interfaces()
        if interface_name not in interfaces:
            interfaces.append(interface_name)
            self.set("completed_interfaces", interfaces)

    def get_review_notes(self) -> list[dict]:
        """Get accumulated review notes."""
        return self.get("review_notes", [])

    def add_review_note(self, note: dict):
        """Add a review note from reviewer agent."""
        notes = self.get_review_notes()
        notes.append({
            **note,
            "timestamp": datetime.utcnow().isoformat(),
        })
        self.set("review_notes", notes)
```

### Message Queue for Agent Communication

```python
# In mcp_server/feature_mcp.py - new tools for agent communication
@server.tool()
async def agent_send_message(
    to_agent: str,
    message_type: str,
    payload: dict,
) -> dict:
    """Send a message to another agent or the orchestrator."""
    message = AgentMessage(
        from_agent=current_agent_id(),
        to_agent=to_agent,
        message_type=message_type,
        payload=payload,
        timestamp=datetime.utcnow(),
    )

    # Write to message queue (file-based for cross-process)
    queue_file = project_dir / ".agent_messages.jsonl"
    with open(queue_file, "a") as f:
        f.write(json.dumps(message.__dict__) + "\n")

    return {"success": True, "message_id": message.id}


@server.tool()
async def agent_get_messages() -> list[dict]:
    """Get messages addressed to this agent."""
    queue_file = project_dir / ".agent_messages.jsonl"

    messages = []
    my_id = current_agent_id()

    with open(queue_file, "r") as f:
        for line in f:
            msg = json.loads(line)
            if msg["to_agent"] in (my_id, "*"):
                messages.append(msg)

    return messages


@server.tool()
async def context_get(key: str) -> dict:
    """Get a value from shared context."""
    context = SharedContext(project_name)
    return {"key": key, "value": context.get(key)}


@server.tool()
async def context_set(key: str, value) -> dict:
    """Set a value in shared context."""
    context = SharedContext(project_name)
    context.set(key, value)
    return {"success": True}
```

---

## 14. Enhanced UI Components

### Multi-Agent Dashboard

```typescript
// ui/src/components/agents/AgentDashboard.tsx
interface AgentDashboardProps {
  projectName: string;
}

// Shows all running agents with:
// - Agent type and ID
// - Current task/feature
// - Status (running, paused, idle)
// - Token usage
// - Real-time logs (tabbed view)

interface AgentInfo {
  id: string;
  type: 'architect' | 'initializer' | 'coding' | 'reviewer' | 'testing';
  status: 'running' | 'paused' | 'idle' | 'crashed';
  currentTask: Task | null;
  currentFeature: Feature | null;
  tokensUsed: number;
  startedAt: string;
}
```

### Agent Timeline View

```typescript
// ui/src/components/agents/AgentTimeline.tsx
interface AgentTimelineProps {
  projectName: string;
  timeRange: 'hour' | 'day' | 'week';
}

// Visual timeline showing:
// - When each agent started/stopped
// - What tasks were completed
// - Handoffs between agents
// - Phase transitions
// - Review events

interface TimelineEvent {
  timestamp: string;
  type: 'agent_start' | 'agent_stop' | 'task_complete' | 'review' | 'phase_complete';
  agentId: string;
  details: Record<string, unknown>;
}
```

### Dependency Graph Visualization

```typescript
// ui/src/components/tasks/DependencyGraph.tsx
import { useCallback, useMemo } from 'react';
import ReactFlow, { Node, Edge, Controls, Background } from 'reactflow';

interface DependencyGraphProps {
  tasks: Task[];
  onTaskClick: (taskId: number) => void;
}

// Interactive DAG visualization:
// - Nodes = tasks (color by status)
// - Edges = dependencies
// - Zoom, pan, select
// - Click node to view task
// - Highlight critical path
// - Show blocked chains
```

### Enhanced Kanban with Dependencies

```typescript
// ui/src/components/tasks/TaskKanban.tsx
// Enhanced to show:
// - Dependency indicators (arrow icon if has deps)
// - Blocked badge (red "BLOCKED" tag)
// - Blocked reason tooltip
// - Dependency count (e.g., "2 deps")
// - Quick action to view dependency graph

interface TaskCardProps {
  task: Task;
  showDependencies?: boolean;
}

const TaskCard = ({ task, showDependencies }: TaskCardProps) => {
  return (
    <div className={cn(
      "task-card",
      task.is_blocked && "task-card-blocked"
    )}>
      <div className="task-header">
        <span className="task-name">{task.name}</span>
        {task.depends_on?.length > 0 && (
          <span className="dependency-badge">
            {task.depends_on.length} deps
          </span>
        )}
      </div>

      {task.is_blocked && (
        <div className="blocked-reason">
          🚫 {task.blocked_reason}
        </div>
      )}

      {/* ... rest of card ... */}
    </div>
  );
};
```

---

## 15. Implementation Roadmap

### Phase 1: Foundation (Database & Core)

#### Milestone 1.1: Database Schema
- [ ] Create new database models (Phase, enhanced Feature, Task, UsageLog)
- [ ] Add dependency fields (depends_on, blocks, is_blocked, blocked_reason)
- [ ] Add review fields (reviewed, review_notes, review_score)
- [ ] Write migration script for existing features.db data
- [ ] Preserve backward compatibility with existing projects

#### Milestone 1.2: API Layer
- [ ] Implement Phase CRUD endpoints
- [ ] Implement Feature CRUD endpoints (with spec trigger)
- [ ] Rename feature endpoints to task endpoints
- [ ] Add dependency management endpoints
- [ ] Add usage tracking endpoints

#### Milestone 1.3: MCP Tools Update
- [ ] Rename feature_* tools to task_*
- [ ] Add phase_* tools (get_current, mark_complete, check_status)
- [ ] Add dependency tools (task_set_dependencies, task_get_blocked, task_get_ready)
- [ ] Add task_get_dependency_graph for visualization

---

### Phase 2: Multi-Agent Architecture

#### Milestone 2.1: Agent Types
- [ ] Create architect_prompt.template.md
- [ ] Create reviewer_prompt.template.md
- [ ] Create testing_prompt.template.md
- [ ] Implement determine_agent_type() selection logic
- [ ] Add architecture.md detection

#### Milestone 2.2: Orchestrator Service
- [ ] Implement Orchestrator class in server/services/orchestrator.py
- [ ] Add agent lifecycle management (start/stop/reconcile)
- [ ] Implement message routing system
- [ ] Add phase transition detection

#### Milestone 2.3: Agent Communication
- [ ] Implement SharedContext manager
- [ ] Add agent_send_message MCP tool
- [ ] Add agent_get_messages MCP tool
- [ ] Add context_get/context_set MCP tools
- [ ] Create .agent_messages.jsonl queue

#### Milestone 2.4: Parallel Agents
- [ ] Implement ParallelYoloManager
- [ ] Add feature independence detection
- [ ] Support multiple coding agents per project
- [ ] Add agent scoping by feature_id

---

### Phase 3: Task Dependencies

#### Milestone 3.1: Dependency Logic
- [ ] Implement update_blocked_status() function
- [ ] Implement propagate_completion() function
- [ ] Add automatic dependency detection hints to initializer
- [ ] Update task selection to skip blocked tasks

#### Milestone 3.2: Dependency UI
- [ ] Add DependencyGraph.tsx component (using ReactFlow)
- [ ] Add blocked badge/indicators to TaskCard
- [ ] Add dependency count display
- [ ] Add dependency graph modal/view

---

### Phase 4: YOLO Mode Enhancements

#### Milestone 4.1: YOLO Variants
- [ ] Implement YOLO+Review mode
- [ ] Implement Parallel YOLO mode
- [ ] Implement Staged YOLO mode
- [ ] Add coding_prompt_yolo_review.template.md

#### Milestone 4.2: YOLO UI
- [ ] Create YOLO mode selector dropdown
- [ ] Add YOLO variant descriptions
- [ ] Show active YOLO mode in agent status
- [ ] Add staged mode phase indicator

---

### Phase 5: Phase Management & Workflow

#### Milestone 5.1: Phase Workflow
- [ ] Implement phase status transitions (pending → in_progress → awaiting_approval → completed)
- [ ] Add approval gate logic
- [ ] Add rejection handling (return to in_progress)
- [ ] Add phase completion notifications

#### Milestone 5.2: Phase UI
- [ ] Create PhaseTimeline.tsx component
- [ ] Create PhaseCard.tsx component
- [ ] Create PhaseApprovalModal.tsx
- [ ] Add phase status indicators

---

### Phase 6: Drill-Down UI Architecture

#### Milestone 6.1: Navigation
- [ ] Create Breadcrumb.tsx component
- [ ] Create DrillDownContainer.tsx with navigation state
- [ ] Implement URL-based navigation
- [ ] Add keyboard shortcuts for navigation

#### Milestone 6.2: View Levels
- [ ] Create ProjectGrid.tsx (Level 1)
- [ ] Create PhaseTimeline.tsx (Level 2)
- [ ] Enhance existing Kanban as TaskKanban.tsx (Level 3)
- [ ] Add FeatureList.tsx within phases

#### Milestone 6.3: Terminology Rename
- [ ] Rename Feature → Task in all UI components
- [ ] Add new Feature components for major work items
- [ ] Update all labels, tooltips, and messages
- [ ] Update API client types

---

### Phase 7: Usage Monitoring

#### Milestone 7.1: Usage Tracking
- [ ] Capture usage from Claude API responses
- [ ] Store in UsageLog table
- [ ] Track by project and session
- [ ] Calculate daily/weekly/monthly aggregates

#### Milestone 7.2: Smart Scheduling
- [ ] Implement SmartTaskScheduler class
- [ ] Add usage threshold logic (critical/low/moderate)
- [ ] Prioritize completion tasks when usage is low
- [ ] Add graceful wind-down at 5% remaining

#### Milestone 7.3: Usage UI
- [ ] Create UsageDashboard.tsx component
- [ ] Create UsageChart.tsx (usage over time)
- [ ] Create UsageWarning.tsx (alert banner)
- [ ] Add usage indicator to header
- [ ] Add per-project usage breakdown

---

### Phase 8: Enhanced UI Components

#### Milestone 8.1: Multi-Agent Dashboard
- [ ] Create AgentDashboard.tsx component
- [ ] Show all running agents with status
- [ ] Add tabbed log view per agent
- [ ] Show current task/feature per agent

#### Milestone 8.2: Agent Timeline
- [ ] Create AgentTimeline.tsx component
- [ ] Track agent start/stop events
- [ ] Show task completion events
- [ ] Visualize handoffs between agents

#### Milestone 8.3: Feature Spec Creation
- [ ] Create AddFeatureModal.tsx with spec chat
- [ ] Integrate existing spec creation chat
- [ ] Generate tasks from feature spec
- [ ] Assign feature to phase

---

### Phase 9: Polish & Integration

#### Milestone 9.1: Testing
- [ ] Unit tests for new database models
- [ ] Integration tests for API endpoints
- [ ] E2E tests for UI workflows
- [ ] Multi-agent coordination tests

#### Milestone 9.2: Documentation
- [ ] Update CLAUDE.md with new architecture
- [ ] Create user guide for phases/features/tasks
- [ ] Document multi-agent configuration
- [ ] Add migration guide for existing projects

#### Milestone 9.3: Performance
- [ ] Optimize database queries for large projects
- [ ] Add caching for usage calculations
- [ ] Optimize WebSocket message volume
- [ ] Profile and optimize agent startup time

---

## Summary: Complete Feature List

| Category | Feature | Section |
|----------|---------|---------|
| **Hierarchy** | Projects → Phases → Features → Tasks | §1 |
| **Terminology** | Rename "features" to "tasks" | §1 |
| **Phases** | Phase-based workflow with approval gates | §3 |
| **UI** | Drill-down navigation | §4 |
| **Usage** | Token usage monitoring | §5 |
| **Usage** | Smart task scheduling based on usage | §5 |
| **Agents** | Architect Agent | §10 |
| **Agents** | Reviewer Agent | §10 |
| **Agents** | Testing Agent | §10 |
| **Agents** | Parallel coding agents | §10 |
| **Dependencies** | Task dependency tracking | §11 |
| **Dependencies** | Blocked task detection | §11 |
| **Dependencies** | Dependency graph visualization | §11 |
| **YOLO** | YOLO+Review mode | §12 |
| **YOLO** | Parallel YOLO mode | §12 |
| **YOLO** | Staged YOLO mode | §12 |
| **Orchestration** | Orchestrator service | §13 |
| **Orchestration** | Shared context between agents | §13 |
| **Orchestration** | Agent message queue | §13 |
| **UI** | Multi-agent dashboard | §14 |
| **UI** | Agent timeline view | §14 |
| **UI** | Enhanced Kanban with dependencies | §14 |

---

## Appendix: TypeScript Types Update

```typescript
// ui/src/lib/types.ts - New types

// Phase types
export type PhaseStatus = 'pending' | 'in_progress' | 'awaiting_approval' | 'completed'

export interface Phase {
  id: number
  project_name: string
  name: string
  description: string | null
  order: number
  status: PhaseStatus
  created_at: string | null
  completed_at: string | null
  feature_count: number
}

// Feature types (new concept)
export type FeatureStatus = 'pending' | 'speccing' | 'ready' | 'in_progress' | 'completed'

export interface Feature {
  id: number
  phase_id: number | null
  name: string
  description: string | null
  spec: string | null
  status: FeatureStatus
  priority: number
  agent_id: string | null
  created_at: string | null
  completed_at: string | null
  task_count: number
  tasks_completed: number
}

// Task types (renamed from Feature)
export interface Task {
  id: number
  feature_id: number | null
  priority: number
  category: string
  name: string
  description: string
  steps: string[]
  passes: boolean
  in_progress: boolean
  estimated_complexity: number
}

export interface TaskListResponse {
  pending: Task[]
  in_progress: Task[]
  done: Task[]
}

// Usage types
export interface UsageStats {
  total_tokens: number
  input_tokens: number
  output_tokens: number
  cache_read_tokens: number
  cache_write_tokens: number
  limit: number
  remaining: number
  percentage_used: number
  reset_date: string
}

export interface UsageHistory {
  date: string
  tokens: number
}

// Navigation state
export type ViewLevel = 'projects' | 'phases' | 'features' | 'tasks'

export interface NavigationState {
  level: ViewLevel
  projectName: string | null
  phaseId: number | null
  featureId: number | null
}
```

---

This document provides a complete blueprint for implementing the enhanced Autocoder system with phases, hierarchical task management, and usage monitoring.
