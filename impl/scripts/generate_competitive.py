#!/usr/bin/env python3
"""Competitive test case generation script."""

import argparse
import ast
import re
import textwrap
from pathlib import Path
import sys
from typing import List

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from impl.src.llm import call_local_llm

# Prompt for the first agent — generates initial tests with no prior context.
_INITIAL_PROMPT = textwrap.dedent("""\
    Generate {num_tests} pytest test cases for the following Python module.

    Module name: {cut_module}

    Source code:
    ```python
    {source_code}
    ```

    Requirements:
    - All function names MUST start with "test_agent1_"
    - Import at the top: from impl.cut.{cut_module} import *
    - Each test must have a one-line docstring

    Return ONLY a complete Python file inside a ```python ... ``` block.
""")

# Prompts for subsequent agents — each sees the tests already generated and must
# add value beyond them according to the competition mode.
_COMPETING_PROMPTS = {
    "adversarial": textwrap.dedent("""\
        You are an adversarial tester. Your goal is to find bugs and failures
        that the previous agent's tests would NOT catch.

        Previous tests (DO NOT duplicate these — find what they MISS):
        ```python
        {existing_tests}
        ```

        Module source code:
        ```python
        {source_code}
        ```

        Generate {num_tests} NEW pytest test cases for module '{cut_module}'.
        - All function names MUST start with "test_agent{agent_idx}_"
        - Import at the top: from impl.cut.{cut_module} import *
        - Focus on surprising inputs, corner cases, and common implementation bugs
        - Each test must have a one-line docstring

        Return ONLY a complete Python file inside a ```python ... ``` block.
    """),
    "diversity": textwrap.dedent("""\
        You are a diversity-focused tester. Your goal is to generate tests that are
        structurally and semantically DIFFERENT from those already written.

        Existing tests (generate tests that are UNLIKE these in structure and approach):
        ```python
        {existing_tests}
        ```

        Module source code:
        ```python
        {source_code}
        ```

        Generate {num_tests} NEW pytest test cases for module '{cut_module}'.
        - All function names MUST start with "test_agent{agent_idx}_"
        - Import at the top: from impl.cut.{cut_module} import *
        - Use different assertion styles, input patterns, and test structures
        - Each test must have a one-line docstring

        Return ONLY a complete Python file inside a ```python ... ``` block.
    """),
    "coverage": textwrap.dedent("""\
        You are a coverage-focused tester. Your goal is to cover code paths
        NOT exercised by the existing tests.

        Existing tests (identify uncovered branches and generate tests for them):
        ```python
        {existing_tests}
        ```

        Module source code:
        ```python
        {source_code}
        ```

        Generate {num_tests} NEW pytest test cases for module '{cut_module}'.
        - All function names MUST start with "test_agent{agent_idx}_"
        - Import at the top: from impl.cut.{cut_module} import *
        - Target every uncovered if/else branch, loop, and exception handler
        - Each test must have a one-line docstring

        Return ONLY a complete Python file inside a ```python ... ``` block.
    """),
}


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

            if re.match(r"^(import |from \S+ import)", stripped):
                if stripped not in seen_imports:
                    seen_imports.add(stripped)
                    import_lines.append(line)
                continue

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


def generate_competitive_tests(
    cut_module: str,
    output_dir: Path,
    num_agents: int = 2,
    num_tests: int = 10,
    competition_mode: str = "adversarial",
) -> None:
    """
    Generate test cases using competitive/adversarial agents.

    Agent 1 generates an initial test suite. Each subsequent agent sees the
    accumulated tests and generates additional tests according to competition_mode:
    - adversarial: find what the others missed (bugs, surprising inputs)
    - diversity:   generate structurally different tests
    - coverage:    cover branches not yet exercised

    Args:
        cut_module: Name of the module in impl/cut/ to test.
        output_dir: Directory to save generated test files.
        num_agents: Number of competing agents.
        num_tests: Number of test cases to generate per agent.
        competition_mode: Competition strategy ('adversarial', 'diversity', 'coverage').
    """
    valid_modes = {"adversarial", "diversity", "coverage"}
    if competition_mode not in valid_modes:
        raise ValueError(
            f"Invalid competition_mode '{competition_mode}'. "
            f"Must be one of: {sorted(valid_modes)}"
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    source_code = _load_cut_source(cut_module)

    code_blocks: List[str] = []

    # Agent 1 — initial generation with no prior context
    prompt = _INITIAL_PROMPT.format(
        cut_module=cut_module,
        source_code=source_code,
        num_tests=num_tests,
    )
    print(f"[competitive/{competition_mode}] Agent 1 generating {num_tests} initial tests...")
    raw = call_local_llm(prompt)
    code = _ensure_pytest_import(_extract_python_code(raw))
    try:
        ast.parse(code)
        code_blocks.append(code)
    except SyntaxError as exc:
        print(f"[competitive] Warning: Agent 1 returned invalid code ({exc}). Continuing.")

    # Subsequent agents — each sees the accumulated tests
    competing_template = _COMPETING_PROMPTS[competition_mode]
    for agent_idx in range(2, num_agents + 1):
        existing_tests = _merge_test_codes(code_blocks) if code_blocks else "(none yet)"
        prompt = competing_template.format(
            cut_module=cut_module,
            source_code=source_code,
            existing_tests=existing_tests,
            num_tests=num_tests,
            agent_idx=agent_idx,
        )
        print(
            f"[competitive/{competition_mode}] Agent {agent_idx} generating "
            f"{num_tests} competing tests..."
        )
        raw = call_local_llm(prompt)
        code = _ensure_pytest_import(_extract_python_code(raw))
        try:
            ast.parse(code)
            code_blocks.append(code)
        except SyntaxError as exc:
            print(
                f"[competitive] Warning: Agent {agent_idx} returned invalid "
                f"code ({exc}). Skipping."
            )

    if not code_blocks:
        raise RuntimeError("All agents produced invalid code. No tests were saved.")

    merged = _merge_test_codes(code_blocks)

    tree = ast.parse(merged)
    total = sum(
        1
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
    )

    output_file = output_dir / f"test_{cut_module}.py"
    output_file.write_text(merged)
    print(
        f"[competitive] Saved {total} test(s) from {len(code_blocks)} agent(s) "
        f"-> {output_file}"
    )


def main():
    parser = argparse.ArgumentParser(
        description="Generate test cases using competitive/adversarial agents"
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
        default=Path(__file__).parent.parent / "tests_generated" / "competitive",
        help="Directory to save generated test files",
    )
    parser.add_argument(
        "--num-agents",
        type=int,
        default=2,
        help="Number of competing agents",
    )
    parser.add_argument(
        "--num-tests",
        type=int,
        default=10,
        help="Number of test cases to generate per agent",
    )
    parser.add_argument(
        "--competition-mode",
        type=str,
        default="adversarial",
        choices=["adversarial", "diversity", "coverage"],
        help="Mode of competition between agents",
    )

    args = parser.parse_args()
    generate_competitive_tests(
        cut_module=args.cut_module,
        output_dir=args.output_dir,
        num_agents=args.num_agents,
        num_tests=args.num_tests,
        competition_mode=args.competition_mode,
    )


if __name__ == "__main__":
    main()
