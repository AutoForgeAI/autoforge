"""
Stack Detector
==============

Detects technology stack from manifest files in a codebase.
Analyzes package.json, requirements.txt, pyproject.toml, and other
manifest files to identify languages, frameworks, and dependencies.
"""

import json
import logging
import re
from pathlib import Path
from typing import TypedDict

# Python 3.11+ has tomllib in the standard library
try:
    import tomllib
except ImportError:
    tomllib = None  # type: ignore[assignment]


logger = logging.getLogger(__name__)


# =============================================================================
# Type Definitions
# =============================================================================


class FrameworksByCategory(TypedDict):
    """Frameworks organized by category."""

    frontend: list[str]
    backend: list[str]
    testing: list[str]
    styling: list[str]
    database: list[str]
    build: list[str]


class RuntimeVersions(TypedDict, total=False):
    """Runtime version information."""

    python: str
    node: str
    rust: str
    go: str
    java: str
    ruby: str
    php: str
    dotnet: str


class StackDetectionResult(TypedDict):
    """Complete stack detection result."""

    languages: list[str]
    frameworks: FrameworksByCategory
    dependencies: dict[str, dict[str, str]]
    runtime: RuntimeVersions
    build_tools: list[str]
    detected_from: list[str]


# =============================================================================
# Framework Detection Patterns
# =============================================================================

# Package name patterns that indicate specific frameworks
# Format: (package_pattern, framework_name, category)
# Pattern can be exact match or regex

NODE_FRAMEWORK_PATTERNS: list[tuple[str, str, str]] = [
    # Frontend frameworks
    ("react", "React", "frontend"),
    ("react-dom", "React", "frontend"),
    ("vue", "Vue", "frontend"),
    ("@vue/", "Vue", "frontend"),
    ("svelte", "Svelte", "frontend"),
    ("@angular/core", "Angular", "frontend"),
    ("solid-js", "Solid.js", "frontend"),
    ("preact", "Preact", "frontend"),
    ("lit", "Lit", "frontend"),
    ("qwik", "Qwik", "frontend"),
    ("htmx.org", "HTMX", "frontend"),
    ("alpinejs", "Alpine.js", "frontend"),
    # Meta-frameworks / SSR
    ("next", "Next.js", "frontend"),
    ("nuxt", "Nuxt.js", "frontend"),
    ("gatsby", "Gatsby", "frontend"),
    ("astro", "Astro", "frontend"),
    ("remix", "Remix", "frontend"),
    ("@remix-run/", "Remix", "frontend"),
    ("sveltekit", "SvelteKit", "frontend"),
    # Backend frameworks
    ("express", "Express.js", "backend"),
    ("fastify", "Fastify", "backend"),
    ("koa", "Koa", "backend"),
    ("hapi", "Hapi", "backend"),
    ("@hapi/hapi", "Hapi", "backend"),
    ("nestjs", "NestJS", "backend"),
    ("@nestjs/", "NestJS", "backend"),
    ("hono", "Hono", "backend"),
    ("elysia", "Elysia", "backend"),
    # Testing frameworks
    ("jest", "Jest", "testing"),
    ("vitest", "Vitest", "testing"),
    ("mocha", "Mocha", "testing"),
    ("cypress", "Cypress", "testing"),
    ("playwright", "Playwright", "testing"),
    ("@playwright/test", "Playwright", "testing"),
    ("@testing-library/", "Testing Library", "testing"),
    ("puppeteer", "Puppeteer", "testing"),
    # Styling
    ("tailwindcss", "Tailwind CSS", "styling"),
    ("styled-components", "Styled Components", "styling"),
    ("@emotion/", "Emotion", "styling"),
    ("sass", "Sass", "styling"),
    ("less", "Less", "styling"),
    ("@mui/material", "Material UI", "styling"),
    ("@chakra-ui/", "Chakra UI", "styling"),
    ("@radix-ui/", "Radix UI", "styling"),
    ("antd", "Ant Design", "styling"),
    ("bootstrap", "Bootstrap", "styling"),
    # Database / ORM
    ("prisma", "Prisma", "database"),
    ("@prisma/client", "Prisma", "database"),
    ("typeorm", "TypeORM", "database"),
    ("sequelize", "Sequelize", "database"),
    ("mongoose", "Mongoose", "database"),
    ("drizzle-orm", "Drizzle", "database"),
    ("knex", "Knex.js", "database"),
    # Build tools (usually devDependencies)
    ("vite", "Vite", "build"),
    ("webpack", "Webpack", "build"),
    ("esbuild", "esbuild", "build"),
    ("rollup", "Rollup", "build"),
    ("parcel", "Parcel", "build"),
    ("turbo", "Turborepo", "build"),
    ("@swc/core", "SWC", "build"),
    ("tsup", "tsup", "build"),
]

PYTHON_FRAMEWORK_PATTERNS: list[tuple[str, str, str]] = [
    # Backend frameworks
    ("fastapi", "FastAPI", "backend"),
    ("django", "Django", "backend"),
    ("flask", "Flask", "backend"),
    ("starlette", "Starlette", "backend"),
    ("tornado", "Tornado", "backend"),
    ("pyramid", "Pyramid", "backend"),
    ("falcon", "Falcon", "backend"),
    ("bottle", "Bottle", "backend"),
    ("sanic", "Sanic", "backend"),
    ("litestar", "Litestar", "backend"),
    ("aiohttp", "aiohttp", "backend"),
    ("quart", "Quart", "backend"),
    # Frontend (Python web frameworks with templating)
    ("streamlit", "Streamlit", "frontend"),
    ("gradio", "Gradio", "frontend"),
    ("nicegui", "NiceGUI", "frontend"),
    ("reflex", "Reflex", "frontend"),
    ("flet", "Flet", "frontend"),
    ("dash", "Dash", "frontend"),
    # Testing
    ("pytest", "pytest", "testing"),
    ("unittest", "unittest", "testing"),
    ("nose2", "nose2", "testing"),
    ("hypothesis", "Hypothesis", "testing"),
    ("behave", "Behave", "testing"),
    ("robot", "Robot Framework", "testing"),
    ("locust", "Locust", "testing"),
    ("playwright", "Playwright", "testing"),
    ("selenium", "Selenium", "testing"),
    # Database / ORM
    ("sqlalchemy", "SQLAlchemy", "database"),
    ("django", "Django ORM", "database"),
    ("tortoise-orm", "Tortoise ORM", "database"),
    ("peewee", "Peewee", "database"),
    ("sqlmodel", "SQLModel", "database"),
    ("alembic", "Alembic", "database"),
    ("asyncpg", "asyncpg", "database"),
    ("psycopg", "psycopg", "database"),
    ("pymongo", "PyMongo", "database"),
    ("motor", "Motor", "database"),
    ("redis", "Redis", "database"),
    # Build tools
    ("poetry", "Poetry", "build"),
    ("setuptools", "setuptools", "build"),
    ("flit", "Flit", "build"),
    ("hatch", "Hatch", "build"),
    ("pdm", "PDM", "build"),
]

PHP_FRAMEWORK_PATTERNS: list[tuple[str, str, str]] = [
    ("laravel/framework", "Laravel", "backend"),
    ("symfony/", "Symfony", "backend"),
    ("slim/slim", "Slim", "backend"),
    ("cakephp/cakephp", "CakePHP", "backend"),
    ("yiisoft/yii2", "Yii", "backend"),
    ("codeigniter4/framework", "CodeIgniter", "backend"),
    ("phpunit/phpunit", "PHPUnit", "testing"),
    ("doctrine/orm", "Doctrine", "database"),
    ("illuminate/database", "Eloquent", "database"),
]

RUBY_FRAMEWORK_PATTERNS: list[tuple[str, str, str]] = [
    ("rails", "Ruby on Rails", "backend"),
    ("sinatra", "Sinatra", "backend"),
    ("hanami", "Hanami", "backend"),
    ("rspec", "RSpec", "testing"),
    ("minitest", "Minitest", "testing"),
    ("capybara", "Capybara", "testing"),
    ("activerecord", "ActiveRecord", "database"),
    ("sequel", "Sequel", "database"),
]


# =============================================================================
# Manifest Parsers
# =============================================================================


def _parse_package_json(project_dir: Path) -> dict | None:
    """
    Parse package.json if it exists.

    Args:
        project_dir: Path to the project directory.

    Returns:
        Parsed package.json as dict, or None if not found or invalid.
    """
    package_json_path = project_dir / "package.json"

    if not package_json_path.exists():
        return None

    try:
        with open(package_json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                logger.debug("Parsed package.json in %s", project_dir)
                return data
            return None
    except (json.JSONDecodeError, OSError) as e:
        logger.debug("Failed to parse package.json in %s: %s", project_dir, e)
        return None


def _parse_requirements_txt(project_dir: Path) -> dict[str, str]:
    """
    Parse requirements.txt to extract package names and versions.

    Handles various formats:
    - package==1.0.0
    - package>=1.0.0
    - package~=1.0.0
    - package[extra]>=1.0.0
    - package  # with comment
    - -r other-requirements.txt (ignored)
    - -e git+... (ignored)

    Args:
        project_dir: Path to the project directory.

    Returns:
        Dict mapping package names to version specifiers.
    """
    requirements_path = project_dir / "requirements.txt"

    if not requirements_path.exists():
        return {}

    packages: dict[str, str] = {}

    # Regex to parse requirement lines
    # Matches: package_name[extras] version_spec
    req_pattern = re.compile(
        r"^([a-zA-Z0-9][-a-zA-Z0-9._]*)"  # Package name
        r"(?:\[[^\]]+\])?"  # Optional extras [extra1,extra2]
        r"([<>=!~].*)?"  # Optional version specifier
        r"(?:\s*#.*)?$"  # Optional comment
    )

    try:
        with open(requirements_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()

                # Skip empty lines, comments, and special directives
                if not line or line.startswith("#") or line.startswith("-"):
                    continue

                match = req_pattern.match(line)
                if match:
                    pkg_name = match.group(1).lower()
                    version = match.group(2) or "*"
                    packages[pkg_name] = version.strip()

        logger.debug(
            "Parsed requirements.txt in %s: %d packages", project_dir, len(packages)
        )

    except OSError as e:
        logger.debug("Failed to read requirements.txt in %s: %s", project_dir, e)

    return packages


def _parse_pyproject_toml(project_dir: Path) -> dict | None:
    """
    Parse pyproject.toml if it exists.

    Args:
        project_dir: Path to the project directory.

    Returns:
        Parsed pyproject.toml as dict, or None if not found or invalid.
    """
    pyproject_path = project_dir / "pyproject.toml"

    if not pyproject_path.exists():
        return None

    if tomllib is None:
        logger.debug("tomllib not available, skipping pyproject.toml parsing")
        return None

    try:
        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)
            logger.debug("Parsed pyproject.toml in %s", project_dir)
            return data
    except Exception as e:
        logger.debug("Failed to parse pyproject.toml in %s: %s", project_dir, e)
        return None


def _parse_cargo_toml(project_dir: Path) -> dict | None:
    """
    Parse Cargo.toml if it exists.

    Args:
        project_dir: Path to the project directory.

    Returns:
        Parsed Cargo.toml as dict, or None if not found or invalid.
    """
    cargo_path = project_dir / "Cargo.toml"

    if not cargo_path.exists():
        return None

    if tomllib is None:
        logger.debug("tomllib not available, skipping Cargo.toml parsing")
        return None

    try:
        with open(cargo_path, "rb") as f:
            data = tomllib.load(f)
            logger.debug("Parsed Cargo.toml in %s", project_dir)
            return data
    except Exception as e:
        logger.debug("Failed to parse Cargo.toml in %s: %s", project_dir, e)
        return None


def _parse_go_mod(project_dir: Path) -> dict[str, str]:
    """
    Parse go.mod to extract module dependencies.

    Args:
        project_dir: Path to the project directory.

    Returns:
        Dict mapping module paths to versions.
    """
    go_mod_path = project_dir / "go.mod"

    if not go_mod_path.exists():
        return {}

    modules: dict[str, str] = {}

    # Patterns for parsing go.mod
    require_line = re.compile(r"^\s*([^\s]+)\s+([^\s]+)")
    go_version = re.compile(r"^go\s+(\d+\.\d+)")

    try:
        with open(go_mod_path, "r", encoding="utf-8") as f:
            in_require_block = False
            for line in f:
                line = line.strip()

                # Track require block
                if line == "require (":
                    in_require_block = True
                    continue
                elif line == ")" and in_require_block:
                    in_require_block = False
                    continue

                # Parse go version
                go_match = go_version.match(line)
                if go_match:
                    modules["go"] = go_match.group(1)
                    continue

                # Parse inline require or require block entries
                if line.startswith("require ") or in_require_block:
                    # Remove 'require ' prefix if present
                    if line.startswith("require "):
                        line = line[8:].strip()

                    # Skip indirect dependencies
                    if "// indirect" in line:
                        continue

                    match = require_line.match(line)
                    if match:
                        modules[match.group(1)] = match.group(2)

        logger.debug("Parsed go.mod in %s: %d modules", project_dir, len(modules))

    except OSError as e:
        logger.debug("Failed to read go.mod in %s: %s", project_dir, e)

    return modules


def _parse_composer_json(project_dir: Path) -> dict | None:
    """
    Parse composer.json if it exists.

    Args:
        project_dir: Path to the project directory.

    Returns:
        Parsed composer.json as dict, or None if not found or invalid.
    """
    composer_path = project_dir / "composer.json"

    if not composer_path.exists():
        return None

    try:
        with open(composer_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                logger.debug("Parsed composer.json in %s", project_dir)
                return data
            return None
    except (json.JSONDecodeError, OSError) as e:
        logger.debug("Failed to parse composer.json in %s: %s", project_dir, e)
        return None


def _parse_gemfile(project_dir: Path) -> dict[str, str]:
    """
    Parse Gemfile to extract gem dependencies.

    Args:
        project_dir: Path to the project directory.

    Returns:
        Dict mapping gem names to version specifiers.
    """
    gemfile_path = project_dir / "Gemfile"

    if not gemfile_path.exists():
        return {}

    gems: dict[str, str] = {}

    # Pattern to match gem declarations
    # gem 'name', 'version'  or  gem "name", "~> 1.0"
    gem_pattern = re.compile(
        r"""gem\s+['"]([^'"]+)['"]"""  # gem name
        r"""(?:\s*,\s*['"]([^'"]+)['"])?"""  # optional version
    )

    try:
        with open(gemfile_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()

                # Skip comments
                if line.startswith("#"):
                    continue

                match = gem_pattern.match(line)
                if match:
                    gem_name = match.group(1)
                    version = match.group(2) or "*"
                    gems[gem_name] = version

        logger.debug("Parsed Gemfile in %s: %d gems", project_dir, len(gems))

    except OSError as e:
        logger.debug("Failed to read Gemfile in %s: %s", project_dir, e)

    return gems


def _parse_pom_xml(project_dir: Path) -> dict[str, str]:
    """
    Parse pom.xml to extract Maven dependencies (basic parsing).

    This is a simplified parser that extracts groupId:artifactId -> version.

    Args:
        project_dir: Path to the project directory.

    Returns:
        Dict mapping dependency coordinates to versions.
    """
    pom_path = project_dir / "pom.xml"

    if not pom_path.exists():
        return {}

    dependencies: dict[str, str] = {}

    # Simple regex-based parsing (not full XML parsing to avoid dependencies)
    # This handles the common case but may miss some edge cases
    dep_pattern = re.compile(
        r"<dependency>\s*"
        r"<groupId>([^<]+)</groupId>\s*"
        r"<artifactId>([^<]+)</artifactId>\s*"
        r"(?:<version>([^<]+)</version>)?",
        re.DOTALL,
    )

    try:
        with open(pom_path, "r", encoding="utf-8") as f:
            content = f.read()

        for match in dep_pattern.finditer(content):
            group_id = match.group(1).strip()
            artifact_id = match.group(2).strip()
            version = match.group(3).strip() if match.group(3) else "*"
            coord = f"{group_id}:{artifact_id}"
            dependencies[coord] = version

        logger.debug("Parsed pom.xml in %s: %d dependencies", project_dir, len(dependencies))

    except OSError as e:
        logger.debug("Failed to read pom.xml in %s: %s", project_dir, e)

    return dependencies


def _parse_build_gradle(project_dir: Path) -> dict[str, str]:
    """
    Parse build.gradle to extract Gradle dependencies (basic parsing).

    Args:
        project_dir: Path to the project directory.

    Returns:
        Dict mapping dependency coordinates to versions.
    """
    # Check both build.gradle and build.gradle.kts
    gradle_path = project_dir / "build.gradle"
    if not gradle_path.exists():
        gradle_path = project_dir / "build.gradle.kts"
    if not gradle_path.exists():
        return {}

    dependencies: dict[str, str] = {}

    # Pattern for Gradle dependencies
    # implementation 'group:artifact:version'
    # implementation("group:artifact:version")
    dep_pattern = re.compile(
        r"""(?:implementation|api|compile|testImplementation)\s*"""
        r"""[('"]([^:'"]+):([^:'"]+):?([^'"]*)?['")]"""
    )

    try:
        with open(gradle_path, "r", encoding="utf-8") as f:
            content = f.read()

        for match in dep_pattern.finditer(content):
            group_id = match.group(1).strip()
            artifact_id = match.group(2).strip()
            version = match.group(3).strip() if match.group(3) else "*"
            coord = f"{group_id}:{artifact_id}"
            dependencies[coord] = version

        logger.debug(
            "Parsed build.gradle in %s: %d dependencies", project_dir, len(dependencies)
        )

    except OSError as e:
        logger.debug("Failed to read build.gradle in %s: %s", project_dir, e)

    return dependencies


def _parse_csproj(project_dir: Path) -> dict[str, str]:
    """
    Parse .csproj files to extract NuGet package references.

    Searches for any .csproj file in the project directory.

    Args:
        project_dir: Path to the project directory.

    Returns:
        Dict mapping package names to versions.
    """
    packages: dict[str, str] = {}

    # Find .csproj files
    csproj_files = list(project_dir.glob("*.csproj"))
    if not csproj_files:
        return {}

    # Pattern for PackageReference
    pkg_pattern = re.compile(
        r'<PackageReference\s+Include="([^"]+)"' r'(?:\s+Version="([^"]+)")?'
    )

    for csproj_path in csproj_files:
        try:
            with open(csproj_path, "r", encoding="utf-8") as f:
                content = f.read()

            for match in pkg_pattern.finditer(content):
                pkg_name = match.group(1)
                version = match.group(2) or "*"
                packages[pkg_name] = version

            logger.debug("Parsed %s: %d packages", csproj_path.name, len(packages))

        except OSError as e:
            logger.debug("Failed to read %s: %s", csproj_path, e)

    return packages


# =============================================================================
# Framework Detection
# =============================================================================


def _detect_node_frameworks(
    package_json: dict,
) -> tuple[FrameworksByCategory, dict[str, str]]:
    """
    Detect Node.js frameworks from package.json dependencies.

    Args:
        package_json: Parsed package.json dict.

    Returns:
        Tuple of (frameworks dict by category, all dependencies dict).
    """
    frameworks: FrameworksByCategory = {
        "frontend": [],
        "backend": [],
        "testing": [],
        "styling": [],
        "database": [],
        "build": [],
    }
    all_deps: dict[str, str] = {}

    # Combine all dependency types
    for dep_key in ("dependencies", "devDependencies", "peerDependencies"):
        deps = package_json.get(dep_key, {})
        if isinstance(deps, dict):
            all_deps.update(deps)

    # Detect frameworks from dependencies
    seen_frameworks: set[str] = set()

    for pkg_name, version in all_deps.items():
        for pattern, framework, category in NODE_FRAMEWORK_PATTERNS:
            # Check if package name matches pattern (exact or prefix)
            if pkg_name == pattern or (
                pattern.endswith("/") and pkg_name.startswith(pattern)
            ):
                if framework not in seen_frameworks:
                    frameworks[category].append(framework)  # type: ignore[literal-required]
                    seen_frameworks.add(framework)
                break

    return frameworks, all_deps


def _detect_python_frameworks(
    packages: dict[str, str],
) -> FrameworksByCategory:
    """
    Detect Python frameworks from package names.

    Args:
        packages: Dict mapping package names to versions.

    Returns:
        Frameworks dict by category.
    """
    frameworks: FrameworksByCategory = {
        "frontend": [],
        "backend": [],
        "testing": [],
        "styling": [],
        "database": [],
        "build": [],
    }
    seen_frameworks: set[str] = set()

    for pkg_name in packages:
        pkg_lower = pkg_name.lower()
        for pattern, framework, category in PYTHON_FRAMEWORK_PATTERNS:
            if pkg_lower == pattern or pkg_lower.startswith(pattern):
                if framework not in seen_frameworks:
                    frameworks[category].append(framework)  # type: ignore[literal-required]
                    seen_frameworks.add(framework)
                break

    return frameworks


def _detect_php_frameworks(packages: dict[str, str]) -> FrameworksByCategory:
    """
    Detect PHP frameworks from composer packages.

    Args:
        packages: Dict mapping package names to versions.

    Returns:
        Frameworks dict by category.
    """
    frameworks: FrameworksByCategory = {
        "frontend": [],
        "backend": [],
        "testing": [],
        "styling": [],
        "database": [],
        "build": [],
    }
    seen_frameworks: set[str] = set()

    for pkg_name in packages:
        pkg_lower = pkg_name.lower()
        for pattern, framework, category in PHP_FRAMEWORK_PATTERNS:
            if pkg_lower == pattern or pkg_lower.startswith(pattern):
                if framework not in seen_frameworks:
                    frameworks[category].append(framework)  # type: ignore[literal-required]
                    seen_frameworks.add(framework)
                break

    return frameworks


def _detect_ruby_frameworks(gems: dict[str, str]) -> FrameworksByCategory:
    """
    Detect Ruby frameworks from gems.

    Args:
        gems: Dict mapping gem names to versions.

    Returns:
        Frameworks dict by category.
    """
    frameworks: FrameworksByCategory = {
        "frontend": [],
        "backend": [],
        "testing": [],
        "styling": [],
        "database": [],
        "build": [],
    }
    seen_frameworks: set[str] = set()

    for gem_name in gems:
        gem_lower = gem_name.lower()
        for pattern, framework, category in RUBY_FRAMEWORK_PATTERNS:
            if gem_lower == pattern or gem_lower.startswith(pattern):
                if framework not in seen_frameworks:
                    frameworks[category].append(framework)  # type: ignore[literal-required]
                    seen_frameworks.add(framework)
                break

    return frameworks


def _merge_frameworks(
    target: FrameworksByCategory, source: FrameworksByCategory
) -> None:
    """
    Merge source frameworks into target, avoiding duplicates.

    Args:
        target: Target frameworks dict to merge into.
        source: Source frameworks dict to merge from.
    """
    for category in ("frontend", "backend", "testing", "styling", "database", "build"):
        for framework in source[category]:
            if framework not in target[category]:
                target[category].append(framework)


# =============================================================================
# Runtime Detection
# =============================================================================


def _detect_node_version(package_json: dict) -> str | None:
    """
    Extract Node.js version from package.json engines field.

    Args:
        package_json: Parsed package.json dict.

    Returns:
        Node version string or None.
    """
    engines = package_json.get("engines", {})
    if isinstance(engines, dict):
        node_ver = engines.get("node")
        if isinstance(node_ver, str):
            return node_ver
    return None


def _detect_python_version(pyproject: dict | None) -> str | None:
    """
    Extract Python version from pyproject.toml.

    Checks [project].requires-python and [tool.poetry.dependencies].python.

    Args:
        pyproject: Parsed pyproject.toml dict.

    Returns:
        Python version string or None.
    """
    if not pyproject:
        return None

    # Check [project].requires-python (PEP 621)
    project = pyproject.get("project", {})
    if isinstance(project, dict):
        requires_python = project.get("requires-python")
        if isinstance(requires_python, str):
            return requires_python

    # Check [tool.poetry.dependencies].python
    tool = pyproject.get("tool", {})
    if isinstance(tool, dict):
        poetry = tool.get("poetry", {})
        if isinstance(poetry, dict):
            deps = poetry.get("dependencies", {})
            if isinstance(deps, dict):
                python_ver = deps.get("python")
                if isinstance(python_ver, str):
                    return python_ver

    return None


def _detect_rust_version(cargo_toml: dict | None) -> str | None:
    """
    Extract Rust edition from Cargo.toml.

    Args:
        cargo_toml: Parsed Cargo.toml dict.

    Returns:
        Rust edition string or None.
    """
    if not cargo_toml:
        return None

    package = cargo_toml.get("package", {})
    if isinstance(package, dict):
        edition = package.get("edition")
        if isinstance(edition, (str, int)):
            return str(edition)

    return None


# =============================================================================
# Main Detection Function
# =============================================================================


def detect_stack(project_dir: str | Path) -> StackDetectionResult:
    """
    Detect technology stack from manifest files in a codebase.

    Analyzes common manifest files (package.json, requirements.txt, etc.)
    to identify languages, frameworks, and dependencies.

    Args:
        project_dir: Path to the project directory to analyze.

    Returns:
        StackDetectionResult dict containing:
        - languages: List of detected programming languages
        - frameworks: Dict of frameworks by category (frontend, backend, etc.)
        - dependencies: Dict mapping language -> {package: version}
        - runtime: Dict of runtime version information
        - build_tools: List of detected build tools
        - detected_from: List of manifest files that were successfully parsed

    Example:
        >>> result = detect_stack("/path/to/project")
        >>> print(result["languages"])
        ["TypeScript", "Python"]
        >>> print(result["frameworks"]["frontend"])
        ["React", "Tailwind CSS"]
    """
    project_path = Path(project_dir).resolve()

    # Initialize result structure
    result: StackDetectionResult = {
        "languages": [],
        "frameworks": {
            "frontend": [],
            "backend": [],
            "testing": [],
            "styling": [],
            "database": [],
            "build": [],
        },
        "dependencies": {},
        "runtime": {},
        "build_tools": [],
        "detected_from": [],
    }

    if not project_path.exists() or not project_path.is_dir():
        logger.warning("Project directory does not exist: %s", project_path)
        return result

    # ==========================================================================
    # Node.js / JavaScript / TypeScript Detection
    # ==========================================================================

    package_json = _parse_package_json(project_path)
    if package_json:
        result["detected_from"].append("package.json")

        # Detect language (TypeScript vs JavaScript)
        deps = {
            **package_json.get("dependencies", {}),
            **package_json.get("devDependencies", {}),
        }
        if "typescript" in deps or (project_path / "tsconfig.json").exists():
            if "TypeScript" not in result["languages"]:
                result["languages"].append("TypeScript")
        else:
            if "JavaScript" not in result["languages"]:
                result["languages"].append("JavaScript")

        # Detect frameworks
        node_frameworks, all_deps = _detect_node_frameworks(package_json)
        _merge_frameworks(result["frameworks"], node_frameworks)

        # Store dependencies
        result["dependencies"]["node"] = all_deps

        # Detect runtime version
        node_ver = _detect_node_version(package_json)
        if node_ver:
            result["runtime"]["node"] = node_ver

        # Detect build tools from scripts
        scripts = package_json.get("scripts", {})
        if isinstance(scripts, dict):
            if "vite" in str(scripts) or "vite" in deps:
                if "Vite" not in result["build_tools"]:
                    result["build_tools"].append("Vite")
            if "webpack" in str(scripts) or "webpack" in deps:
                if "Webpack" not in result["build_tools"]:
                    result["build_tools"].append("Webpack")
            if "turbo" in str(scripts) or "turbo" in deps:
                if "Turborepo" not in result["build_tools"]:
                    result["build_tools"].append("Turborepo")

        # Add npm as build tool
        if "npm" not in result["build_tools"]:
            result["build_tools"].append("npm")

    # ==========================================================================
    # Python Detection
    # ==========================================================================

    # Parse requirements.txt
    requirements = _parse_requirements_txt(project_path)
    if requirements:
        result["detected_from"].append("requirements.txt")
        if "Python" not in result["languages"]:
            result["languages"].append("Python")

        python_frameworks = _detect_python_frameworks(requirements)
        _merge_frameworks(result["frameworks"], python_frameworks)

        result["dependencies"]["python"] = requirements

        if "pip" not in result["build_tools"]:
            result["build_tools"].append("pip")

    # Parse pyproject.toml
    pyproject = _parse_pyproject_toml(project_path)
    if pyproject:
        result["detected_from"].append("pyproject.toml")
        if "Python" not in result["languages"]:
            result["languages"].append("Python")

        # Extract dependencies from pyproject.toml
        pyproject_deps: dict[str, str] = {}

        # PEP 621 format: [project].dependencies
        project_section = pyproject.get("project", {})
        if isinstance(project_section, dict):
            deps_list = project_section.get("dependencies", [])
            if isinstance(deps_list, list):
                for dep in deps_list:
                    if isinstance(dep, str):
                        # Parse "package>=1.0" format
                        match = re.match(r"([a-zA-Z0-9][-a-zA-Z0-9._]*)(.*)$", dep)
                        if match:
                            pyproject_deps[match.group(1).lower()] = (
                                match.group(2) or "*"
                            )

        # Poetry format: [tool.poetry.dependencies]
        tool_section = pyproject.get("tool", {})
        if isinstance(tool_section, dict):
            poetry = tool_section.get("poetry", {})
            if isinstance(poetry, dict):
                deps = poetry.get("dependencies", {})
                if isinstance(deps, dict):
                    for name, ver in deps.items():
                        if name.lower() != "python":
                            if isinstance(ver, str):
                                pyproject_deps[name.lower()] = ver
                            elif isinstance(ver, dict):
                                pyproject_deps[name.lower()] = ver.get("version", "*")

        if pyproject_deps:
            # Merge with existing python dependencies
            if "python" not in result["dependencies"]:
                result["dependencies"]["python"] = {}
            result["dependencies"]["python"].update(pyproject_deps)

            python_frameworks = _detect_python_frameworks(pyproject_deps)
            _merge_frameworks(result["frameworks"], python_frameworks)

        # Detect Python version
        python_ver = _detect_python_version(pyproject)
        if python_ver:
            result["runtime"]["python"] = python_ver

        # Detect Poetry
        if "poetry" in pyproject.get("tool", {}):
            if "Poetry" not in result["build_tools"]:
                result["build_tools"].append("Poetry")

    # ==========================================================================
    # Rust Detection
    # ==========================================================================

    cargo_toml = _parse_cargo_toml(project_path)
    if cargo_toml:
        result["detected_from"].append("Cargo.toml")
        if "Rust" not in result["languages"]:
            result["languages"].append("Rust")

        # Extract dependencies
        rust_deps: dict[str, str] = {}
        dependencies = cargo_toml.get("dependencies", {})
        if isinstance(dependencies, dict):
            for name, ver in dependencies.items():
                if isinstance(ver, str):
                    rust_deps[name] = ver
                elif isinstance(ver, dict):
                    rust_deps[name] = ver.get("version", "*")

        if rust_deps:
            result["dependencies"]["rust"] = rust_deps

        # Detect Rust edition
        rust_ver = _detect_rust_version(cargo_toml)
        if rust_ver:
            result["runtime"]["rust"] = rust_ver

        if "Cargo" not in result["build_tools"]:
            result["build_tools"].append("Cargo")

    # ==========================================================================
    # Go Detection
    # ==========================================================================

    go_modules = _parse_go_mod(project_path)
    if go_modules:
        result["detected_from"].append("go.mod")
        if "Go" not in result["languages"]:
            result["languages"].append("Go")

        # Extract Go version
        if "go" in go_modules:
            result["runtime"]["go"] = go_modules.pop("go")

        if go_modules:
            result["dependencies"]["go"] = go_modules

        if "Go" not in result["build_tools"]:
            result["build_tools"].append("Go")

    # ==========================================================================
    # PHP Detection
    # ==========================================================================

    composer_json = _parse_composer_json(project_path)
    if composer_json:
        result["detected_from"].append("composer.json")
        if "PHP" not in result["languages"]:
            result["languages"].append("PHP")

        # Extract dependencies
        php_deps: dict[str, str] = {}
        require = composer_json.get("require", {})
        if isinstance(require, dict):
            for name, ver in require.items():
                if name != "php":
                    php_deps[name] = ver
                else:
                    result["runtime"]["php"] = ver

        require_dev = composer_json.get("require-dev", {})
        if isinstance(require_dev, dict):
            php_deps.update(require_dev)

        if php_deps:
            result["dependencies"]["php"] = php_deps
            php_frameworks = _detect_php_frameworks(php_deps)
            _merge_frameworks(result["frameworks"], php_frameworks)

        if "Composer" not in result["build_tools"]:
            result["build_tools"].append("Composer")

    # ==========================================================================
    # Ruby Detection
    # ==========================================================================

    gems = _parse_gemfile(project_path)
    if gems:
        result["detected_from"].append("Gemfile")
        if "Ruby" not in result["languages"]:
            result["languages"].append("Ruby")

        result["dependencies"]["ruby"] = gems

        ruby_frameworks = _detect_ruby_frameworks(gems)
        _merge_frameworks(result["frameworks"], ruby_frameworks)

        if "Bundler" not in result["build_tools"]:
            result["build_tools"].append("Bundler")

    # ==========================================================================
    # Java Detection
    # ==========================================================================

    maven_deps = _parse_pom_xml(project_path)
    if maven_deps:
        result["detected_from"].append("pom.xml")
        if "Java" not in result["languages"]:
            result["languages"].append("Java")

        result["dependencies"]["java"] = maven_deps

        if "Maven" not in result["build_tools"]:
            result["build_tools"].append("Maven")

    gradle_deps = _parse_build_gradle(project_path)
    if gradle_deps:
        gradle_file = (
            "build.gradle.kts"
            if (project_path / "build.gradle.kts").exists()
            else "build.gradle"
        )
        result["detected_from"].append(gradle_file)

        # Could be Java or Kotlin
        if (project_path / "build.gradle.kts").exists():
            if "Kotlin" not in result["languages"]:
                result["languages"].append("Kotlin")
        if "Java" not in result["languages"]:
            result["languages"].append("Java")

        # Merge with existing Java dependencies
        if "java" not in result["dependencies"]:
            result["dependencies"]["java"] = {}
        result["dependencies"]["java"].update(gradle_deps)

        if "Gradle" not in result["build_tools"]:
            result["build_tools"].append("Gradle")

    # ==========================================================================
    # C# / .NET Detection
    # ==========================================================================

    nuget_packages = _parse_csproj(project_path)
    if nuget_packages:
        result["detected_from"].append("*.csproj")
        if "C#" not in result["languages"]:
            result["languages"].append("C#")

        result["dependencies"]["dotnet"] = nuget_packages

        if "dotnet" not in result["build_tools"]:
            result["build_tools"].append("dotnet")

    logger.info(
        "Stack detection complete for %s: %d languages, %d manifest files",
        project_path.name,
        len(result["languages"]),
        len(result["detected_from"]),
    )

    return result
