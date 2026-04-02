#!/usr/bin/env python3
"""Collaborative test case generation script."""

import argparse
import ast
import json
import re
import textwrap
from pathlib import Path
import sys
from typing import List, Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from impl.src.llm import call_local_llm

# Default role definitions used when no external roles file is provided.
_DEFAULT_ROLES = [
    {
        "name": "edge_case_tester",
        "description": (
            "You specialise in edge cases: None/null inputs, empty strings, "
            "empty collections, zero, very large numbers, and type boundaries."
        ),
    },
    {
        "name": "boundary_tester",
        "description": (
            "You specialise in boundary conditions: off-by-one errors, "
            "minimum and maximum valid values, and transitions between states."
        ),
    },
    {
        "name": "error_tester",
        "description": (
            "You specialise in error handling: invalid argument types, "
            "values that should raise exceptions, and incorrect API usage."
        ),
    },
]

_ROLE_PROMPT_TEMPLATE = textwrap.dedent("""\
    You are a specialised software tester with the following role:
    {role_description}

    Generate {num_tests} pytest test cases for the module below.
    Name every test function starting with "test_{role_name}_".

    Module name: {cut_module}

    Source code:
    ```python
    {source_code}
    ```

    Requirements:
    - All function names MUST start with "test_{role_name}_"
    - Import at the top: from impl.cut.{cut_module} import *
    - Focus strictly on your assigned role
    - Each test must have a one-line docstring

    Return ONLY a complete Python file inside a ```python ... ``` block.
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


def _merge_test_codes(code_blocks: List[str]) -> str:
    """
    Merge multiple Python test code blocks into one file.
    Deduplicates import lines and renames duplicate test_ function names.
    """
    seen_imports: set = set()
    import_lines: List[str] = []
    body_lines: List[str] = []
    seen_fn_names: set = set()

    for code in code_blocks:
        for line in code.strip().splitlines():
            stripped = line.strip()

            # Collect and deduplicate import statements
            if re.match(r"^(import |from \S+ import)", stripped):
                if stripped not in seen_imports:
                    seen_imports.add(stripped)
                    import_lines.append(line)
                continue

            # Detect and rename duplicate test_ function definitions
            fn_match = re.match(r"^def (test_\w+)\(", stripped)
            if fn_match:
                fn_name = fn_match.group(1)
                original = fn_name
                counter = 2
                while fn_name in seen_fn_names:
                    fn_name = f"{original}_{counter}"
                    counter += 1
                seen_fn_names.add(fn_name)
                if fn_name != original:
                    line = re.sub(
                        rf"^def {re.escape(original)}\(",
                        f"def {fn_name}(",
                        line,
                    )

            body_lines.append(line)

    return "\n".join(import_lines) + "\n\n\n" + "\n".join(body_lines)


def generate_collab_tests(
    cut_module: str,
    output_dir: Path,
    num_agents: int = 3,
    num_tests: int = 10,
    prompt_roles: Optional[Path] = None,
) -> None:
    """
    Generate test cases using multiple collaborating agents.

    Each agent is assigned a distinct role (edge-case, boundary, error testing).
    Their outputs are merged into a single deduplicated test file.

    Args:
        cut_module: Name of the module in impl/cut/ to test.
        output_dir: Directory to save generated test files.
        num_agents: Number of collaborating agents (capped to available roles).
        num_tests: Number of test cases to generate per agent.
        prompt_roles: Optional path to a JSON file with role definitions.
            Each entry must have "name" and "description" keys.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    source_code = _load_cut_source(cut_module)

    # Load role definitions
    if prompt_roles is not None and Path(prompt_roles).exists():
        roles = json.loads(Path(prompt_roles).read_text())
    else:
        roles = _DEFAULT_ROLES

    # Use only as many roles as requested agents
    roles = roles[:num_agents]

    code_blocks: List[str] = []
    for role in roles:
        prompt = _ROLE_PROMPT_TEMPLATE.format(
            role_name=role["name"],
            role_description=role["description"],
            cut_module=cut_module,
            source_code=source_code,
            num_tests=num_tests,
        )
        print(f"[collab] Agent '{role['name']}' generating {num_tests} tests...")
        raw = call_local_llm(prompt)
        code = _ensure_pytest_import(_extract_python_code(raw))

        # Basic syntax check before accepting
        try:
            ast.parse(code)
            code_blocks.append(code)
        except SyntaxError as exc:
            print(f"[collab] Warning: agent '{role['name']}' returned invalid code ({exc}). Skipping.")

    if not code_blocks:
        raise RuntimeError("All agents produced invalid code. No tests were saved.")

    merged = _merge_test_codes(code_blocks)

    # Count test functions in merged output
    tree = ast.parse(merged)
    total = sum(
        1
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
    )

    output_file = output_dir / f"test_{cut_module}.py"
    output_file.write_text(merged)
    print(f"[collab] Saved {total} test(s) from {len(code_blocks)} agent(s) -> {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Generate test cases using multiple collaborating agents"
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
        default=Path(__file__).parent.parent / "tests_generated" / "collab",
        help="Directory to save generated test files",
    )
    parser.add_argument(
        "--num-agents",
        type=int,
        default=3,
        help="Number of collaborating agents",
    )
    parser.add_argument(
        "--num-tests",
        type=int,
        default=10,
        help="Number of test cases to generate per agent",
    )
    parser.add_argument(
        "--prompt-roles",
        type=Path,
        default=None,
        help="Optional path to JSON file with role definitions for agents",
    )

    args = parser.parse_args()
    generate_collab_tests(
        cut_module=args.cut_module,
        output_dir=args.output_dir,
        num_agents=args.num_agents,
        num_tests=args.num_tests,
        prompt_roles=args.prompt_roles,
    )


if __name__ == "__main__":
    main()
