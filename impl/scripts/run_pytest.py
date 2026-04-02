#!/usr/bin/env python3
"""Run pytest on generated test files."""

import argparse
import os
import subprocess
from pathlib import Path
import sys


def run_pytest(
    test_dir: Path,
    cut_module_path: Path = None,
    output_file: Path = None,
    verbose: bool = False,
) -> int:
    """
    Run pytest on generated test files.

    Sets PYTHONPATH so that 'from impl.cut.<module> import *' resolves correctly
    inside generated test files.

    Args:
        test_dir: Directory containing test files to run.
        cut_module_path: Additional path to add to PYTHONPATH (e.g., impl/cut/).
        output_file: Optional file to save the combined pytest output.
        verbose: Whether to run pytest in verbose mode (-v).

    Returns:
        Exit code from pytest (0 = all tests passed).
    """
    # Project root must be on PYTHONPATH so 'impl.cut.*' imports resolve.
    project_root = str(Path(__file__).parent.parent.parent)

    env = os.environ.copy()
    extra_paths = [project_root]
    if cut_module_path:
        extra_paths.append(str(cut_module_path))

    existing_pythonpath = env.get("PYTHONPATH", "")
    if existing_pythonpath:
        extra_paths.append(existing_pythonpath)
    env["PYTHONPATH"] = os.pathsep.join(extra_paths)

    cmd = [sys.executable, "-m", "pytest", str(test_dir)]
    if verbose:
        cmd.append("-v")

    result = subprocess.run(cmd, capture_output=True, text=True, env=env)
    output = result.stdout + result.stderr

    if output_file:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(output)
        print(f"[pytest] Output saved -> {output_file}")

    print(output, end="")
    return result.returncode


def main():
    parser = argparse.ArgumentParser(
        description="Run pytest on generated test files"
    )
    parser.add_argument(
        "--test-dir",
        type=Path,
        required=True,
        help="Directory containing test files to run",
    )
    parser.add_argument(
        "--cut-module-path",
        type=Path,
        default=None,
        help="Path to CUT module directory (impl/cut/)",
    )
    parser.add_argument(
        "--output-file",
        type=Path,
        default=None,
        help="Optional file to save pytest output",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Run pytest in verbose mode",
    )

    args = parser.parse_args()
    exit_code = run_pytest(
        test_dir=args.test_dir,
        cut_module_path=args.cut_module_path,
        output_file=args.output_file,
        verbose=args.verbose,
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
