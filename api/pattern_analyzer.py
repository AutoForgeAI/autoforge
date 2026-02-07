"""
Pattern Analyzer
================

Analyzes codebases to detect architecture patterns, layers, entry points,
and common design patterns. This is used by AutoForge to understand
the structure of existing projects.

Supported Architecture Patterns:
- MVC (Model-View-Controller)
- Clean Architecture (domain, application, infrastructure, presentation)
- Hexagonal Architecture (ports and adapters)
- Component-based (self-contained modules)
- Microservices (multiple independent services)
- Monolith (single unified application)

Detection Approach:
1. Directory structure analysis for layer identification
2. File naming convention detection
3. Code pattern scanning for design patterns
4. Entry point identification
"""

import logging
import re
from pathlib import Path
from typing import TypedDict

logger = logging.getLogger(__name__)


# =============================================================================
# Type Definitions
# =============================================================================


class LayerInfo(TypedDict):
    """Information about an architectural layer."""

    name: str
    directories: list[str]
    description: str


class EntryPointInfo(TypedDict):
    """Information about an application entry point."""

    file: str
    type: str  # "application", "api", "cli", "test", "web"


class PatternAnalysisResult(TypedDict):
    """Complete result from pattern analysis."""

    architecture_pattern: str
    layers: list[LayerInfo]
    entry_points: list[EntryPointInfo]
    data_flow: list[str]
    patterns_detected: list[str]
    confidence: float


class _LayerPatternConfig(TypedDict):
    """Internal configuration for layer pattern matching."""

    directories: list[str]
    description: str


# =============================================================================
# Directory Pattern Definitions
# =============================================================================

# Patterns that indicate MVC architecture
MVC_PATTERNS = {
    "models": ["models", "model", "entities", "entity"],
    "views": ["views", "view", "templates", "template", "pages"],
    "controllers": ["controllers", "controller", "handlers", "handler"],
}

# Patterns that indicate Clean Architecture
CLEAN_ARCHITECTURE_PATTERNS = {
    "domain": ["domain", "core", "entities", "business"],
    "application": ["application", "use_cases", "usecases", "use-cases", "services"],
    "infrastructure": ["infrastructure", "infra", "adapters", "external"],
    "presentation": ["presentation", "ui", "web", "api", "interfaces"],
}

# Patterns that indicate Hexagonal Architecture (Ports & Adapters)
HEXAGONAL_PATTERNS = {
    "ports": ["ports", "interfaces", "contracts"],
    "adapters": ["adapters", "adapter", "driven", "driving"],
    "core": ["core", "domain", "application"],
}

# Common layer directory patterns
LAYER_PATTERNS: dict[str, _LayerPatternConfig] = {
    "presentation": {
        "directories": [
            "components",
            "views",
            "pages",
            "templates",
            "ui",
            "presentation",
            "screens",
            "layouts",
            "widgets",
            "frontend",
        ],
        "description": "UI components and presentation logic",
    },
    "business": {
        "directories": [
            "services",
            "domain",
            "use_cases",
            "usecases",
            "use-cases",
            "business",
            "core",
            "application",
            "logic",
            "features",
        ],
        "description": "Business logic and domain rules",
    },
    "data": {
        "directories": [
            "repositories",
            "repository",
            "data",
            "database",
            "db",
            "api",
            "dal",
            "persistence",
            "storage",
            "models",
            "entities",
            "infrastructure",
        ],
        "description": "Data access and persistence",
    },
    "shared": {
        "directories": ["utils", "utilities", "helpers", "common", "shared", "lib", "tools", "support"],
        "description": "Shared utilities and helpers",
    },
    "config": {
        "directories": ["config", "configuration", "settings", "conf", "setup"],
        "description": "Configuration and settings",
    },
}

# Entry point file patterns
ENTRY_POINT_PATTERNS = [
    # Application entry points
    (r"^main\.(py|ts|js|go|rs|java|rb)$", "application"),
    (r"^app\.(py|ts|js)$", "application"),
    (r"^index\.(py|ts|js|tsx|jsx)$", "application"),
    (r"^__main__\.py$", "application"),
    (r"^server\.(py|ts|js|go)$", "application"),
    (r"^start\.(py|ts|js|sh|bat)$", "application"),
    (r"^run\.(py|ts|js|sh|bat)$", "application"),
    # API entry points
    (r"^routes?\.(py|ts|js)$", "api"),
    (r"^router\.(py|ts|js)$", "api"),
    (r"^api\.(py|ts|js)$", "api"),
    (r"^endpoints?\.(py|ts|js)$", "api"),
    # CLI entry points
    (r"^cli\.(py|ts|js)$", "cli"),
    (r"^cmd\.(py|ts|js|go)$", "cli"),
    (r"^command\.(py|ts|js)$", "cli"),
    # Web entry points
    (r"^App\.(tsx|jsx|vue|svelte)$", "web"),
    (r"^_app\.(tsx|jsx)$", "web"),
    (r"^layout\.(tsx|jsx)$", "web"),
    (r"^root\.(tsx|jsx)$", "web"),
    # Test entry points
    (r"^test_.*\.(py|ts|js)$", "test"),
    (r"^.*\.test\.(ts|js|tsx|jsx)$", "test"),
    (r"^.*\.spec\.(ts|js|tsx|jsx)$", "test"),
    (r"^conftest\.py$", "test"),
]

# Design pattern indicators in code
# These are simple heuristics based on naming conventions
DESIGN_PATTERN_INDICATORS = {
    "Repository": [
        r"class\s+\w+Repository",
        r"interface\s+\w+Repository",
        r"Repository\s*[<(]",
        r"_repository\s*[=:]",
    ],
    "Factory": [
        r"class\s+\w+Factory",
        r"interface\s+\w+Factory",
        r"Factory\s*[<(]",
        r"create\w+\s*\(",
        r"def\s+create_",
    ],
    "Singleton": [
        r"_instance\s*=\s*None",
        r"getInstance\s*\(",
        r"@singleton",
        r"class\s+\w+.*Singleton",
    ],
    "Observer": [
        r"subscribe\s*\(",
        r"unsubscribe\s*\(",
        r"notify\s*\(",
        r"addEventListener",
        r"removeEventListener",
        r"on\w+Changed",
        r"Observable",
        r"Observer",
    ],
    "Strategy": [
        r"class\s+\w+Strategy",
        r"interface\s+\w+Strategy",
        r"Strategy\s*[<(]",
        r"set_?[Ss]trategy",
    ],
    "Decorator": [
        r"class\s+\w+Decorator",
        r"@\w+",  # Python decorators
        r"Decorator\s*[<(]",
    ],
    "Adapter": [
        r"class\s+\w+Adapter",
        r"interface\s+\w+Adapter",
        r"Adapter\s*[<(]",
    ],
    "Facade": [
        r"class\s+\w+Facade",
        r"Facade\s*[<(]",
    ],
    "Builder": [
        r"class\s+\w+Builder",
        r"Builder\s*[<(]",
        r"\.build\s*\(\)",
        r"with_\w+\s*\(",
    ],
    "Command": [
        r"class\s+\w+Command",
        r"execute\s*\(",
        r"Command\s*[<(]",
    ],
    "Middleware": [
        r"middleware",
        r"use\s*\(\s*\w+Middleware",
        r"app\.use\s*\(",
    ],
    "Provider": [
        r"class\s+\w+Provider",
        r"Provider\s*[<(]",
        r"provide\s*\(",
    ],
    "Service": [
        r"class\s+\w+Service",
        r"Service\s*[<(]",
        r"@service",
        r"_service\s*[=:]",
    ],
    "Controller": [
        r"class\s+\w+Controller",
        r"Controller\s*[<(]",
        r"@controller",
    ],
}


# =============================================================================
# Analysis Functions
# =============================================================================


def _get_all_directories(project_dir: Path, max_depth: int = 4) -> list[str]:
    """
    Get all directory names within the project, limited by depth.

    Excludes common non-source directories like node_modules, venv, etc.

    Args:
        project_dir: Root directory to scan.
        max_depth: Maximum directory depth to traverse.

    Returns:
        List of relative directory paths from project root.
    """
    excluded_dirs = {
        "node_modules",
        ".git",
        "__pycache__",
        ".pytest_cache",
        "venv",
        ".venv",
        "env",
        ".env",
        "dist",
        "build",
        ".next",
        ".nuxt",
        "coverage",
        ".nyc_output",
        "target",
        ".cargo",
        ".idea",
        ".vscode",
        ".vs",
        "bin",
        "obj",
        ".gradle",
        "vendor",
        ".bundle",
        "packages",
        ".dart_tool",
        ".pub-cache",
    }

    directories: list[str] = []

    def scan_dir(current: Path, depth: int) -> None:
        if depth > max_depth:
            return

        try:
            for item in current.iterdir():
                if item.is_dir() and item.name not in excluded_dirs:
                    rel_path = str(item.relative_to(project_dir))
                    # Normalize to forward slashes for consistency
                    rel_path = rel_path.replace("\\", "/")
                    directories.append(rel_path)
                    scan_dir(item, depth + 1)
        except PermissionError:
            logger.debug("Permission denied accessing %s", current)
        except OSError as e:
            logger.debug("Error scanning directory %s: %s", current, e)

    scan_dir(project_dir, 0)
    return directories


def _get_source_files(
    project_dir: Path,
    extensions: tuple[str, ...] | None = None,
    max_files: int = 500,
) -> list[Path]:
    """
    Get source files in the project for pattern analysis.

    Args:
        project_dir: Root directory to scan.
        extensions: File extensions to include. Defaults to common source extensions.
        max_files: Maximum number of files to return (for performance).

    Returns:
        List of file paths.
    """
    if extensions is None:
        extensions = (
            ".py",
            ".ts",
            ".tsx",
            ".js",
            ".jsx",
            ".java",
            ".kt",
            ".go",
            ".rs",
            ".rb",
            ".php",
            ".cs",
            ".swift",
            ".vue",
            ".svelte",
        )

    excluded_dirs = {
        "node_modules",
        ".git",
        "__pycache__",
        ".pytest_cache",
        "venv",
        ".venv",
        "env",
        ".env",
        "dist",
        "build",
        ".next",
        ".nuxt",
        "coverage",
        ".nyc_output",
        "target",
        ".cargo",
        ".idea",
        ".vscode",
        ".vs",
        "bin",
        "obj",
        ".gradle",
        "vendor",
        ".bundle",
        "packages",
        ".dart_tool",
        ".pub-cache",
    }

    files: list[Path] = []

    def scan_dir(current: Path) -> None:
        if len(files) >= max_files:
            return

        try:
            for item in current.iterdir():
                if len(files) >= max_files:
                    return

                if item.is_dir():
                    if item.name not in excluded_dirs:
                        scan_dir(item)
                elif item.is_file() and item.suffix.lower() in extensions:
                    files.append(item)
        except PermissionError:
            logger.debug("Permission denied accessing %s", current)
        except OSError as e:
            logger.debug("Error scanning directory %s: %s", current, e)

    scan_dir(project_dir)
    return files


def _detect_layers(directories: list[str]) -> list[LayerInfo]:
    """
    Detect architectural layers from directory structure.

    Args:
        directories: List of relative directory paths.

    Returns:
        List of detected layers with their directories.
    """
    layers: list[LayerInfo] = []

    for layer_name, layer_config in LAYER_PATTERNS.items():
        matching_dirs = []
        for dir_path in directories:
            dir_name = dir_path.split("/")[-1].lower()
            if dir_name in layer_config["directories"]:
                matching_dirs.append(dir_path)

        if matching_dirs:
            layers.append(
                {
                    "name": layer_name,
                    "directories": matching_dirs,
                    "description": layer_config["description"],
                }
            )

    return layers


def _detect_entry_points(project_dir: Path) -> list[EntryPointInfo]:
    """
    Detect application entry points in the project.

    Args:
        project_dir: Root directory to scan.

    Returns:
        List of detected entry points with their types.
    """
    entry_points: list[EntryPointInfo] = []
    seen_files: set[str] = set()

    # Common directories where entry points might be
    search_dirs = [
        project_dir,
        project_dir / "src",
        project_dir / "app",
        project_dir / "lib",
        project_dir / "cmd",
        project_dir / "bin",
        project_dir / "server",
        project_dir / "api",
    ]

    for search_dir in search_dirs:
        if not search_dir.exists():
            continue

        try:
            for item in search_dir.iterdir():
                if not item.is_file():
                    continue

                rel_path = str(item.relative_to(project_dir)).replace("\\", "/")
                if rel_path in seen_files:
                    continue

                for pattern, entry_type in ENTRY_POINT_PATTERNS:
                    if re.match(pattern, item.name, re.IGNORECASE):
                        entry_points.append(
                            {
                                "file": rel_path,
                                "type": entry_type,
                            }
                        )
                        seen_files.add(rel_path)
                        break

        except PermissionError:
            logger.debug("Permission denied accessing %s", search_dir)
        except OSError as e:
            logger.debug("Error scanning directory %s: %s", search_dir, e)

    # Deduplicate, preferring application over other types
    type_priority = {"application": 0, "api": 1, "web": 2, "cli": 3, "test": 4}
    entry_points.sort(key=lambda ep: type_priority.get(ep["type"], 99))

    return entry_points


def _detect_design_patterns(
    project_dir: Path,
    source_files: list[Path],
    sample_size: int = 100,
) -> list[str]:
    """
    Detect design patterns used in the codebase.

    Samples source files and searches for pattern indicators
    using regex matching on naming conventions and code structure.

    Args:
        project_dir: Root directory of the project.
        source_files: List of source file paths to analyze.
        sample_size: Maximum number of files to sample.

    Returns:
        List of detected design pattern names.
    """
    detected_patterns: set[str] = set()

    # Sample files if there are too many
    files_to_check = source_files[:sample_size]

    for file_path in files_to_check:
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")

            for pattern_name, indicators in DESIGN_PATTERN_INDICATORS.items():
                if pattern_name in detected_patterns:
                    continue

                for indicator in indicators:
                    if re.search(indicator, content, re.IGNORECASE | re.MULTILINE):
                        detected_patterns.add(pattern_name)
                        break

        except (OSError, PermissionError) as e:
            logger.debug("Error reading %s: %s", file_path, e)
            continue

    return sorted(detected_patterns)


def _score_architecture_pattern(
    directories: list[str],
    layers: list[LayerInfo],
) -> tuple[str, float]:
    """
    Determine the most likely architecture pattern and confidence score.

    Args:
        directories: List of relative directory paths.
        layers: Detected architectural layers.

    Returns:
        Tuple of (pattern_name, confidence_score).
    """
    dir_names = {d.split("/")[-1].lower() for d in directories}

    scores: dict[str, float] = {
        "MVC": 0.0,
        "Clean Architecture": 0.0,
        "Hexagonal": 0.0,
        "Component-based": 0.0,
        "Microservices": 0.0,
        "Monolith": 0.0,
    }

    # Score MVC pattern
    mvc_matches = 0
    for category, patterns in MVC_PATTERNS.items():
        if any(p in dir_names for p in patterns):
            mvc_matches += 1
    scores["MVC"] = mvc_matches / len(MVC_PATTERNS)

    # Score Clean Architecture pattern
    clean_matches = 0
    for category, patterns in CLEAN_ARCHITECTURE_PATTERNS.items():
        if any(p in dir_names for p in patterns):
            clean_matches += 1
    scores["Clean Architecture"] = clean_matches / len(CLEAN_ARCHITECTURE_PATTERNS)

    # Score Hexagonal Architecture pattern
    hex_matches = 0
    for category, patterns in HEXAGONAL_PATTERNS.items():
        if any(p in dir_names for p in patterns):
            hex_matches += 1
    scores["Hexagonal"] = hex_matches / len(HEXAGONAL_PATTERNS)

    # Score Component-based pattern (self-contained modules)
    # Look for components/ directory with multiple subdirectories
    component_indicators = ["components", "modules", "features"]
    has_components = any(p in dir_names for p in component_indicators)
    if has_components:
        # Check if components contain self-contained modules
        component_dirs = [
            d for d in directories if any(d.startswith(ci + "/") or d == ci for ci in component_indicators)
        ]
        if len(component_dirs) > 3:
            scores["Component-based"] = 0.7
        else:
            scores["Component-based"] = 0.4

    # Score Microservices pattern
    # Look for multiple service directories or docker-compose
    service_indicators = ["services", "microservices", "apps"]
    has_services = any(p in dir_names for p in service_indicators)
    if has_services:
        service_dirs = [d for d in directories if any(d.startswith(si + "/") for si in service_indicators)]
        if len(service_dirs) >= 3:
            scores["Microservices"] = 0.8
        else:
            scores["Microservices"] = 0.3

    # Score Monolith (default if nothing else scores high)
    # A monolith typically has a simpler, flatter structure
    if max(scores.values()) < 0.4:
        scores["Monolith"] = 0.5

    # Find the highest scoring pattern
    best_pattern = max(scores.items(), key=lambda x: x[1])
    pattern_name = best_pattern[0]
    confidence = best_pattern[1]

    # If confidence is too low, mark as Unknown
    if confidence < 0.3:
        return "Unknown", confidence

    return pattern_name, confidence


def _generate_data_flow(
    architecture_pattern: str,
    layers: list[LayerInfo],
    entry_points: list[EntryPointInfo],
) -> list[str]:
    """
    Generate data flow descriptions based on detected architecture.

    Args:
        architecture_pattern: Detected architecture pattern.
        layers: Detected architectural layers.
        entry_points: Detected entry points.

    Returns:
        List of data flow descriptions.
    """
    flows: list[str] = []

    layer_names = {layer["name"] for layer in layers}
    has_presentation = "presentation" in layer_names
    has_business = "business" in layer_names
    has_data = "data" in layer_names

    # Generate flow based on architecture pattern
    if architecture_pattern == "MVC":
        flows.append("Request -> Router -> Controller -> Model -> View -> Response")
        if has_data:
            flows.append("Controller -> Service -> Repository -> Database")

    elif architecture_pattern == "Clean Architecture":
        flows.append("Request -> Controller -> Use Case -> Entity -> Repository -> Database")
        flows.append("External -> Adapter -> Port -> Use Case -> Domain Entity")

    elif architecture_pattern == "Hexagonal":
        flows.append("Driving Adapter -> Port -> Application Core -> Port -> Driven Adapter")
        flows.append("HTTP Request -> REST Adapter -> Use Case -> Repository Adapter -> Database")

    elif architecture_pattern == "Component-based":
        flows.append("Parent Component -> Child Component -> Event Handler -> State Update -> Re-render")
        if has_data:
            flows.append("Component -> API Client -> Backend -> Database")

    elif architecture_pattern == "Microservices":
        flows.append("API Gateway -> Service -> Database")
        flows.append("Service A -> Message Queue -> Service B")
        flows.append("Client -> Load Balancer -> Service Instance -> Cache -> Database")

    else:
        # Generic flow based on detected layers
        if has_presentation and has_business and has_data:
            flows.append("UI -> Business Logic -> Data Access -> Storage")
        elif has_presentation and has_business:
            flows.append("UI -> Business Logic -> External API")
        elif has_business and has_data:
            flows.append("Request -> Service -> Repository -> Database")
        else:
            flows.append("Input -> Processing -> Output")

    # Add entry point specific flows
    api_entry = any(ep["type"] == "api" for ep in entry_points)
    if api_entry and "API" not in " ".join(flows):
        flows.append("HTTP Request -> Router -> Handler -> Response")

    return flows


# =============================================================================
# Main Analysis Function
# =============================================================================


def analyze_patterns(project_dir: str) -> PatternAnalysisResult:
    """
    Analyze codebase for architecture patterns.

    Scans the project directory structure and source files to detect
    architecture patterns, layers, entry points, and design patterns.

    Args:
        project_dir: Path to the project directory to analyze.

    Returns:
        PatternAnalysisResult containing:
        - architecture_pattern: Detected architecture style (MVC, Clean Architecture, etc.)
        - layers: List of architectural layers with their directories
        - entry_points: Application entry points (main files, API routes, etc.)
        - data_flow: Descriptions of how data flows through the system
        - patterns_detected: Design patterns found in the codebase
        - confidence: Confidence score for the architecture detection (0.0-1.0)

    Example:
        >>> result = analyze_patterns("/path/to/project")
        >>> print(result["architecture_pattern"])
        "MVC"
        >>> print(result["layers"])
        [{"name": "presentation", "directories": ["src/views"], "description": "..."}]
    """
    project_path = Path(project_dir).resolve()

    # Initialize result with empty/default values
    result: PatternAnalysisResult = {
        "architecture_pattern": "Unknown",
        "layers": [],
        "entry_points": [],
        "data_flow": [],
        "patterns_detected": [],
        "confidence": 0.0,
    }

    # Validate project directory exists
    if not project_path.exists():
        logger.warning("Project directory does not exist: %s", project_path)
        return result

    if not project_path.is_dir():
        logger.warning("Path is not a directory: %s", project_path)
        return result

    logger.info("Analyzing patterns in %s", project_path)

    # Step 1: Scan directory structure
    directories = _get_all_directories(project_path)
    if not directories:
        logger.debug("No directories found in project")
        # Still try to detect entry points in root
        result["entry_points"] = _detect_entry_points(project_path)
        return result

    logger.debug("Found %d directories", len(directories))

    # Step 2: Detect architectural layers
    result["layers"] = _detect_layers(directories)
    logger.debug("Detected %d layers", len(result["layers"]))

    # Step 3: Detect entry points
    result["entry_points"] = _detect_entry_points(project_path)
    logger.debug("Detected %d entry points", len(result["entry_points"]))

    # Step 4: Determine architecture pattern
    pattern, confidence = _score_architecture_pattern(directories, result["layers"])
    result["architecture_pattern"] = pattern
    result["confidence"] = round(confidence, 2)
    logger.debug("Detected architecture: %s (confidence: %.2f)", pattern, confidence)

    # Step 5: Detect design patterns in source code
    source_files = _get_source_files(project_path)
    if source_files:
        result["patterns_detected"] = _detect_design_patterns(project_path, source_files)
        logger.debug("Detected %d design patterns", len(result["patterns_detected"]))

    # Step 6: Generate data flow descriptions
    result["data_flow"] = _generate_data_flow(
        result["architecture_pattern"],
        result["layers"],
        result["entry_points"],
    )

    logger.info(
        "Pattern analysis complete: %s (%d layers, %d patterns)",
        result["architecture_pattern"],
        len(result["layers"]),
        len(result["patterns_detected"]),
    )

    return result
