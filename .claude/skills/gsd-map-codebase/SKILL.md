---
name: gsd-map-codebase
description: |
  Analyze existing codebase and document structure. This skill should be used when
  the user wants to onboard an existing project to AutoForge or understand a codebase.
  Triggers: "map codebase", "analyze codebase", "document structure", "onboard project",
  "understand this codebase", before running /gsd-to-autoforge-spec.
---

# GSD Codebase Mapper

Analyzes an existing codebase and generates structured documentation in `.planning/codebase/`.

## When to Use

- Before using `/gsd-to-autoforge-spec` on an existing project
- When onboarding to an unfamiliar codebase
- To document an existing project's architecture
- Before making major changes to understand current structure

## Prerequisites

- An existing codebase to analyze
- Read access to project files
- Project should have recognizable structure (package.json, pyproject.toml, etc.)

## Process

<step name="verify_project">
### Step 1: Verify Project Exists

Confirm the target directory contains a codebase:

```bash
ls -la
```

Look for indicators of a project:
- `package.json` (Node.js/JavaScript)
- `pyproject.toml` or `requirements.txt` (Python)
- `Cargo.toml` (Rust)
- `go.mod` (Go)
- `pom.xml` or `build.gradle` (Java)
- `.git/` directory
- `src/` or `lib/` directories

If no project indicators found:
```
No recognizable project structure found.

Please navigate to a project directory with source code.
```
Stop workflow.
</step>

<step name="create_output_dir">
### Step 2: Create Output Directory

```bash
mkdir -p .planning/codebase
```

This creates the directory structure for GSD codebase documentation.
</step>

<step name="analyze_stack">
### Step 3: Analyze Technology Stack

Examine package managers and configuration files to identify the stack.

**For Node.js projects:**
```bash
cat package.json 2>/dev/null | head -50
```

**For Python projects:**
```bash
cat pyproject.toml 2>/dev/null || cat requirements.txt 2>/dev/null | head -30
```

**For other ecosystems:**
```bash
cat Cargo.toml go.mod pom.xml build.gradle 2>/dev/null | head -50
```

**Generate STACK.md** documenting:
- Primary language(s)
- Frameworks (frontend, backend, testing)
- Key dependencies with versions
- Runtime requirements
- Development tools
- Ports used (from config files or defaults)

```bash
cat > .planning/codebase/STACK.md << 'EOF'
# Technology Stack

## Languages
- {Primary language and version}

## Frameworks
- **Frontend:** {Framework or "N/A"}
- **Backend:** {Framework or "N/A"}
- **Testing:** {Test framework}

## Key Dependencies
- {dependency}: {version} - {purpose}
- {dependency}: {version} - {purpose}

## Runtime
- {Runtime}: {version requirement}
- **Port(s):** {port numbers}

## Development Tools
- {Tool}: {purpose}
EOF
```
</step>

<step name="analyze_structure">
### Step 4: Analyze Directory Structure

Map the project layout:

```bash
find . -type d -not -path '*/node_modules/*' -not -path '*/.git/*' -not -path '*/venv/*' -not -path '*/__pycache__/*' -not -path '*/.next/*' -not -path '*/dist/*' -not -path '*/build/*' | head -50
```

Count files by type:
```bash
find . -type f -name "*.ts" -o -name "*.tsx" -o -name "*.js" -o -name "*.jsx" -o -name "*.py" -o -name "*.rs" -o -name "*.go" 2>/dev/null | wc -l
```

**Generate STRUCTURE.md** documenting:
- Directory layout with purpose of each folder
- Key file locations (entry points, configs)
- Naming conventions observed
- File organization patterns

```bash
cat > .planning/codebase/STRUCTURE.md << 'EOF'
# Project Structure

## Directory Layout

```
{project_name}/
├── {dir}/          # {purpose}
│   ├── {subdir}/   # {purpose}
│   └── {file}      # {purpose}
├── {dir}/          # {purpose}
└── {config_file}   # {purpose}
```

## Key Files
- `{file}` - {purpose, e.g., "Application entry point"}
- `{file}` - {purpose}

## Naming Conventions
- **Files:** {convention, e.g., "kebab-case for components"}
- **Directories:** {convention}
- **Components:** {convention}

## File Counts
- TypeScript/JavaScript: {count} files
- Styles: {count} files
- Tests: {count} files
EOF
```
</step>

<step name="analyze_architecture">
### Step 5: Analyze Architecture

Examine key source files to understand patterns:

```bash
# Find entry points
ls -la src/index.* src/main.* src/app.* app/page.* pages/index.* 2>/dev/null

# Find route definitions
find . -type f \( -name "routes.*" -o -name "router.*" -o -path "*/routes/*" -o -path "*/api/*" \) -not -path '*/node_modules/*' 2>/dev/null | head -10

# Find data layer
find . -type f \( -name "*model*" -o -name "*schema*" -o -name "*entity*" -o -path "*/models/*" -o -path "*/database/*" \) -not -path '*/node_modules/*' 2>/dev/null | head -10
```

Read key architectural files to understand patterns:
- Entry points (main, index, app)
- Route definitions
- Data models/schemas
- State management
- API handlers

**Generate ARCHITECTURE.md** documenting:
- Overall architecture pattern (MVC, layered, etc.)
- Layer descriptions and responsibilities
- Data flow between layers
- Key design patterns used
- Entry points and initialization

```bash
cat > .planning/codebase/ARCHITECTURE.md << 'EOF'
# Architecture

## Overview
{1-2 sentence description of the overall architecture}

## Pattern
**{Pattern name}** (e.g., "Layered Architecture", "MVC", "Clean Architecture")

## Layers

### {Layer 1 Name}
- **Location:** `{path}/`
- **Responsibility:** {what this layer does}
- **Key files:** {main files in this layer}

### {Layer 2 Name}
- **Location:** `{path}/`
- **Responsibility:** {what this layer does}
- **Key files:** {main files in this layer}

## Data Flow
1. {Step 1: e.g., "Request enters via API route"}
2. {Step 2: e.g., "Controller validates input"}
3. {Step 3: e.g., "Service performs business logic"}
4. {Step 4: e.g., "Repository accesses database"}

## Entry Points
- **Main:** `{file}` - {description}
- **API:** `{file}` - {description}
- **CLI:** `{file}` - {description, if applicable}

## Design Patterns
- **{Pattern}:** {where/how it's used}
EOF
```
</step>

<step name="analyze_conventions">
### Step 6: Analyze Code Conventions

Sample source files to identify coding patterns:

```bash
# Sample a component/module file
find . -type f \( -name "*.tsx" -o -name "*.ts" -o -name "*.py" \) -not -path '*/node_modules/*' -not -name "*.test.*" -not -name "*.spec.*" | head -5 | xargs head -50 2>/dev/null
```

Look for:
- Import organization
- Export patterns
- Naming conventions (camelCase, snake_case, PascalCase)
- Comment styles
- Error handling patterns
- Type usage

**Generate CONVENTIONS.md** documenting:
- Code style and formatting
- Naming conventions by type
- Import/export patterns
- Error handling approach
- Testing conventions
- Documentation patterns

```bash
cat > .planning/codebase/CONVENTIONS.md << 'EOF'
# Code Conventions

## Naming
- **Variables:** {convention, e.g., "camelCase"}
- **Functions:** {convention}
- **Classes/Types:** {convention, e.g., "PascalCase"}
- **Constants:** {convention, e.g., "SCREAMING_SNAKE_CASE"}
- **Files:** {convention}

## Imports
- {Pattern, e.g., "External imports first, then internal"}
- {Pattern, e.g., "Absolute imports preferred"}

## Exports
- {Pattern, e.g., "Named exports preferred over default"}

## Error Handling
- {Approach, e.g., "Try/catch with custom error classes"}
- {Pattern, e.g., "Errors logged to console in development"}

## Comments
- {Style, e.g., "JSDoc for public APIs"}
- {Convention, e.g., "TODO: format for incomplete work"}

## Testing
- **Location:** {where tests live, e.g., "__tests__/ or *.test.ts"}
- **Naming:** {convention, e.g., "ComponentName.test.tsx"}
- **Pattern:** {pattern, e.g., "Arrange-Act-Assert"}
EOF
```
</step>

<step name="analyze_integrations">
### Step 7: Analyze Integrations

Look for external service connections:

```bash
# Environment variables
cat .env.example .env.sample 2>/dev/null || echo "No .env example found"

# API clients
find . -type f \( -name "*client*" -o -name "*api*" -o -name "*service*" \) -not -path '*/node_modules/*' 2>/dev/null | head -10

# Database config
find . -type f \( -name "*database*" -o -name "*db*" -o -name "*.prisma" -o -name "knexfile*" \) -not -path '*/node_modules/*' 2>/dev/null | head -10
```

**Generate INTEGRATIONS.md** documenting:
- Database connections and ORMs
- External API integrations
- Third-party services
- Authentication providers
- Environment configuration

```bash
cat > .planning/codebase/INTEGRATIONS.md << 'EOF'
# Integrations

## Database
- **Type:** {database type, e.g., "PostgreSQL", "SQLite"}
- **ORM/Client:** {e.g., "Prisma", "SQLAlchemy"}
- **Connection:** {how configured, e.g., "DATABASE_URL env var"}

## External APIs
- **{API Name}:**
  - Purpose: {what it's used for}
  - Config: {env var or config file}

## Third-Party Services
- **{Service}:** {purpose}

## Authentication
- **Method:** {e.g., "JWT", "Session", "OAuth"}
- **Provider:** {e.g., "Auth0", "Firebase", "Custom"}

## Environment Variables
| Variable | Purpose | Required |
|----------|---------|----------|
| {VAR_NAME} | {purpose} | {Yes/No} |
EOF
```
</step>

<step name="verify_output">
### Step 8: Verify Generated Documentation

```bash
ls -la .planning/codebase/
echo "---"
wc -l .planning/codebase/*.md
```

**Validation checklist:**
- [ ] STACK.md exists and documents languages/frameworks
- [ ] STRUCTURE.md exists and maps directory layout
- [ ] ARCHITECTURE.md exists and describes patterns
- [ ] CONVENTIONS.md exists and captures coding style
- [ ] INTEGRATIONS.md exists and lists external dependencies
</step>

<step name="completion">
### Step 9: Report Completion

Output:
```
Codebase mapping complete.

Output: .planning/codebase/
  - STACK.md        (Technology stack)
  - STRUCTURE.md    (Directory layout)
  - ARCHITECTURE.md (Architecture patterns)
  - CONVENTIONS.md  (Code conventions)
  - INTEGRATIONS.md (External services)

Next steps:

1. Review the generated documentation for accuracy
2. Run /gsd-to-autoforge-spec to convert to AutoForge format
3. Start AutoForge to begin development

Or manually review:
  cat .planning/codebase/ARCHITECTURE.md
```
</step>

## Output Files

| File | Purpose |
|------|---------|
| `.planning/codebase/STACK.md` | Languages, frameworks, dependencies |
| `.planning/codebase/STRUCTURE.md` | Directory layout and file organization |
| `.planning/codebase/ARCHITECTURE.md` | Architecture patterns and data flow |
| `.planning/codebase/CONVENTIONS.md` | Coding style and conventions |
| `.planning/codebase/INTEGRATIONS.md` | External services and APIs |

## Error Handling

| Error | Resolution |
|-------|------------|
| No project files found | Navigate to a project directory first |
| Cannot read config files | Check file permissions |
| Missing package manager | Document stack manually based on source files |
| Complex monorepo | Analyze each package separately |
