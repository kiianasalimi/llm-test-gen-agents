#!/usr/bin/env python3
"""Evaluate code coverage of generated tests."""

import argparse
import ast
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def _estimate_function_coverage(source_code: str, executed_lines: set) -> float:
    """
    Estimate what fraction of top-level and method functions were entered,
    based on which lines were marked as executed by coverage.py.
    """
    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        return 0.0

    functions = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    if not functions:
        return 1.0

    covered = sum(1 for f in functions if f.lineno in executed_lines)
    return round(covered / len(functions), 4)


def eval_coverage(
    test_dir: Path,
    cut_module: str,
    output_file: Path = None,
    report_format: str = "text",
) -> dict:
    """
    Evaluate code coverage of generated tests using coverage.py.

    Runs the test suite under coverage measurement, then parses the JSON
    report to extract line, branch, and function coverage ratios.

    Args:
        test_dir: Directory containing test files.
        cut_module: Name of the CUT module to measure coverage for.
        output_file: Optional file to save the coverage report.
        report_format: Format of coverage report ('text', 'html', 'json').

    Returns:
        Dictionary with coverage metrics:
        {'line': float, 'branch': float, 'function': float}  (values 0.0–1.0)
    """
    project_root = Path(__file__).parent.parent.parent
    cut_dir = Path(__file__).parent.parent / "cut"
    cut_file = cut_dir / f"{cut_module}.py"

    if not cut_file.exists():
        print(f"[coverage] Warning: CUT file not found: {cut_file}")
        return {"line": 0.0, "branch": 0.0, "function": 0.0}

    # Build environment with project root on PYTHONPATH
    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        f"{project_root}{os.pathsep}{existing}" if existing else str(project_root)
    )

    # Step 1: run tests under coverage (branch tracking enabled)
    subprocess.run(
        [
            sys.executable, "-m", "coverage", "run",
            "--branch",
            f"--source={cut_dir}",
            "-m", "pytest", str(test_dir),
        ],
        env=env,
        capture_output=True,
        text=True,
    )

    # Step 2: export JSON report for programmatic parsing
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as tf:
        json_path = tf.name

    subprocess.run(
        [
            sys.executable, "-m", "coverage", "json",
            f"--include=*{cut_module}*",
            "-o", json_path,
        ],
        env=env,
        capture_output=True,
        text=True,
    )

    metrics = {"line": 0.0, "branch": 0.0, "function": 0.0}

    try:
        with open(json_path) as fh:
            data = json.load(fh)

        totals = data.get("totals", {})
        metrics["line"] = round(totals.get("percent_covered", 0.0) / 100, 4)

        num_branches = totals.get("num_branches", 0)
        covered_branches = totals.get("covered_branches", 0)
        metrics["branch"] = (
            round(covered_branches / num_branches, 4) if num_branches > 0 else 0.0
        )

        # Estimate function coverage from per-file executed line data
        for file_path, file_data in data.get("files", {}).items():
            if cut_module in file_path:
                executed = set(file_data.get("executed_lines", []))
                source = cut_file.read_text()
                metrics["function"] = _estimate_function_coverage(source, executed)
                break

    except (FileNotFoundError, json.JSONDecodeError, KeyError) as exc:
        print(f"[coverage] Warning: could not parse coverage JSON: {exc}")
    finally:
        Path(json_path).unlink(missing_ok=True)

    # Step 3: generate human-readable report in requested format
    if report_format == "html":
        html_result = subprocess.run(
            [
                sys.executable, "-m", "coverage", "html",
                f"--include=*{cut_module}*",
            ],
            env=env,
            capture_output=True,
            text=True,
        )
        if output_file:
            output_file.parent.mkdir(parents=True, exist_ok=True)
            output_file.write_text(html_result.stdout + html_result.stderr)

    elif report_format == "text":
        text_result = subprocess.run(
            [
                sys.executable, "-m", "coverage", "report",
                f"--include=*{cut_module}*",
            ],
            env=env,
            capture_output=True,
            text=True,
        )
        report_text = text_result.stdout
        print(report_text, end="")
        if output_file:
            output_file.parent.mkdir(parents=True, exist_ok=True)
            output_file.write_text(report_text)

    elif report_format == "json":
        if output_file:
            output_file.parent.mkdir(parents=True, exist_ok=True)
            output_file.write_text(json.dumps(metrics, indent=2))

    # Always persist metrics as JSON for aggregate.py to consume.
    # Naming convention: {method}_coverage.json where method = test_dir.name
    results_dir = Path(__file__).parent.parent / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    auto_out = results_dir / f"{Path(test_dir).name}_coverage.json"
    auto_out.write_text(json.dumps(metrics, indent=2))

    return metrics


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate code coverage of generated tests"
    )
    parser.add_argument(
        "--test-dir",
        type=Path,
        required=True,
        help="Directory containing test files",
    )
    parser.add_argument(
        "--cut-module",
        type=str,
        required=True,
        help="Name of the CUT module to measure coverage for",
    )
    parser.add_argument(
        "--output-file",
        type=Path,
        default=None,
        help="Optional file to save coverage report",
    )
    parser.add_argument(
        "--report-format",
        type=str,
        default="text",
        choices=["text", "html", "json"],
        help="Format of coverage report",
    )

    args = parser.parse_args()
    metrics = eval_coverage(
        test_dir=args.test_dir,
        cut_module=args.cut_module,
        output_file=args.output_file,
        report_format=args.report_format,
    )
    print(f"Coverage metrics: {metrics}")


if __name__ == "__main__":
    main()
