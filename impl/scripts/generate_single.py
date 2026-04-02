#!/usr/bin/env python3
"""Single-agent test case generation script."""

import argparse
import ast
import re
import textwrap
from pathlib import Path
import sys
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from impl.src.llm import call_local_llm

_DEFAULT_PROMPT_TEMPLATE = textwrap.dedent("""\
    Generate {num_tests} pytest test cases for the following Python module.

    Module name: {cut_module}

    Source code:
    ```python
    {source_code}
    ```

    Requirements:
    - All test function names MUST start with "test_"
    - At the top of the file write: from impl.cut.{cut_module} import *
    - Cover normal behavior AND error/edge cases
    - Include boundary conditions (zero, negative, empty, None where applicable)
    - Each test function must have a one-line docstring

    Return ONLY a complete Python file inside a ```python ... ``` block.
    Do not include any text or commentary outside the code block.
""")


def _extract_python_code(text: str) -> str:
    """Extract Python code from an LLM response that may wrap it in code fences."""
    for pattern in (r"```python\s*\n(.*?)```", r"```\s*\n(.*?)```"):
        matches = re.findall(pattern, text, re.DOTALL)
        if matches:
            return "\n\n".join(m.strip() for m in matches)
    return text.strip()


def _ensure_pytest_import(code: str) -> str:
    """Inject 'import pytest' if the code uses pytest but doesn't import it."""
    if "pytest" not in code:
        return code
    if re.search(r"^\s*import pytest\b", code, re.MULTILINE):
        return code
    # Insert after the last top-level import line
    lines = code.splitlines()
    last_import = -1
    for i, line in enumerate(lines):
        if re.match(r"^(import |from \S+ import)", line.strip()):
            last_import = i
    insert_at = last_import + 1 if last_import >= 0 else 0
    lines.insert(insert_at, "import pytest")
    return "\n".join(lines)


def _load_cut_source(cut_module: str) -> str:
    """Read the source code of a CUT module from impl/cut/."""
    cut_path = Path(__file__).parent.parent / "cut" / f"{cut_module}.py"
    if not cut_path.exists():
        raise FileNotFoundError(
            f"CUT module not found: {cut_path}\n"
            f"Create impl/cut/{cut_module}.py before generating tests."
        )
    return cut_path.read_text()


def _validate_test_code(code: str) -> int:
    """
    Validate that code is syntactically correct and contains test_ functions.
    Returns the count of test_ functions found.
    Raises ValueError on failure.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        raise ValueError(f"Generated code has a syntax error: {exc}") from exc

    test_fns = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
    ]
    if not test_fns:
        raise ValueError(
            "No test_ functions found in generated code. "
            "The LLM did not follow the naming convention."
        )
    return len(test_fns)


def generate_single_tests(
    cut_module: str,
    output_dir: Path,
    num_tests: int = 10,
    prompt_template: Optional[Path] = None,
) -> None:
    """
    Generate test cases using a single agent.

    Args:
        cut_module: Name of the module in impl/cut/ to test.
        output_dir: Directory to save generated test files.
        num_tests: Number of test cases to generate.
        prompt_template: Optional path to a custom prompt template file.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    source_code = _load_cut_source(cut_module)

    if prompt_template is not None and Path(prompt_template).exists():
        template = Path(prompt_template).read_text()
    else:
        template = _DEFAULT_PROMPT_TEMPLATE

    prompt = template.format(
        cut_module=cut_module,
        source_code=source_code,
        num_tests=num_tests,
    )

    max_attempts = 3
    last_error = None
    for attempt in range(1, max_attempts + 1):
        print(f"[single] Generating {num_tests} tests for '{cut_module}' (attempt {attempt}/{max_attempts})...")
        raw_response = call_local_llm(prompt)
        code = _ensure_pytest_import(_extract_python_code(raw_response))
        try:
            num_found = _validate_test_code(code)
        except ValueError as exc:
            print(f"[single] Attempt {attempt} produced invalid code: {exc}. Retrying...")
            last_error = exc
            continue

        output_file = output_dir / f"test_{cut_module}.py"
        output_file.write_text(code)
        print(f"[single] Saved {num_found} test(s) -> {output_file}")
        return

    raise RuntimeError(
        f"Failed to generate valid tests after {max_attempts} attempts. "
        f"Last error: {last_error}"
    )


def main():
    parser = argparse.ArgumentParser(
        description="Generate test cases using a single agent"
    )
    parser.add_argument(
        "--cut-module",
        type=str,
        required=True,
        help="Name of the module in impl/cut/ to test (e.g., 'calculator')",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).parent.parent / "tests_generated" / "single",
        help="Directory to save generated test files",
    )
    parser.add_argument(
        "--num-tests",
        type=int,
        default=10,
        help="Number of test cases to generate",
    )
    parser.add_argument(
        "--prompt-template",
        type=Path,
        default=None,
        help="Optional path to custom prompt template",
    )

    args = parser.parse_args()
    generate_single_tests(
        cut_module=args.cut_module,
        output_dir=args.output_dir,
        num_tests=args.num_tests,
        prompt_template=args.prompt_template,
    )


if __name__ == "__main__":
    main()
