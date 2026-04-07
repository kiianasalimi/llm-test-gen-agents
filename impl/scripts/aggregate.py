#!/usr/bin/env python3
"""Aggregate evaluation results from multiple test generation runs."""

import argparse
import json
from pathlib import Path


def aggregate_results(
    results_dir: Path,
    output_file: Path = None,
    output_format: str = "csv",
) -> None:
    """
    Aggregate evaluation results from multiple test generation runs.

    Scans results_dir for JSON files named {method}_{eval_type}.json
    (e.g., single_coverage.json, collab_mutation.json), combines them into
    one table, computes per-method summary statistics, and exports.

    Args:
        results_dir: Directory containing evaluation result JSON files.
        output_file: File to save aggregated results (default: results_dir/summary.<fmt>).
        output_format: Format for aggregated output ('csv', 'json', 'html').
    """
    try:
        import pandas as pd
    except ImportError:
        raise ImportError(
            "pandas is required for aggregation. Install it with: pip install pandas"
        )

    results_dir = Path(results_dir)
    if not results_dir.exists():
        print(f"[aggregate] Results directory not found: {results_dir}")
        return

    rows = []
    for json_file in sorted(results_dir.glob("*.json")):
        stem = json_file.stem  # e.g. "single_coverage" or "collab_mutation"
        parts = stem.split("_", 1)
        method = parts[0]                     # "single" / "collab" / "competitive"
        eval_type = parts[1] if len(parts) == 2 else "unknown"  # "coverage" / etc.

        try:
            data = json.loads(json_file.read_text())
        except (json.JSONDecodeError, OSError) as exc:
            print(f"[aggregate] Skipping {json_file.name}: {exc}")
            continue

        if not isinstance(data, dict):
            continue

        row = {"method": method, "eval_type": eval_type}
        row.update({k: v for k, v in data.items() if isinstance(v, (int, float))})
        rows.append(row)

    if not rows:
        print(f"[aggregate] No valid result files found in {results_dir}")
        return

    df = pd.DataFrame(rows)

    numeric_cols = [c for c in df.columns if c not in ("method", "eval_type")]

    if not numeric_cols:
        print("[aggregate] No numeric metrics found in result files.")
        return

    # Wide format: one row per (method, eval_type), columns are metric values
    wide = df.pivot_table(
        index="method",
        columns="eval_type",
        values=numeric_cols,
        aggfunc="mean",
    )
    wide.columns = [f"{metric}_{etype}" for metric, etype in wide.columns]
    wide = wide.reset_index()

    # Summary statistics per method across all metrics
    summary_parts = [wide]
    if len(df) > 1:
        stats = (
            df.groupby("method")[numeric_cols]
            .agg(["mean", "std", "min", "max"])
        )
        stats.columns = ["_".join(col) for col in stats.columns]
        stats = stats.reset_index()
        summary_parts.append(stats.set_index("method"))

    if output_file is None:
        output_file = results_dir / f"summary.{output_format}"

    output_file.parent.mkdir(parents=True, exist_ok=True)

    if output_format == "csv":
        wide.to_csv(output_file, index=False)
    elif output_format == "json":
        wide.to_json(output_file, orient="records", indent=2)
    elif output_format == "html":
        wide.to_html(output_file, index=False)

    print(f"[aggregate] Summary saved -> {output_file}")
    print(wide.to_string(index=False))


def main():
    parser = argparse.ArgumentParser(
        description="Aggregate evaluation results from multiple test generation runs"
    )
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=Path(__file__).parent.parent / "results",
        help="Directory containing evaluation result files",
    )
    parser.add_argument(
        "--output-file",
        type=Path,
        default=None,
        help="File to save aggregated results",
    )
    parser.add_argument(
        "--output-format",
        type=str,
        default="csv",
        choices=["csv", "json", "html"],
        help="Format for aggregated output",
    )

    args = parser.parse_args()
    aggregate_results(
        results_dir=args.results_dir,
        output_file=args.output_file,
        output_format=args.output_format,
    )


if __name__ == "__main__":
    main()
