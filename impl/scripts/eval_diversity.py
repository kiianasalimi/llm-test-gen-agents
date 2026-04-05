#!/usr/bin/env python3
"""Evaluate diversity of generated test cases."""

import argparse
import ast
import json
from itertools import combinations
from pathlib import Path
from typing import List, Set


def _get_test_function_signatures(code: str) -> List[Set[str]]:
    """
    Parse a Python source file and return one set of AST node-type names per
    test_ function.  The set captures the structural "fingerprint" of the test.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []

    signatures = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
            node_types = {type(child).__name__ for child in ast.walk(node)}
            signatures.append(node_types)
    return signatures


def _get_literal_values(code: str) -> List[str]:
    """Return string representations of all constant literals used in the code."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []
    return [str(node.value) for node in ast.walk(tree) if isinstance(node, ast.Constant)]


def _jaccard_similarity(a: Set[str], b: Set[str]) -> float:
    """Jaccard similarity between two sets (0 = disjoint, 1 = identical)."""
    union = len(a | b)
    return len(a & b) / union if union > 0 else 0.0


def eval_diversity(
    test_dir: Path,
    output_file: Path = None,
    diversity_metric: str = "syntactic",
) -> dict:
    """
    Evaluate diversity of generated test cases.

    Three modes:
    - syntactic: pairwise Jaccard similarity of AST node-type fingerprints.
                 diversity_score = 1 - mean_pairwise_similarity
    - semantic:  ratio of unique literal values to total literal values.
                 diversity_score = unique_literals / total_literals
    - coverage:  ratio of unique call-site patterns across test functions.
                 diversity_score = unique_call_targets / total_test_functions

    Args:
        test_dir: Directory containing test files.
        output_file: Optional file to save diversity analysis results.
        diversity_metric: Type of diversity to measure ('syntactic', 'semantic', 'coverage').

    Returns:
        Dictionary with diversity metrics:
        {'diversity_score': float, 'unique_patterns': int, 'similarity': float}
    """
    test_files = sorted(Path(test_dir).glob("test_*.py"))
    zero_result = {"diversity_score": 0.0, "unique_patterns": 0, "similarity": 0.0}

    if not test_files:
        print(f"[diversity] No test_*.py files found in {test_dir}")
        return zero_result

    all_signatures: List[Set[str]] = []
    all_literals: List[str] = []

    for test_file in test_files:
        code = test_file.read_text()
        all_signatures.extend(_get_test_function_signatures(code))
        all_literals.extend(_get_literal_values(code))

    if not all_signatures:
        return zero_result

    if diversity_metric == "syntactic":
        if len(all_signatures) < 2:
            similarity = 0.0
        else:
            sims = [
                _jaccard_similarity(a, b)
                for a, b in combinations(all_signatures, 2)
            ]
            similarity = round(sum(sims) / len(sims), 4)

        unique_patterns = len({frozenset(s) for s in all_signatures})
        diversity_score = round(1.0 - similarity, 4)

    elif diversity_metric == "semantic":
        total = len(all_literals)
        unique = len(set(all_literals))
        diversity_score = round(unique / total, 4) if total > 0 else 0.0
        similarity = round(1.0 - diversity_score, 4)
        unique_patterns = unique

    else:  # coverage — proxy: fraction of structurally distinct call targets
        call_targets: Set[str] = set()
        for sig in all_signatures:
            call_targets.update(t for t in sig if "Call" in t)
        unique_patterns = len(call_targets)
        n = len(all_signatures)
        diversity_score = round(min(1.0, unique_patterns / n), 4) if n > 0 else 0.0
        similarity = round(1.0 - diversity_score, 4)

    metrics = {
        "diversity_score": diversity_score,
        "unique_patterns": unique_patterns,
        "similarity": similarity,
    }

    # Persist for aggregate.py
    results_dir = Path(__file__).parent.parent / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    auto_out = results_dir / f"{Path(test_dir).name}_diversity.json"
    auto_out.write_text(json.dumps(metrics, indent=2))

    if output_file:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(json.dumps(metrics, indent=2))

    return metrics


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate diversity of generated test cases"
    )
    parser.add_argument(
        "--test-dir",
        type=Path,
        required=True,
        help="Directory containing test files",
    )
    parser.add_argument(
        "--output-file",
        type=Path,
        default=None,
        help="Optional file to save diversity analysis results",
    )
    parser.add_argument(
        "--diversity-metric",
        type=str,
        default="syntactic",
        choices=["syntactic", "semantic", "coverage"],
        help="Type of diversity to measure",
    )

    args = parser.parse_args()
    metrics = eval_diversity(
        test_dir=args.test_dir,
        output_file=args.output_file,
        diversity_metric=args.diversity_metric,
    )
    print(f"Diversity metrics: {metrics}")


if __name__ == "__main__":
    main()
