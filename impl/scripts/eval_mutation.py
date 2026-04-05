#!/usr/bin/env python3
"""Evaluate mutation testing score of generated tests (mutmut 3.x compatible)."""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def _humanize_mutmut_output(text: str) -> str:
    """Replace mutmut emojis with text labels for readability."""
    replacements = {
        "🎉": "[KILLED]",
        "⏰": "[TIMEOUT]",
        "🤔": "[SUSPICIOUS]",
        "🙁": "[SURVIVED]",
        "🔇": "[SKIPPED]",
    }
    result = text
    for emoji, label in replacements.items():
        result = result.replace(emoji, label)
    return result


def _parse_mutmut_results(stdout: str) -> dict:
    """
    Parse mutmut 3.x output to extract killed/survived/timeout counts.

    Strategy 1 — emoji summary line written during the run (most reliable):
        🎉 23  ⏰ 0  🤔 0  🙁 19  🔇 0

    Strategy 2 — per-mutant lines from ``mutmut results --all True``:
        <key>: killed
        <key>: survived
    """
    import re

    # Strategy 1: parse the final emoji summary line from mutmut run stdout.
    # Take the last matching line (the final totals after all mutants finish).
    killed = survived = timeout = 0
    emoji_pattern = re.compile(
        r"🎉\s*(\d+).*?⏰\s*(\d+).*?🤔\s*(\d+).*?🙁\s*(\d+)"
    )
    for line in reversed(stdout.splitlines()):
        m = emoji_pattern.search(line)
        if m:
            killed = int(m.group(1))
            timeout = int(m.group(2))
            # group 3 = suspicious, count as survived (not killed)
            survived = int(m.group(4))
            return {"killed": killed, "survived": survived, "timeout": timeout}

    # Strategy 2: per-mutant lines from mutmut results
    for line in stdout.splitlines():
        line = line.strip()
        if line.endswith(": killed") or line.endswith(": caught by type check"):
            killed += 1
        elif line.endswith(": survived"):
            survived += 1
        elif line.endswith(": timeout"):
            timeout += 1

    return {"killed": killed, "survived": survived, "timeout": timeout}


def eval_mutation(
    test_dir: Path,
    cut_module: str,
    output_file: Path = None,
    mutation_target: Path = None,
) -> dict:
    """
    Evaluate mutation testing score of generated tests using mutmut (3.x).

    Writes a temporary ``setup.cfg`` with the mutmut configuration for this
    run, invokes ``mutmut run`` followed by ``mutmut results --all True``,
    then parses the output to compute the mutation score.

    Args:
        test_dir: Directory containing test files.
        cut_module: Name of the CUT module to run mutation testing on.
        output_file: Optional file to save mutation testing results.
        mutation_target: Specific file to mutate (defaults to impl/cut/{cut_module}.py).

    Returns:
        Dict with keys: score (float 0-1), killed (int), survived (int), timeout (int).
    """
    impl_dir = Path(__file__).parent.parent          # impl/
    project_root = Path(__file__).parent.parent.parent  # repo root

    if mutation_target is None:
        mutation_target = impl_dir / "cut" / f"{cut_module}.py"

    mutation_target = Path(mutation_target)
    if not mutation_target.exists():
        print(f"[mutation] Warning: mutation target not found: {mutation_target}")
        return {"score": 0.0, "killed": 0, "survived": 0, "timeout": 0}

    # All paths passed to mutmut must be relative to impl_dir (its cwd).
    try:
        rel_target = str(mutation_target.relative_to(impl_dir))
    except ValueError:
        rel_target = str(mutation_target)

    abs_test_dir = Path(test_dir).resolve()
    try:
        rel_test_dir = str(abs_test_dir.relative_to(impl_dir))
    except ValueError:
        rel_test_dir = str(abs_test_dir)

    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        f"{project_root}{os.pathsep}{existing}" if existing else str(project_root)
    )
    # Tell pytest (run inside mutmut's sandbox) how to resolve impl.cut.*
    env["PYTHONPATH"] = os.pathsep.join([str(project_root), env.get("PYTHONPATH", "")])

    # mutmut 3.x reads configuration from setup.cfg.
    # also_copy: mutmut copies these paths into its sandbox before running tests.
    #   Without this, the test files are not visible inside the mutmut subprocess.
    # tests_dir: tells mutmut where to find/run pytest tests (relative path).
    setup_cfg = impl_dir / "setup.cfg"
    setup_cfg_existed = setup_cfg.exists()
    setup_cfg_backup = setup_cfg.read_text() if setup_cfg_existed else None

    zero = {"score": 0.0, "killed": 0, "survived": 0, "timeout": 0}

    try:
        import shutil

        cfg_content = (
            "[mutmut]\n"
            f"paths_to_mutate = {rel_target}\n"
            f"tests_dir = {rel_test_dir}\n"
            f"also_copy = {rel_test_dir}\n"
        )
        setup_cfg.write_text(cfg_content)
        print(f"[mutation] Config written:\n{cfg_content}")

        # Clear stale cache so mutmut re-runs against the current test suite.
        for stale in [impl_dir / ".mutmut-cache", impl_dir / "mutants"]:
            if stale.is_dir():
                shutil.rmtree(stale)
            elif stale.exists():
                stale.unlink()

        # Write a temporary conftest.py that tells pytest to ignore all
        # tests_generated subdirs EXCEPT the target one.  conftest.py is
        # respected by every pytest invocation mutmut makes internally,
        # regardless of how mutmut constructs the command line.
        all_test_subdirs = {"single", "collab", "competitive"}
        target_parts = Path(rel_test_dir).parts  # e.g. ('tests_generated', 'single')
        target_subdir = target_parts[1] if len(target_parts) > 1 else rel_test_dir
        ignored_globs = [f"tests_generated/{d}/*" for d in sorted(all_test_subdirs) if d != target_subdir]
        conftest = impl_dir / "conftest.py"
        conftest_existed = conftest.exists()
        conftest_backup = conftest.read_text() if conftest_existed else None
        conftest.write_text(
            "# Auto-generated by eval_mutation.py — do not edit manually\n"
            f"collect_ignore_glob = {ignored_globs!r}\n"
        )
        print(f"[mutation] conftest.py: ignoring {ignored_globs}")

        print(f"[mutation] Running mutmut on {mutation_target} ...")
        run_result = subprocess.run(
            [sys.executable, "-m", "mutmut", "run"],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(impl_dir),
        )

        print(f"[mutation] mutmut run exit code: {run_result.returncode}")
        if run_result.stdout.strip():
            print(f"[mutation] stdout:\n{_humanize_mutmut_output(run_result.stdout[-1000:])}")
        if run_result.stderr.strip():
            print(f"[mutation] stderr:\n{_humanize_mutmut_output(run_result.stderr[-1000:])}")

        # exit 0 = all killed, 1 = some survived, 2 = completed with survivors
        # (mutmut 3.x uses 2 for "run done, survivors exist") — all are normal.
        if run_result.returncode not in (0, 1, 2):
            print(f"[mutation] mutmut run failed (exit {run_result.returncode}). Returning zero scores.")
            return zero

    finally:
        if setup_cfg_existed:
            setup_cfg.write_text(setup_cfg_backup)
        else:
            setup_cfg.unlink(missing_ok=True)
        if conftest_existed:
            conftest.write_text(conftest_backup)
        else:
            conftest.unlink(missing_ok=True)

    counts = _parse_mutmut_results(run_result.stdout)
    killed = counts["killed"]
    survived = counts["survived"]
    timeout = counts["timeout"]

    total = killed + survived
    score = round(killed / total, 4) if total > 0 else 0.0

    metrics = {
        "score": score,
        "killed": killed,
        "survived": survived,
        "timeout": timeout,
    }

    # Persist metrics for aggregate.py
    results_dir = impl_dir / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    auto_out = results_dir / f"{Path(test_dir).name}_mutation.json"
    auto_out.write_text(json.dumps(metrics, indent=2))

    if output_file:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(json.dumps(metrics, indent=2))

    return metrics


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate mutation testing score of generated tests"
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
        help="Name of the CUT module to run mutation testing on",
    )
    parser.add_argument(
        "--output-file",
        type=Path,
        default=None,
        help="Optional file to save mutation testing results",
    )
    parser.add_argument(
        "--mutation-target",
        type=Path,
        default=None,
        help="Optional specific file to mutate (defaults to cut_module)",
    )

    args = parser.parse_args()
    metrics = eval_mutation(
        test_dir=args.test_dir,
        cut_module=args.cut_module,
        output_file=args.output_file,
        mutation_target=args.mutation_target,
    )
    print(f"Mutation testing metrics: {metrics}")


if __name__ == "__main__":
    main()
