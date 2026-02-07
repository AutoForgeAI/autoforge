#!/usr/bin/env python3
"""
MCP Server for Codebase Research
================================

Provides tools for analyzing existing codebases and documenting findings.
Used by AutoForge to understand projects before adding features.

Tools:
- research_scan_files: Scan project files matching glob pattern
- research_detect_stack: Auto-detect technology stack from manifest files
- research_add_finding: Add a finding to a research document section
- research_get_context: Get current state of a research document
- research_finalize: Write findings to .planning/codebase/*.md files
- research_get_stats: Get research progress statistics

Documents:
- STACK: Technology stack (languages, frameworks, databases)
- ARCHITECTURE: System architecture and patterns
- STRUCTURE: Directory and module organization
- CONVENTIONS: Code style and naming conventions
- INTEGRATIONS: External integrations and APIs
"""

import glob as glob_module
import json
import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any, Literal

from mcp.server.fastmcp import FastMCP
from pydantic import Field

# Add parent directory to path so we can import from api module
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.research_database import (
    DOCUMENT_TYPES,
    ResearchDocument,
    ResearchProgress,
    get_research_database_path,
    init_research_db,
    reset_research_db,
)

# Configuration from environment
PROJECT_DIR = Path(os.environ.get("PROJECT_DIR", ".")).resolve()

# Global database session maker (initialized on startup)
_session_maker = None
_engine = None


@asynccontextmanager
async def server_lifespan(server: FastMCP):
    """Initialize database on startup, cleanup on shutdown."""
    global _session_maker, _engine

    # Create project directory if it doesn't exist
    PROJECT_DIR.mkdir(parents=True, exist_ok=True)

    # Initialize research database
    db_path = get_research_database_path(PROJECT_DIR)
    _engine, _session_maker = init_research_db(db_path)

    # Reset database for fresh research session
    # This ensures each research run starts with clean state
    reset_research_db(db_path)

    yield

    # Cleanup
    if _engine:
        _engine.dispose()


# Initialize the MCP server
mcp = FastMCP("research", lifespan=server_lifespan)


def get_session():
    """Get a new database session."""
    if _session_maker is None:
        raise RuntimeError("Database not initialized")
    return _session_maker()


# Manifest files to check for stack detection
MANIFEST_FILES = {
    # JavaScript/Node.js
    "package.json": "javascript",
    "package-lock.json": "javascript",
    "yarn.lock": "javascript",
    "pnpm-lock.yaml": "javascript",
    "bun.lockb": "javascript",
    # Python
    "requirements.txt": "python",
    "pyproject.toml": "python",
    "setup.py": "python",
    "Pipfile": "python",
    "poetry.lock": "python",
    "setup.cfg": "python",
    # Rust
    "Cargo.toml": "rust",
    "Cargo.lock": "rust",
    # Go
    "go.mod": "go",
    "go.sum": "go",
    # Ruby
    "Gemfile": "ruby",
    "Gemfile.lock": "ruby",
    # PHP
    "composer.json": "php",
    "composer.lock": "php",
    # Java/Kotlin
    "pom.xml": "java",
    "build.gradle": "java",
    "build.gradle.kts": "kotlin",
    "settings.gradle": "java",
    "settings.gradle.kts": "kotlin",
    # .NET
    "*.csproj": "csharp",
    "*.fsproj": "fsharp",
    "*.sln": "dotnet",
    "Directory.Build.props": "dotnet",
    "nuget.config": "dotnet",
    # Swift/iOS
    "Package.swift": "swift",
    "Podfile": "swift",
    "*.xcodeproj": "swift",
    "*.xcworkspace": "swift",
    # Docker
    "Dockerfile": "docker",
    "docker-compose.yml": "docker",
    "docker-compose.yaml": "docker",
    # Kubernetes
    "*.yaml": None,  # Special handling for k8s
    "kustomization.yaml": "kubernetes",
    # Terraform
    "*.tf": "terraform",
    "terraform.tfvars": "terraform",
    # Config files
    "tsconfig.json": "typescript",
    ".eslintrc.json": "javascript",
    ".eslintrc.js": "javascript",
    ".prettierrc": "javascript",
    "tailwind.config.js": "tailwind",
    "tailwind.config.ts": "tailwind",
    "vite.config.js": "vite",
    "vite.config.ts": "vite",
    "webpack.config.js": "webpack",
    "next.config.js": "nextjs",
    "next.config.mjs": "nextjs",
    "nuxt.config.ts": "nuxt",
    "astro.config.mjs": "astro",
    # Database
    "prisma/schema.prisma": "prisma",
    "drizzle.config.ts": "drizzle",
    "alembic.ini": "sqlalchemy",
}


def _get_file_metadata(file_path: Path) -> dict:
    """Get metadata for a file."""
    try:
        stat = file_path.stat()
        return {
            "path": str(file_path.relative_to(PROJECT_DIR)),
            "size": stat.st_size,
            "modified": datetime.fromtimestamp(
                stat.st_mtime, tz=timezone.utc
            ).isoformat(),
            "extension": file_path.suffix.lower(),
        }
    except (OSError, ValueError):
        return {
            "path": str(file_path),
            "size": 0,
            "modified": None,
            "extension": file_path.suffix.lower(),
        }


def _detect_from_package_json(package_json_path: Path) -> dict:
    """Extract detailed stack info from package.json."""
    result = {
        "frameworks": [],
        "libraries": [],
        "dev_tools": [],
        "scripts": [],
    }

    try:
        with open(package_json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return result

    deps = {}
    deps.update(data.get("dependencies", {}))
    deps.update(data.get("devDependencies", {}))

    # Framework detection
    framework_patterns = {
        "react": "React",
        "next": "Next.js",
        "vue": "Vue.js",
        "nuxt": "Nuxt",
        "@angular/core": "Angular",
        "svelte": "Svelte",
        "solid-js": "SolidJS",
        "astro": "Astro",
        "remix": "Remix",
        "express": "Express",
        "fastify": "Fastify",
        "hono": "Hono",
        "koa": "Koa",
        "@nestjs/core": "NestJS",
        "electron": "Electron",
    }

    for pattern, name in framework_patterns.items():
        if any(d.startswith(pattern) for d in deps):
            result["frameworks"].append(name)

    # UI library detection
    ui_patterns = {
        "tailwindcss": "Tailwind CSS",
        "@radix-ui": "Radix UI",
        "@shadcn/ui": "shadcn/ui",
        "styled-components": "styled-components",
        "@emotion": "Emotion",
        "@mui": "Material UI",
        "@chakra-ui": "Chakra UI",
        "bootstrap": "Bootstrap",
        "antd": "Ant Design",
    }

    for pattern, name in ui_patterns.items():
        if any(d.startswith(pattern) for d in deps):
            result["libraries"].append(name)

    # State management
    state_patterns = {
        "redux": "Redux",
        "@reduxjs/toolkit": "Redux Toolkit",
        "zustand": "Zustand",
        "jotai": "Jotai",
        "recoil": "Recoil",
        "mobx": "MobX",
        "@tanstack/react-query": "TanStack Query",
        "swr": "SWR",
    }

    for pattern, name in state_patterns.items():
        if any(d.startswith(pattern) for d in deps):
            result["libraries"].append(name)

    # Dev tools
    dev_patterns = {
        "typescript": "TypeScript",
        "eslint": "ESLint",
        "prettier": "Prettier",
        "vitest": "Vitest",
        "jest": "Jest",
        "@playwright/test": "Playwright",
        "cypress": "Cypress",
        "vite": "Vite",
        "webpack": "Webpack",
        "esbuild": "esbuild",
        "turbo": "Turborepo",
    }

    for pattern, name in dev_patterns.items():
        if any(d.startswith(pattern) for d in deps):
            result["dev_tools"].append(name)

    # Extract scripts
    if "scripts" in data:
        result["scripts"] = list(data["scripts"].keys())

    return result


def _detect_from_pyproject(pyproject_path: Path) -> dict:
    """Extract detailed stack info from pyproject.toml."""
    result = {
        "frameworks": [],
        "libraries": [],
        "dev_tools": [],
    }

    try:
        # Use tomllib in Python 3.11+, or tomli as fallback
        try:
            import tomllib
            with open(pyproject_path, "rb") as f:
                data = tomllib.load(f)
        except ImportError:
            # Fallback to basic parsing
            return result
    except OSError:
        return result

    # Collect all dependencies
    deps = []

    # Poetry format
    if "tool" in data and "poetry" in data["tool"]:
        poetry = data["tool"]["poetry"]
        deps.extend(poetry.get("dependencies", {}).keys())
        deps.extend(poetry.get("dev-dependencies", {}).keys())
        if "group" in poetry:
            for group in poetry["group"].values():
                deps.extend(group.get("dependencies", {}).keys())

    # PEP 621 format
    if "project" in data:
        proj = data["project"]
        deps.extend(proj.get("dependencies", []))
        for extra_deps in proj.get("optional-dependencies", {}).values():
            deps.extend(extra_deps)

    # Framework detection
    framework_patterns = {
        "fastapi": "FastAPI",
        "django": "Django",
        "flask": "Flask",
        "starlette": "Starlette",
        "tornado": "Tornado",
        "aiohttp": "aiohttp",
        "sanic": "Sanic",
        "litestar": "Litestar",
    }

    for pattern, name in framework_patterns.items():
        if any(pattern in str(d).lower() for d in deps):
            result["frameworks"].append(name)

    # Database/ORM detection
    db_patterns = {
        "sqlalchemy": "SQLAlchemy",
        "sqlmodel": "SQLModel",
        "tortoise-orm": "Tortoise ORM",
        "peewee": "Peewee",
        "prisma": "Prisma",
        "pymongo": "MongoDB (PyMongo)",
        "redis": "Redis",
        "psycopg": "PostgreSQL",
        "asyncpg": "PostgreSQL (asyncpg)",
        "aiomysql": "MySQL",
    }

    for pattern, name in db_patterns.items():
        if any(pattern in str(d).lower() for d in deps):
            result["libraries"].append(name)

    # Dev tools detection
    dev_patterns = {
        "pytest": "pytest",
        "ruff": "Ruff",
        "black": "Black",
        "mypy": "mypy",
        "pyright": "Pyright",
        "pre-commit": "pre-commit",
        "tox": "tox",
        "nox": "nox",
        "poetry": "Poetry",
        "hatch": "Hatch",
    }

    for pattern, name in dev_patterns.items():
        if any(pattern in str(d).lower() for d in deps):
            result["dev_tools"].append(name)

    return result


@mcp.tool()
def research_scan_files(
    pattern: Annotated[str, Field(description="Glob pattern to match files (e.g., '**/*.py', 'src/**/*.ts')")],
    limit: Annotated[int, Field(default=100, ge=1, le=500, description="Maximum number of files to return")] = 100
) -> str:
    """Scan project files matching a glob pattern.

    Returns file paths and metadata (size, modified date, extension) for files
    matching the pattern. Use this to explore the project structure.

    Common patterns:
    - "**/*.py" - All Python files
    - "src/**/*.ts" - TypeScript files in src/
    - "**/test_*.py" - Python test files
    - "**/*.{js,ts}" - JavaScript and TypeScript files

    Args:
        pattern: Glob pattern to match files
        limit: Maximum number of files to return (1-500, default 100)

    Returns:
        JSON with: files (list of file metadata), count (int), truncated (bool)
    """
    # Security: Ensure pattern doesn't escape project directory
    if ".." in pattern:
        return json.dumps({"error": "Pattern cannot contain '..' for security"})

    # Use glob to find matching files
    search_pattern = str(PROJECT_DIR / pattern)
    matches = glob_module.glob(search_pattern, recursive=True)

    # Filter to only files (not directories)
    files = []
    for match_path in matches:
        path = Path(match_path)
        if path.is_file():
            # Skip hidden files and common non-code directories
            relative = path.relative_to(PROJECT_DIR)
            parts = relative.parts
            if any(part.startswith(".") for part in parts):
                continue
            if any(part in ("node_modules", "__pycache__", "venv", ".venv", "dist", "build") for part in parts):
                continue

            files.append(_get_file_metadata(path))

    # Sort by modification time (newest first)
    files.sort(key=lambda f: f.get("modified") or "", reverse=True)

    # Apply limit
    truncated = len(files) > limit
    files = files[:limit]

    # Update progress tracking - set phase to scanning and update files_scanned
    from api.research_database import get_research_session
    db_path = get_research_database_path(PROJECT_DIR)
    init_research_db(db_path)  # Ensure DB exists
    session = get_research_session(db_path)
    try:
        progress = session.query(ResearchProgress).first()
        if progress:
            # Only update files_scanned, keep phase if already past scanning
            progress.files_scanned = progress.files_scanned + len(files)
            if progress.phase in (None, "scanning"):
                progress.phase = "scanning"
        else:
            progress = ResearchProgress(
                phase="scanning",
                files_scanned=len(files),
                findings_count=0,
            )
            session.add(progress)
        session.commit()
    finally:
        session.close()

    return json.dumps({
        "files": files,
        "count": len(files),
        "truncated": truncated,
        "total_matched": len(matches) if not truncated else f"{limit}+"
    })


@mcp.tool()
def research_detect_stack() -> str:
    """Auto-detect the technology stack from manifest files.

    Scans for package.json, requirements.txt, Cargo.toml, go.mod, and other
    manifest files to determine the languages, frameworks, and tools used.

    Returns:
        JSON with detected stack information including:
        - languages: List of detected programming languages
        - frameworks: Web frameworks, UI libraries
        - databases: Database technologies
        - dev_tools: Linters, formatters, test frameworks
        - manifest_files: List of found manifest files
    """
    result: dict[str, list[str] | dict[str, Any]] = {
        "languages": [],
        "frameworks": [],
        "libraries": [],
        "dev_tools": [],
        "manifest_files": [],
        "package_info": {},
    }

    detected_languages = set()

    # Scan for manifest files
    for manifest, language in MANIFEST_FILES.items():
        # Handle glob patterns in manifest names
        if "*" in manifest:
            matches = glob_module.glob(str(PROJECT_DIR / manifest))
            for match in matches:
                path = Path(match)
                if path.is_file():
                    rel_path = str(path.relative_to(PROJECT_DIR))
                    result["manifest_files"].append(rel_path)
                    if language:
                        detected_languages.add(language)
        else:
            # Handle nested paths like prisma/schema.prisma
            manifest_path = PROJECT_DIR / manifest
            if manifest_path.exists():
                result["manifest_files"].append(manifest)
                if language:
                    detected_languages.add(language)

    # Deep analysis of package.json
    package_json_path = PROJECT_DIR / "package.json"
    if package_json_path.exists():
        pkg_info = _detect_from_package_json(package_json_path)
        result["frameworks"].extend(pkg_info["frameworks"])
        result["libraries"].extend(pkg_info["libraries"])
        result["dev_tools"].extend(pkg_info["dev_tools"])
        if pkg_info["scripts"]:
            result["package_info"]["npm_scripts"] = pkg_info["scripts"]

    # Deep analysis of pyproject.toml
    pyproject_path = PROJECT_DIR / "pyproject.toml"
    if pyproject_path.exists():
        py_info = _detect_from_pyproject(pyproject_path)
        result["frameworks"].extend(py_info["frameworks"])
        result["libraries"].extend(py_info["libraries"])
        result["dev_tools"].extend(py_info["dev_tools"])

    # Check for requirements.txt
    requirements_path = PROJECT_DIR / "requirements.txt"
    if requirements_path.exists():
        try:
            with open(requirements_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                # Extract package names (handle version specifiers)
                packages = []
                for line in lines:
                    line = line.strip()
                    if line and not line.startswith("#") and not line.startswith("-"):
                        # Extract package name before version specifier
                        for sep in ("==", ">=", "<=", ">", "<", "~=", "["):
                            if sep in line:
                                line = line.split(sep)[0]
                                break
                        packages.append(line.strip())
                result["package_info"]["python_packages"] = packages[:20]  # Limit for readability
        except OSError:
            pass

    # Detect TypeScript
    tsconfig_path = PROJECT_DIR / "tsconfig.json"
    if tsconfig_path.exists():
        detected_languages.add("typescript")

    # Convert sets to sorted lists
    result["languages"] = sorted(detected_languages)

    # Remove duplicates from lists
    result["frameworks"] = sorted(set(result["frameworks"]))
    result["libraries"] = sorted(set(result["libraries"]))
    result["dev_tools"] = sorted(set(result["dev_tools"]))

    # Update progress tracking - ensure phase is at least "scanning"
    from api.research_database import get_research_session
    db_path = get_research_database_path(PROJECT_DIR)
    init_research_db(db_path)  # Ensure DB exists
    session = get_research_session(db_path)
    try:
        progress = session.query(ResearchProgress).first()
        if not progress:
            progress = ResearchProgress(
                phase="scanning",
                files_scanned=0,
                findings_count=0,
            )
            session.add(progress)
            session.commit()
    finally:
        session.close()

    return json.dumps(result)


@mcp.tool()
def research_add_finding(
    document: Annotated[
        Literal["STACK", "ARCHITECTURE", "STRUCTURE", "CONVENTIONS", "INTEGRATIONS"],
        Field(description="Which document to add the finding to")
    ],
    section: Annotated[str, Field(min_length=1, max_length=100, description="Section heading within the document")],
    content: Annotated[str, Field(min_length=1, description="The finding content (markdown supported)")],
    source_files: Annotated[list[str], Field(default=[], description="List of source files this finding is based on")] = []
) -> str:
    """Add a research finding to a specific document section.

    Findings are accumulated and later rendered to markdown files when
    research_finalize() is called.

    Document types:
    - STACK: Languages, frameworks, databases, build tools
    - ARCHITECTURE: Patterns, layers, data flow, security model
    - STRUCTURE: Directory layout, module organization
    - CONVENTIONS: Naming, formatting, error handling, testing patterns
    - INTEGRATIONS: APIs, webhooks, external services

    Args:
        document: Which document to add the finding to
        section: Section heading (e.g., "Frontend Framework", "API Patterns")
        content: The finding content in markdown format
        source_files: Optional list of files this finding is based on

    Returns:
        JSON with: success (bool), finding_id (int), document, section
    """
    if document not in DOCUMENT_TYPES:
        return json.dumps({
            "error": f"Invalid document. Must be one of: {', '.join(sorted(DOCUMENT_TYPES))}"
        })

    session = get_session()
    try:
        # Store source_files as JSON array (the column uses SQLAlchemy JSON type)
        finding = ResearchDocument(
            document_type=document,
            section=section,
            content=content,
            source_files=source_files if source_files else None,
        )
        session.add(finding)
        session.commit()
        session.refresh(finding)

        # Update progress tracking
        progress = session.query(ResearchProgress).first()
        if progress:
            progress.findings_count = session.query(ResearchDocument).count()
            # Transition to analyzing phase when first finding is added
            if progress.phase in (None, "scanning"):
                progress.phase = "analyzing"
        else:
            progress = ResearchProgress(
                phase="analyzing",
                findings_count=1,
            )
            session.add(progress)
        session.commit()

        return json.dumps({
            "success": True,
            "finding_id": finding.id,
            "document": document,
            "section": section,
        })
    except Exception as e:
        session.rollback()
        return json.dumps({"error": f"Failed to add finding: {str(e)}"})
    finally:
        session.close()


@mcp.tool()
def research_get_context(
    document: Annotated[str, Field(description="Document name (STACK, ARCHITECTURE, STRUCTURE, CONVENTIONS, INTEGRATIONS) or 'ALL'")]
) -> str:
    """Get the current state of a research document.

    Returns all findings for the specified document, organized by section.
    Use 'ALL' to get findings from all documents.

    Args:
        document: Document name or 'ALL' for everything

    Returns:
        JSON with document structure containing sections and findings
    """
    session = get_session()
    try:
        if document.upper() == "ALL":
            findings = (
                session.query(ResearchDocument)
                .order_by(
                    ResearchDocument.document_type,
                    ResearchDocument.section,
                    ResearchDocument.created_at
                )
                .all()
            )
        elif document.upper() in DOCUMENT_TYPES:
            findings = (
                session.query(ResearchDocument)
                .filter(ResearchDocument.document_type == document.upper())
                .order_by(ResearchDocument.section, ResearchDocument.created_at)
                .all()
            )
        else:
            return json.dumps({
                "error": f"Invalid document. Must be one of: {', '.join(sorted(DOCUMENT_TYPES))} or 'ALL'"
            })

        # Organize by document and section
        organized: dict[str, dict[str, list]] = {}
        for finding in findings:
            doc = finding.document_type
            sec = finding.section

            if doc not in organized:
                organized[doc] = {}
            if sec not in organized[doc]:
                organized[doc][sec] = []

            organized[doc][sec].append(finding.to_dict())

        return json.dumps({
            "documents": organized,
            "total_findings": len(findings),
        })
    finally:
        session.close()


@mcp.tool()
def research_finalize() -> str:
    """Finalize research and write documents to .planning/codebase/*.md files.

    Renders all accumulated findings into markdown documents organized by
    document type and section. Creates the output directory if needed.

    Output files:
    - .planning/codebase/STACK.md
    - .planning/codebase/ARCHITECTURE.md
    - .planning/codebase/STRUCTURE.md
    - .planning/codebase/CONVENTIONS.md
    - .planning/codebase/INTEGRATIONS.md

    Returns:
        JSON with: success (bool), files_written (list), total_findings (int)
    """
    session = get_session()
    try:
        # Create output directory
        output_dir = PROJECT_DIR / ".planning" / "codebase"
        output_dir.mkdir(parents=True, exist_ok=True)

        # Get all findings ordered by document, section, created_at
        all_findings = (
            session.query(ResearchDocument)
            .order_by(
                ResearchDocument.document_type,
                ResearchDocument.section,
                ResearchDocument.created_at
            )
            .all()
        )

        # Organize findings by document
        by_document: dict[str, dict[str, list]] = {doc: {} for doc in DOCUMENT_TYPES}

        for finding in all_findings:
            doc = finding.document_type
            sec = finding.section

            if sec not in by_document[doc]:
                by_document[doc][sec] = []
            by_document[doc][sec].append(finding)

        # Document titles and descriptions
        doc_info = {
            "STACK": ("Technology Stack", "Languages, frameworks, databases, and build tools used in this codebase."),
            "ARCHITECTURE": ("Architecture", "System architecture, design patterns, and code organization."),
            "STRUCTURE": ("Project Structure", "Directory layout and module organization."),
            "CONVENTIONS": ("Code Conventions", "Naming conventions, formatting rules, and coding standards."),
            "INTEGRATIONS": ("Integrations", "External APIs, services, and third-party integrations."),
        }

        files_written = []
        total_findings = 0

        # Write each document
        for doc_name in DOCUMENT_TYPES:
            title, description = doc_info[doc_name]
            sections = by_document[doc_name]

            # Generate markdown content
            lines = [
                f"# {title}",
                "",
                f"> {description}",
                "",
                f"*Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}*",
                "",
            ]

            if not sections:
                lines.extend([
                    "---",
                    "",
                    "*No findings recorded for this document.*",
                    "",
                ])
            else:
                for section_name in sorted(sections.keys()):
                    findings = sections[section_name]
                    lines.extend([
                        "---",
                        "",
                        f"## {section_name}",
                        "",
                    ])

                    for finding in findings:
                        lines.append(finding.content)
                        lines.append("")

                        # Add source file references if present
                        source_list = finding.get_source_files_safe()
                        if source_list:
                            lines.append("*Source files:*")
                            for src in source_list[:5]:  # Limit to 5 files
                                lines.append(f"- `{src}`")
                            lines.append("")

                        total_findings += 1

            # Write the file
            output_path = output_dir / f"{doc_name}.md"
            with open(output_path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))

            files_written.append(str(output_path.relative_to(PROJECT_DIR)))

        # Update progress to complete
        progress = session.query(ResearchProgress).first()
        if progress:
            progress.phase = "complete"
            progress.findings_count = total_findings
            progress.completed_at = datetime.now(timezone.utc)
        else:
            progress = ResearchProgress(
                phase="complete",
                findings_count=total_findings,
                completed_at=datetime.now(timezone.utc),
            )
            session.add(progress)
        session.commit()

        return json.dumps({
            "success": True,
            "files_written": files_written,
            "total_findings": total_findings,
            "output_directory": str(output_dir.relative_to(PROJECT_DIR)),
        })
    except Exception as e:
        return json.dumps({"error": f"Failed to finalize research: {str(e)}"})
    finally:
        session.close()


@mcp.tool()
def research_get_stats() -> str:
    """Get research progress statistics.

    Returns counts of findings by document type, total findings, and
    whether research has been finalized.

    Returns:
        JSON with: by_document (dict), total_findings (int), finalized (bool), finalized_at (str|null)
    """
    session = get_session()
    try:
        from sqlalchemy import func

        # Count findings by document type
        counts = (
            session.query(
                ResearchDocument.document_type,
                func.count(ResearchDocument.id).label("count")
            )
            .group_by(ResearchDocument.document_type)
            .all()
        )

        by_document = {doc: 0 for doc in DOCUMENT_TYPES}
        total = 0
        for doc, count in counts:
            by_document[doc] = count
            total += count

        # Check progress status
        progress = session.query(ResearchProgress).first()
        finalized = progress.is_complete() if progress else False
        finalized_at = (
            progress.completed_at.isoformat()
            if progress and progress.completed_at
            else None
        )
        phase = progress.phase if progress else "not_started"
        files_scanned = progress.files_scanned if progress else 0

        return json.dumps({
            "by_document": by_document,
            "total_findings": total,
            "phase": phase,
            "files_scanned": files_scanned,
            "finalized": finalized,
            "finalized_at": finalized_at,
        })
    finally:
        session.close()


if __name__ == "__main__":
    mcp.run()
