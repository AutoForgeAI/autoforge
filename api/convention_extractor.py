"""
Convention Extractor
====================

Extracts coding conventions from codebase analysis by sampling files,
analyzing naming patterns, import styles, documentation, and formatting.

This is used by AutoForge to understand and follow existing project
conventions when generating new code.
"""

import json
import logging
import os
import re
from pathlib import Path
from typing import Literal, TypedDict

# Python 3.11+ has tomllib in the standard library
try:
    import tomllib
except ImportError:
    tomllib = None  # type: ignore[assignment]


logger = logging.getLogger(__name__)


# =============================================================================
# Type Definitions
# =============================================================================


class NamingExamples(TypedDict):
    """Examples of naming conventions found in the codebase."""

    files: list[str]
    functions: list[str]
    classes: list[str]
    constants: list[str]


class NamingConventions(TypedDict):
    """Detected naming conventions."""

    files: Literal["kebab-case", "snake_case", "PascalCase", "camelCase", "mixed"]
    functions: Literal["snake_case", "camelCase", "mixed"]
    classes: Literal["PascalCase", "mixed"]
    constants: Literal["SCREAMING_SNAKE_CASE", "mixed"]
    examples: NamingExamples


class ImportConventions(TypedDict):
    """Detected import conventions."""

    style: Literal["absolute", "relative", "mixed"]
    organization: Literal["grouped", "alphabetical", "unorganized"]
    examples: list[str]


class DocumentationConventions(TypedDict):
    """Detected documentation conventions."""

    docstrings: Literal["numpy", "google", "sphinx", "jsdoc", "none", "mixed"]
    inline_comments: Literal["sparse", "moderate", "heavy"]
    examples: list[str]


class TestingConventions(TypedDict):
    """Detected testing conventions."""

    framework: Literal["pytest", "jest", "vitest", "mocha", "unknown"]
    naming: Literal["test_*", "*.test.*", "*.spec.*", "mixed"]
    location: Literal["same-directory", "tests-folder", "mixed"]


class FormattingConventions(TypedDict):
    """Detected formatting conventions."""

    indentation: Literal["spaces-2", "spaces-4", "tabs", "mixed"]
    line_length: int | Literal["unknown"]
    trailing_commas: bool | Literal["mixed"]


class ConventionResult(TypedDict):
    """Complete convention extraction result."""

    naming: NamingConventions
    imports: ImportConventions
    documentation: DocumentationConventions
    testing: TestingConventions
    formatting: FormattingConventions


# =============================================================================
# Constants
# =============================================================================


# Maximum files to sample for performance
MAX_FILES_TO_SAMPLE = 50

# File extensions to analyze by language
CODE_EXTENSIONS = {
    "python": [".py"],
    "javascript": [".js", ".jsx", ".mjs", ".cjs"],
    "typescript": [".ts", ".tsx"],
    "go": [".go"],
    "rust": [".rs"],
    "java": [".java"],
    "csharp": [".cs"],
    "ruby": [".rb"],
    "php": [".php"],
}

# Directories to exclude from analysis
EXCLUDED_DIRS = {
    "node_modules",
    "venv",
    ".venv",
    "env",
    ".env",
    "__pycache__",
    ".git",
    ".svn",
    "dist",
    "build",
    "target",
    ".next",
    ".nuxt",
    "vendor",
    ".cache",
    "coverage",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "site-packages",
}


# =============================================================================
# Naming Pattern Detection
# =============================================================================


def _is_kebab_case(name: str) -> bool:
    """Check if name uses kebab-case (words separated by hyphens)."""
    return bool(re.match(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$", name))


def _is_snake_case(name: str) -> bool:
    """Check if name uses snake_case (words separated by underscores)."""
    return bool(re.match(r"^[a-z][a-z0-9]*(_[a-z0-9]+)*$", name))


def _is_pascal_case(name: str) -> bool:
    """Check if name uses PascalCase (each word capitalized, no separators)."""
    return bool(re.match(r"^[A-Z][a-zA-Z0-9]*$", name))


def _is_camel_case(name: str) -> bool:
    """Check if name uses camelCase (first word lowercase, rest capitalized)."""
    return bool(re.match(r"^[a-z][a-zA-Z0-9]*$", name)) and any(c.isupper() for c in name)


def _is_screaming_snake_case(name: str) -> bool:
    """Check if name uses SCREAMING_SNAKE_CASE (all caps with underscores)."""
    return bool(re.match(r"^[A-Z][A-Z0-9]*(_[A-Z0-9]+)*$", name))


def _detect_file_naming_convention(
    file_names: list[str],
) -> tuple[Literal["kebab-case", "snake_case", "PascalCase", "camelCase", "mixed"], list[str]]:
    """
    Detect the predominant file naming convention.

    Args:
        file_names: List of file names (without extension) to analyze.

    Returns:
        Tuple of (detected convention, example files).
    """
    if not file_names:
        return "mixed", []

    counts = {"kebab-case": 0, "snake_case": 0, "PascalCase": 0, "camelCase": 0}
    examples: dict[str, list[str]] = {"kebab-case": [], "snake_case": [], "PascalCase": [], "camelCase": []}

    for name in file_names:
        # Skip very short names or names starting with underscore
        if len(name) < 2 or name.startswith("_"):
            continue

        if _is_kebab_case(name):
            counts["kebab-case"] += 1
            if len(examples["kebab-case"]) < 3:
                examples["kebab-case"].append(name)
        elif _is_snake_case(name):
            counts["snake_case"] += 1
            if len(examples["snake_case"]) < 3:
                examples["snake_case"].append(name)
        elif _is_pascal_case(name):
            counts["PascalCase"] += 1
            if len(examples["PascalCase"]) < 3:
                examples["PascalCase"].append(name)
        elif _is_camel_case(name):
            counts["camelCase"] += 1
            if len(examples["camelCase"]) < 3:
                examples["camelCase"].append(name)

    if not any(counts.values()):
        return "mixed", []

    # Find the dominant convention (must be >60% to be considered dominant)
    total = sum(counts.values())
    dominant = max(counts.items(), key=lambda x: x[1])

    if dominant[1] / total >= 0.6:
        return dominant[0], examples[dominant[0]]  # type: ignore[return-value]
    return "mixed", list(examples.values())[0] if examples else []


def _detect_function_naming_convention(
    function_names: list[str],
) -> tuple[Literal["snake_case", "camelCase", "mixed"], list[str]]:
    """
    Detect the predominant function naming convention.

    Args:
        function_names: List of function names to analyze.

    Returns:
        Tuple of (detected convention, example functions).
    """
    if not function_names:
        return "mixed", []

    counts = {"snake_case": 0, "camelCase": 0}
    examples: dict[str, list[str]] = {"snake_case": [], "camelCase": []}

    for name in function_names:
        # Skip dunder methods and single-word names (ambiguous)
        if name.startswith("__") or ("_" not in name and not any(c.isupper() for c in name)):
            continue

        if _is_snake_case(name):
            counts["snake_case"] += 1
            if len(examples["snake_case"]) < 3:
                examples["snake_case"].append(name)
        elif _is_camel_case(name):
            counts["camelCase"] += 1
            if len(examples["camelCase"]) < 3:
                examples["camelCase"].append(name)

    if not any(counts.values()):
        return "mixed", []

    total = sum(counts.values())
    dominant = max(counts.items(), key=lambda x: x[1])

    if dominant[1] / total >= 0.6:
        return dominant[0], examples[dominant[0]]  # type: ignore[return-value]
    return "mixed", list(examples.values())[0] if examples else []


def _detect_class_naming_convention(
    class_names: list[str],
) -> tuple[Literal["PascalCase", "mixed"], list[str]]:
    """
    Detect the predominant class naming convention.

    Args:
        class_names: List of class names to analyze.

    Returns:
        Tuple of (detected convention, example classes).
    """
    if not class_names:
        return "mixed", []

    pascal_count = 0
    examples: list[str] = []

    for name in class_names:
        if _is_pascal_case(name):
            pascal_count += 1
            if len(examples) < 3:
                examples.append(name)

    # Classes are almost universally PascalCase
    if pascal_count / len(class_names) >= 0.8:
        return "PascalCase", examples
    return "mixed", examples


def _detect_constant_naming_convention(
    constant_names: list[str],
) -> tuple[Literal["SCREAMING_SNAKE_CASE", "mixed"], list[str]]:
    """
    Detect the predominant constant naming convention.

    Args:
        constant_names: List of constant names to analyze.

    Returns:
        Tuple of (detected convention, example constants).
    """
    if not constant_names:
        return "mixed", []

    screaming_count = 0
    examples: list[str] = []

    for name in constant_names:
        if _is_screaming_snake_case(name):
            screaming_count += 1
            if len(examples) < 3:
                examples.append(name)

    if constant_names and screaming_count / len(constant_names) >= 0.6:
        return "SCREAMING_SNAKE_CASE", examples
    return "mixed", examples


# =============================================================================
# Code Pattern Extraction
# =============================================================================


def _extract_python_patterns(content: str) -> dict:
    """
    Extract naming patterns from Python code.

    Args:
        content: Python source code content.

    Returns:
        Dict with lists of functions, classes, and constants found.
    """
    functions: list[str] = []
    classes: list[str] = []
    constants: list[str] = []

    # Function definitions
    for match in re.finditer(r"^def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(", content, re.MULTILINE):
        functions.append(match.group(1))

    # Class definitions
    for match in re.finditer(r"^class\s+([a-zA-Z_][a-zA-Z0-9_]*)", content, re.MULTILINE):
        classes.append(match.group(1))

    # Module-level constants (ALL_CAPS assignments)
    for match in re.finditer(r"^([A-Z][A-Z0-9_]*)\s*=", content, re.MULTILINE):
        constants.append(match.group(1))

    return {"functions": functions, "classes": classes, "constants": constants}


def _extract_javascript_patterns(content: str) -> dict:
    """
    Extract naming patterns from JavaScript/TypeScript code.

    Args:
        content: JavaScript/TypeScript source code content.

    Returns:
        Dict with lists of functions, classes, and constants found.
    """
    functions: list[str] = []
    classes: list[str] = []
    constants: list[str] = []

    # Function declarations and expressions
    for match in re.finditer(r"(?:function|const|let|var)\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s*(?:=\s*(?:async\s*)?(?:\([^)]*\)|[a-zA-Z_$][a-zA-Z0-9_$]*)\s*=>|\()", content):
        name = match.group(1)
        # Skip if it's likely a constant (ALL_CAPS)
        if not _is_screaming_snake_case(name):
            functions.append(name)

    # Arrow functions assigned to variables
    for match in re.finditer(r"(?:const|let|var)\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s*=\s*(?:async\s*)?\(", content):
        functions.append(match.group(1))

    # Class declarations
    for match in re.finditer(r"class\s+([a-zA-Z_$][a-zA-Z0-9_$]*)", content):
        classes.append(match.group(1))

    # Constants (const with ALL_CAPS)
    for match in re.finditer(r"const\s+([A-Z][A-Z0-9_]*)\s*=", content):
        constants.append(match.group(1))

    return {"functions": functions, "classes": classes, "constants": constants}


def _extract_go_patterns(content: str) -> dict:
    """
    Extract naming patterns from Go code.

    Args:
        content: Go source code content.

    Returns:
        Dict with lists of functions, types (classes), and constants found.
    """
    functions: list[str] = []
    classes: list[str] = []
    constants: list[str] = []

    # Function declarations
    for match in re.finditer(r"^func\s+(?:\([^)]+\)\s+)?([a-zA-Z_][a-zA-Z0-9_]*)\s*\(", content, re.MULTILINE):
        functions.append(match.group(1))

    # Type declarations (struct, interface)
    for match in re.finditer(r"^type\s+([a-zA-Z_][a-zA-Z0-9_]*)\s+(?:struct|interface)", content, re.MULTILINE):
        classes.append(match.group(1))

    # Constants
    for match in re.finditer(r"^const\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*=", content, re.MULTILINE):
        constants.append(match.group(1))

    return {"functions": functions, "classes": classes, "constants": constants}


# =============================================================================
# Import Analysis
# =============================================================================


def _analyze_python_imports(content: str) -> tuple[list[str], bool, bool]:
    """
    Analyze Python import statements.

    Args:
        content: Python source code content.

    Returns:
        Tuple of (import examples, uses_relative, is_grouped).
    """
    imports: list[str] = []
    relative_imports = 0
    absolute_imports = 0

    for line in content.split("\n"):
        line = line.strip()
        if line.startswith("import ") or line.startswith("from "):
            if len(imports) < 5:
                imports.append(line)

            if line.startswith("from ."):
                relative_imports += 1
            elif line.startswith("from ") or line.startswith("import "):
                absolute_imports += 1

    # Check if imports are grouped (stdlib, third-party, local with blank lines)
    # This is a simplified heuristic
    import_blocks = re.split(r"\n\s*\n", content)
    has_import_groups = sum(1 for block in import_blocks if "import " in block) > 1

    uses_relative = relative_imports > absolute_imports / 3 if absolute_imports else relative_imports > 0

    return imports, uses_relative, has_import_groups


def _analyze_javascript_imports(content: str) -> tuple[list[str], bool, bool]:
    """
    Analyze JavaScript/TypeScript import statements.

    Args:
        content: JavaScript/TypeScript source code content.

    Returns:
        Tuple of (import examples, uses_relative, is_organized).
    """
    imports: list[str] = []
    relative_imports = 0
    absolute_imports = 0

    for line in content.split("\n"):
        line = line.strip()
        if line.startswith("import "):
            if len(imports) < 5:
                imports.append(line)

            # Check for relative imports
            if re.search(r"from\s+['\"]\.\.?/", line):
                relative_imports += 1
            elif re.search(r"from\s+['\"]", line):
                absolute_imports += 1

    uses_relative = relative_imports > absolute_imports / 3 if absolute_imports else relative_imports > 0

    # Check for grouping (node_modules vs local)
    import_section = []
    for line in content.split("\n"):
        if line.strip().startswith("import "):
            import_section.append(line)
        elif import_section and not line.strip():
            break

    is_organized = len(import_section) > 0

    return imports, uses_relative, is_organized


# =============================================================================
# Documentation Analysis
# =============================================================================


def _detect_python_docstring_style(content: str) -> Literal["numpy", "google", "sphinx", "none", "mixed"]:
    """
    Detect the docstring style used in Python code.

    Args:
        content: Python source code content.

    Returns:
        Detected docstring style.
    """
    # Look for docstrings
    docstrings = re.findall(r'"""[\s\S]*?"""', content)

    if not docstrings:
        return "none"

    numpy_indicators = 0
    google_indicators = 0
    sphinx_indicators = 0

    for doc in docstrings:
        # NumPy style: Parameters, Returns, Examples with dashes
        if re.search(r"\n\s*Parameters\s*\n\s*-+", doc) or re.search(r"\n\s*Returns\s*\n\s*-+", doc):
            numpy_indicators += 1

        # Google style: Args:, Returns:, Raises: with indented descriptions
        if re.search(r"\n\s*Args:\s*\n", doc) or re.search(r"\n\s*Returns:\s*\n", doc):
            google_indicators += 1

        # Sphinx style: :param, :returns:, :type:
        if re.search(r":param\s+\w+:", doc) or re.search(r":returns?:", doc):
            sphinx_indicators += 1

    total = numpy_indicators + google_indicators + sphinx_indicators
    if total == 0:
        return "none"

    if numpy_indicators > google_indicators and numpy_indicators > sphinx_indicators:
        return "numpy" if numpy_indicators / total > 0.5 else "mixed"
    if google_indicators > numpy_indicators and google_indicators > sphinx_indicators:
        return "google" if google_indicators / total > 0.5 else "mixed"
    if sphinx_indicators > numpy_indicators and sphinx_indicators > google_indicators:
        return "sphinx" if sphinx_indicators / total > 0.5 else "mixed"

    return "mixed"


def _detect_javascript_doc_style(content: str) -> Literal["jsdoc", "none", "mixed"]:
    """
    Detect the documentation style used in JavaScript/TypeScript code.

    Args:
        content: JavaScript/TypeScript source code content.

    Returns:
        Detected documentation style.
    """
    # Look for JSDoc comments
    jsdoc_comments = re.findall(r"/\*\*[\s\S]*?\*/", content)

    if not jsdoc_comments:
        return "none"

    jsdoc_indicators = 0

    for doc in jsdoc_comments:
        # JSDoc style: @param, @returns, @type
        if re.search(r"@param\s+", doc) or re.search(r"@returns?\s+", doc) or re.search(r"@type\s+", doc):
            jsdoc_indicators += 1

    if jsdoc_indicators / len(jsdoc_comments) > 0.5:
        return "jsdoc"
    return "none" if jsdoc_indicators == 0 else "mixed"


def _count_inline_comments(content: str, is_python: bool) -> Literal["sparse", "moderate", "heavy"]:
    """
    Estimate the density of inline comments.

    Args:
        content: Source code content.
        is_python: True if Python code, False for JavaScript/TypeScript.

    Returns:
        Comment density classification.
    """
    lines = content.split("\n")
    code_lines = 0
    comment_lines = 0

    in_multiline_comment = False

    for line in lines:
        stripped = line.strip()

        # Skip empty lines
        if not stripped:
            continue

        # Handle multiline comments
        if is_python:
            if stripped.startswith('"""') or stripped.startswith("'''"):
                in_multiline_comment = not in_multiline_comment
                continue
        else:
            if "/*" in stripped:
                in_multiline_comment = True
            if "*/" in stripped:
                in_multiline_comment = False
                continue

        if in_multiline_comment:
            continue

        # Count comment lines
        if is_python and stripped.startswith("#"):
            comment_lines += 1
        elif not is_python and stripped.startswith("//"):
            comment_lines += 1
        else:
            code_lines += 1
            # Also count inline comments
            if is_python and "#" in line:
                comment_lines += 1
            elif not is_python and "//" in line:
                comment_lines += 1

    if code_lines == 0:
        return "sparse"

    ratio = comment_lines / code_lines

    if ratio < 0.05:
        return "sparse"
    elif ratio < 0.15:
        return "moderate"
    else:
        return "heavy"


# =============================================================================
# Testing Detection
# =============================================================================


def _detect_testing_conventions(project_dir: Path) -> TestingConventions:
    """
    Detect testing framework and conventions.

    Args:
        project_dir: Path to the project directory.

    Returns:
        TestingConventions dict.
    """
    result: TestingConventions = {
        "framework": "unknown",
        "naming": "mixed",
        "location": "mixed",
    }

    # Check for test framework indicators
    package_json = project_dir / "package.json"
    if package_json.exists():
        try:
            with open(package_json, "r", encoding="utf-8") as f:
                pkg = json.load(f)
                deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}

                if "vitest" in deps:
                    result["framework"] = "vitest"
                elif "jest" in deps:
                    result["framework"] = "jest"
                elif "mocha" in deps:
                    result["framework"] = "mocha"
        except (json.JSONDecodeError, OSError):
            pass

    # Check for pytest
    if (project_dir / "pytest.ini").exists() or (project_dir / "pyproject.toml").exists():
        pyproject = project_dir / "pyproject.toml"
        if pyproject.exists() and tomllib:
            try:
                with pyproject.open("rb") as toml_file:
                    data = tomllib.load(toml_file)
                    if "tool" in data and "pytest" in data["tool"]:
                        result["framework"] = "pytest"
            except Exception:
                pass

        # Also check requirements.txt
        requirements = project_dir / "requirements.txt"
        if requirements.exists():
            try:
                with open(requirements, "r", encoding="utf-8") as f:
                    content = f.read().lower()
                    if "pytest" in content:
                        result["framework"] = "pytest"
            except OSError:
                pass

    # Detect test file naming and location
    test_files_test_prefix = list(project_dir.rglob("test_*.py"))
    test_files_spec = list(project_dir.rglob("*.spec.ts")) + list(project_dir.rglob("*.spec.js"))
    test_files_test_suffix = list(project_dir.rglob("*.test.ts")) + list(project_dir.rglob("*.test.js"))

    # Filter out node_modules
    test_files_test_prefix = [f for f in test_files_test_prefix if "node_modules" not in str(f)]
    test_files_spec = [f for f in test_files_spec if "node_modules" not in str(f)]
    test_files_test_suffix = [f for f in test_files_test_suffix if "node_modules" not in str(f)]

    total_test_files = len(test_files_test_prefix) + len(test_files_spec) + len(test_files_test_suffix)

    if total_test_files > 0:
        if len(test_files_test_prefix) > total_test_files * 0.6:
            result["naming"] = "test_*"
        elif len(test_files_spec) > total_test_files * 0.6:
            result["naming"] = "*.spec.*"
        elif len(test_files_test_suffix) > total_test_files * 0.6:
            result["naming"] = "*.test.*"

    # Detect test location
    has_tests_folder = (project_dir / "tests").exists() or (project_dir / "__tests__").exists()
    has_colocated_tests = any(
        f.parent.name not in ("tests", "__tests__", "test")
        for f in test_files_test_prefix + test_files_spec + test_files_test_suffix
    )

    if has_tests_folder and not has_colocated_tests:
        result["location"] = "tests-folder"
    elif has_colocated_tests and not has_tests_folder:
        result["location"] = "same-directory"

    return result


# =============================================================================
# Formatting Detection
# =============================================================================


def _detect_indentation(content: str) -> Literal["spaces-2", "spaces-4", "tabs", "mixed"]:
    """
    Detect the indentation style used.

    Args:
        content: Source code content.

    Returns:
        Detected indentation style.
    """
    lines = content.split("\n")
    space_2_count = 0
    space_4_count = 0
    tab_count = 0

    for line in lines:
        if not line or not line[0].isspace():
            continue

        # Count leading whitespace
        leading = len(line) - len(line.lstrip())

        if line[0] == "\t":
            tab_count += 1
        elif leading == 2 or (leading > 2 and leading % 2 == 0 and leading % 4 != 0):
            space_2_count += 1
        elif leading >= 4 and leading % 4 == 0:
            space_4_count += 1

    total = space_2_count + space_4_count + tab_count
    if total == 0:
        return "spaces-4"  # Default assumption

    if tab_count > total * 0.6:
        return "tabs"
    elif space_2_count > total * 0.6:
        return "spaces-2"
    elif space_4_count > total * 0.6:
        return "spaces-4"
    return "mixed"


def _detect_line_length_from_config(project_dir: Path) -> int | Literal["unknown"]:
    """
    Detect configured line length from formatter config files.

    Args:
        project_dir: Path to the project directory.

    Returns:
        Configured line length or "unknown".
    """
    # Check pyproject.toml for ruff/black/flake8 settings
    pyproject = project_dir / "pyproject.toml"
    if pyproject.exists() and tomllib:
        try:
            with open(pyproject, "rb") as f:
                data = tomllib.load(f)

            # Check ruff
            if "tool" in data and "ruff" in data["tool"]:
                line_length = data["tool"]["ruff"].get("line-length")
                if isinstance(line_length, int):
                    return line_length

            # Check black
            if "tool" in data and "black" in data["tool"]:
                line_length = data["tool"]["black"].get("line-length")
                if isinstance(line_length, int):
                    return line_length
        except Exception:
            pass

    # Check .prettierrc or prettier.config.js
    for prettier_file in [".prettierrc", ".prettierrc.json", ".prettierrc.js"]:
        prettier_path = project_dir / prettier_file
        if prettier_path.exists() and prettier_file.endswith(".json"):
            try:
                with open(prettier_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    print_width = data.get("printWidth")
                    if isinstance(print_width, int):
                        return print_width
            except (json.JSONDecodeError, OSError):
                pass

    # Check editorconfig
    editorconfig = project_dir / ".editorconfig"
    if editorconfig.exists():
        try:
            with open(editorconfig, "r", encoding="utf-8") as f:
                content = f.read()
                match = re.search(r"max_line_length\s*=\s*(\d+)", content)
                if match:
                    return int(match.group(1))
        except OSError:
            pass

    return "unknown"


def _detect_trailing_commas(content: str) -> bool | Literal["mixed"]:
    """
    Detect trailing comma usage in arrays and objects.

    Args:
        content: Source code content.

    Returns:
        True if trailing commas used, False if not, "mixed" if inconsistent.
    """
    # Look for array/object patterns ending with comma before closing bracket
    with_trailing = len(re.findall(r",\s*[\]\}]", content))
    without_trailing = len(re.findall(r"[^\s,]\s*[\]\}]", content))

    total = with_trailing + without_trailing
    if total < 5:
        return "mixed"

    if with_trailing / total > 0.7:
        return True
    elif without_trailing / total > 0.7:
        return False
    return "mixed"


# =============================================================================
# File Sampling
# =============================================================================


def _sample_files(project_dir: Path, max_files: int = MAX_FILES_TO_SAMPLE) -> list[Path]:
    """
    Sample files from the project for analysis.

    Samples files from different directories to get a representative set.

    Args:
        project_dir: Path to the project directory.
        max_files: Maximum number of files to return.

    Returns:
        List of file paths to analyze.
    """
    all_files: list[Path] = []
    all_extensions = []
    for exts in CODE_EXTENSIONS.values():
        all_extensions.extend(exts)

    # Walk directory tree
    for root, dirs, files in os.walk(project_dir):
        # Skip excluded directories
        dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS]

        for file in files:
            file_path = Path(root) / file
            if file_path.suffix in all_extensions:
                all_files.append(file_path)

    # Sort by directory depth to get variety
    all_files.sort(key=lambda p: (len(p.parts), p.name))

    # Sample evenly across the list
    if len(all_files) <= max_files:
        return all_files

    step = len(all_files) // max_files
    sampled = [all_files[i * step] for i in range(max_files)]
    return sampled


# =============================================================================
# Main Extraction Function
# =============================================================================


def extract_conventions(project_dir: str) -> ConventionResult:
    """
    Extract coding conventions from codebase analysis.

    Analyzes files in the project directory to detect naming conventions,
    import styles, documentation patterns, testing setup, and formatting.

    Args:
        project_dir: Path to the project directory to analyze.

    Returns:
        ConventionResult dict containing:
        - naming: File, function, class, and constant naming conventions
        - imports: Import style and organization
        - documentation: Docstring style and comment density
        - testing: Testing framework and conventions
        - formatting: Indentation, line length, trailing commas
    """
    project_path = Path(project_dir).resolve()

    # Initialize result with defaults
    result: ConventionResult = {
        "naming": {
            "files": "mixed",
            "functions": "mixed",
            "classes": "mixed",
            "constants": "mixed",
            "examples": {"files": [], "functions": [], "classes": [], "constants": []},
        },
        "imports": {
            "style": "mixed",
            "organization": "unorganized",
            "examples": [],
        },
        "documentation": {
            "docstrings": "none",
            "inline_comments": "sparse",
            "examples": [],
        },
        "testing": {
            "framework": "unknown",
            "naming": "mixed",
            "location": "mixed",
        },
        "formatting": {
            "indentation": "spaces-4",
            "line_length": "unknown",
            "trailing_commas": "mixed",
        },
    }

    if not project_path.exists() or not project_path.is_dir():
        logger.warning("Project directory does not exist: %s", project_path)
        return result

    # Sample files for analysis
    sampled_files = _sample_files(project_path)

    if not sampled_files:
        logger.info("No code files found in %s", project_path)
        return result

    logger.debug("Analyzing %d files for conventions", len(sampled_files))

    # Collect patterns from all files
    all_file_names: list[str] = []
    all_functions: list[str] = []
    all_classes: list[str] = []
    all_constants: list[str] = []
    all_imports: list[str] = []
    relative_import_count = 0
    absolute_import_count = 0
    grouped_import_count = 0
    total_import_files = 0
    docstring_examples: list[str] = []
    comment_densities: list[Literal["sparse", "moderate", "heavy"]] = []
    indentation_votes: list[Literal["spaces-2", "spaces-4", "tabs", "mixed"]] = []
    trailing_comma_votes: list[bool | Literal["mixed"]] = []

    # Detect primary language
    python_files = [f for f in sampled_files if f.suffix == ".py"]
    js_ts_files = [f for f in sampled_files if f.suffix in (".js", ".jsx", ".ts", ".tsx")]

    is_python_project = len(python_files) >= len(js_ts_files)

    for file_path in sampled_files:
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except OSError:
            continue

        # Collect file names
        stem = file_path.stem
        if stem and not stem.startswith("."):
            all_file_names.append(stem)

        # Extract patterns based on file type
        if file_path.suffix == ".py":
            patterns = _extract_python_patterns(content)
            imports, uses_relative, is_grouped = _analyze_python_imports(content)

            # Detect docstring style
            docstring_style = _detect_python_docstring_style(content)
            if docstring_style not in ("none", "mixed") and len(docstring_examples) < 3:
                # Extract a sample docstring
                docs = re.findall(r'"""[\s\S]*?"""', content)
                if docs:
                    docstring_examples.append(docs[0][:200] + "..." if len(docs[0]) > 200 else docs[0])

        elif file_path.suffix in (".js", ".jsx", ".ts", ".tsx"):
            patterns = _extract_javascript_patterns(content)
            imports, uses_relative, is_grouped = _analyze_javascript_imports(content)

            # Detect JSDoc style
            doc_style = _detect_javascript_doc_style(content)
            if doc_style == "jsdoc" and len(docstring_examples) < 3:
                docs = re.findall(r"/\*\*[\s\S]*?\*/", content)
                if docs:
                    docstring_examples.append(docs[0][:200] + "..." if len(docs[0]) > 200 else docs[0])

        elif file_path.suffix == ".go":
            patterns = _extract_go_patterns(content)
            imports = []
            uses_relative = False
            is_grouped = False
        else:
            continue

        # Aggregate patterns
        all_functions.extend(patterns["functions"])
        all_classes.extend(patterns["classes"])
        all_constants.extend(patterns["constants"])
        all_imports.extend(imports)

        if imports:
            total_import_files += 1
            if uses_relative:
                relative_import_count += 1
            else:
                absolute_import_count += 1
            if is_grouped:
                grouped_import_count += 1

        # Analyze comments and formatting
        comment_densities.append(_count_inline_comments(content, file_path.suffix == ".py"))
        indentation_votes.append(_detect_indentation(content))
        trailing_comma_votes.append(_detect_trailing_commas(content))

    # Analyze collected patterns
    # File naming
    file_conv, file_examples = _detect_file_naming_convention(all_file_names)
    result["naming"]["files"] = file_conv
    result["naming"]["examples"]["files"] = file_examples

    # Function naming
    func_conv, func_examples = _detect_function_naming_convention(all_functions)
    result["naming"]["functions"] = func_conv
    result["naming"]["examples"]["functions"] = func_examples

    # Class naming
    class_conv, class_examples = _detect_class_naming_convention(all_classes)
    result["naming"]["classes"] = class_conv
    result["naming"]["examples"]["classes"] = class_examples

    # Constant naming
    const_conv, const_examples = _detect_constant_naming_convention(all_constants)
    result["naming"]["constants"] = const_conv
    result["naming"]["examples"]["constants"] = const_examples

    # Import conventions
    if total_import_files > 0:
        if relative_import_count > absolute_import_count * 0.6:
            result["imports"]["style"] = "relative"
        elif absolute_import_count > relative_import_count * 0.6:
            result["imports"]["style"] = "absolute"

        if grouped_import_count > total_import_files * 0.6:
            result["imports"]["organization"] = "grouped"
        elif grouped_import_count < total_import_files * 0.2:
            result["imports"]["organization"] = "unorganized"
        else:
            result["imports"]["organization"] = "alphabetical"

    result["imports"]["examples"] = all_imports[:5]

    # Documentation conventions
    if is_python_project:
        # Aggregate docstring detection across all Python files
        docstring_styles: list[str] = []
        for file_path in python_files[:20]:  # Sample up to 20 Python files
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    style = _detect_python_docstring_style(content)
                    if style != "none":
                        docstring_styles.append(style)
            except OSError:
                continue

        if docstring_styles:
            from collections import Counter
            style_counts = Counter(docstring_styles)
            most_common = style_counts.most_common(1)[0]
            if most_common[1] / len(docstring_styles) > 0.5:
                result["documentation"]["docstrings"] = most_common[0]  # type: ignore[typeddict-item]
            else:
                result["documentation"]["docstrings"] = "mixed"
    else:
        # JavaScript/TypeScript
        jsdoc_count = sum(1 for f in js_ts_files[:20] if _detect_javascript_doc_style(
            open(f, "r", encoding="utf-8", errors="ignore").read() if f.exists() else ""
        ) == "jsdoc")
        if jsdoc_count > len(js_ts_files[:20]) * 0.5:
            result["documentation"]["docstrings"] = "jsdoc"

    result["documentation"]["examples"] = docstring_examples[:3]

    # Comment density
    if comment_densities:
        from collections import Counter
        density_counts = Counter(comment_densities)
        result["documentation"]["inline_comments"] = density_counts.most_common(1)[0][0]

    # Testing conventions
    result["testing"] = _detect_testing_conventions(project_path)

    # Formatting conventions
    # Indentation
    if indentation_votes:
        from collections import Counter
        indent_counts = Counter(indentation_votes)
        most_common = indent_counts.most_common(1)[0]
        if most_common[1] / len(indentation_votes) > 0.5:
            result["formatting"]["indentation"] = most_common[0]

    # Line length from config
    result["formatting"]["line_length"] = _detect_line_length_from_config(project_path)

    # Trailing commas
    if trailing_comma_votes:
        true_votes = sum(1 for v in trailing_comma_votes if v is True)
        false_votes = sum(1 for v in trailing_comma_votes if v is False)
        total_votes = true_votes + false_votes

        if total_votes > 0:
            if true_votes / total_votes > 0.6:
                result["formatting"]["trailing_commas"] = True
            elif false_votes / total_votes > 0.6:
                result["formatting"]["trailing_commas"] = False

    logger.info(
        "Convention extraction complete for %s: %s files, %s functions, %s imports analyzed",
        project_path.name,
        result["naming"]["files"],
        result["naming"]["functions"],
        result["imports"]["style"],
    )

    return result
