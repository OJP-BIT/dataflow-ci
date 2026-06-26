import logging
import os
import glob
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


def _find_output_files(repo_path: str) -> list[str]:
    patterns = [
        os.path.join(repo_path, "outputs", "*.csv"),
        os.path.join(repo_path, "outputs", "*.parquet"),
    ]
    files = []
    for pattern in patterns:
        files.extend(glob.glob(pattern))
    return files


def _load_file(filepath: str) -> pd.DataFrame:
    if filepath.endswith(".parquet"):
        return pd.read_parquet(filepath)
    return pd.read_csv(filepath)


def _load_expectations(repo_path: str) -> dict[str, Any]:
    expectations_path = os.path.join(repo_path, "dataflow_expectations.yml")
    if os.path.exists(expectations_path):
        import yaml
        with open(expectations_path) as f:
            return yaml.safe_load(f)
    return {}


def check_foreign_keys(repo_path: str, expectations: dict) -> list[dict]:
    results = []
    relationships = expectations.get("relationships", [])

    for rel in relationships:
        source_file = os.path.join(repo_path, "outputs", rel["source_file"])
        source_col = rel["source_column"]
        target_file = os.path.join(repo_path, "outputs", rel["target_file"])
        target_col = rel["target_column"]
        check_name = f"fk:{rel['source_file']}.{source_col} -> {rel['target_file']}.{target_col}"

        try:
            source_df = _load_file(source_file)
            target_df = _load_file(target_file)
        except FileNotFoundError as e:
            results.append({
                "check": check_name,
                "category": "referential",
                "file": rel["source_file"],
                "passed": False,
                "message": f"Could not load file for FK check: {e}",
            })
            continue

        source_vals = set(source_df[source_col].dropna().unique())
        target_vals = set(target_df[target_col].dropna().unique())
        orphans = source_vals - target_vals
        passed = len(orphans) == 0

        results.append({
            "check": check_name,
            "category": "referential",
            "file": rel["source_file"],
            "passed": passed,
            "message": (
                f"FK violation: {len(orphans)} values in '{source_col}' "
                f"not found in '{target_col}'. Sample: {list(orphans)[:5]}"
                if not passed
                else f"FK integrity OK: all {len(source_vals)} values matched"
            ),
        })

    return results


def check_join_coverage(repo_path: str, expectations: dict) -> list[dict]:
    results = []
    join_checks = expectations.get("join_coverage", [])

    for check in join_checks:
        left_file = os.path.join(repo_path, "outputs", check["left_file"])
        left_col = check["left_column"]
        right_file = os.path.join(repo_path, "outputs", check["right_file"])
        right_col = check["right_column"]
        min_coverage = check.get("min_coverage_ratio", 0.95)
        check_name = f"join_coverage:{check['left_file']} x {check['right_file']}"

        try:
            left_df = _load_file(left_file)
            right_df = _load_file(right_file)
        except FileNotFoundError as e:
            results.append({
                "check": check_name,
                "category": "referential",
                "file": check["left_file"],
                "passed": False,
                "message": f"Could not load file for join coverage check: {e}",
            })
            continue

        left_vals = set(left_df[left_col].dropna().unique())
        right_vals = set(right_df[right_col].dropna().unique())

        if len(left_vals) == 0:
            results.append({
                "check": check_name,
                "category": "referential",
                "file": check["left_file"],
                "passed": False,
                "message": f"Left file has no values in '{left_col}'",
            })
            continue

        matched = left_vals & right_vals
        coverage = len(matched) / len(left_vals)
        passed = coverage >= min_coverage

        results.append({
            "check": check_name,
            "category": "referential",
            "file": check["left_file"],
            "passed": passed,
            "message": (
                f"Join coverage {coverage:.2%} below minimum {min_coverage:.2%}. "
                f"{len(left_vals) - len(matched)} unmatched keys."
                if not passed
                else f"Join coverage {coverage:.2%} meets minimum {min_coverage:.2%}"
            ),
        })

    return results


def check_output_freshness(repo_path: str, expectations: dict) -> list[dict]:
    import time
    results = []
    freshness_checks = expectations.get("freshness", [])

    for check in freshness_checks:
        filepath = os.path.join(repo_path, "outputs", check["file"])
        max_age_hours = check.get("max_age_hours", 24)
        check_name = f"freshness:{check['file']}"

        if not os.path.exists(filepath):
            results.append({
                "check": check_name,
                "category": "referential",
                "file": check["file"],
                "passed": False,
                "message": f"Output file not found: {check['file']}",
            })
            continue

        modified_at = os.path.getmtime(filepath)
        age_hours = (time.time() - modified_at) / 3600
        passed = age_hours <= max_age_hours

        results.append({
            "check": check_name,
            "category": "referential",
            "file": check["file"],
            "passed": passed,
            "message": (
                f"Output '{check['file']}' is {age_hours:.1f}h old, "
                f"exceeds max {max_age_hours}h"
                if not passed
                else f"Output '{check['file']}' is {age_hours:.1f}h old, within bounds"
            ),
        })

    return results


def run_referential_checks(repo_path: str) -> list[dict]:
    expectations = _load_expectations(repo_path)
    results = []

    results.extend(check_foreign_keys(repo_path, expectations))
    results.extend(check_join_coverage(repo_path, expectations))
    results.extend(check_output_freshness(repo_path, expectations))

    if not results:
        results.append({
            "check": "referential_checks",
            "category": "referential",
            "file": "N/A",
            "passed": True,
            "message": "No referential expectations defined. Skipped.",
        })

    return results