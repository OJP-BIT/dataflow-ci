import logging
import os
import glob
from typing import Any

import pandas as pd
import numpy as np

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


def _load_expectations(repo_path: str) -> dict[str, Any]:
    expectations_path = os.path.join(repo_path, "dataflow_expectations.yml")
    if os.path.exists(expectations_path):
        import yaml
        with open(expectations_path) as f:
            return yaml.safe_load(f)
    return {}


def check_value_ranges(df: pd.DataFrame, filename: str, expectations: dict) -> list[dict]:
    file_key = os.path.basename(filename)
    columns = expectations.get(file_key, {}).get("columns", {})
    results = []

    for col, spec in columns.items():
        if col not in df.columns:
            continue

        min_val = spec.get("min_value")
        max_val = spec.get("max_value")

        if min_val is None and max_val is None:
            continue

        series = df[col].dropna()

        if min_val is not None:
            violations = int((series < min_val).sum())
            passed = violations == 0
            results.append({
                "check": f"value_range_min:{col}",
                "category": "statistical",
                "file": file_key,
                "passed": passed,
                "message": (
                    f"Column '{col}' has {violations} values below minimum {min_val}"
                    if not passed
                    else f"Column '{col}' all values >= {min_val}"
                ),
            })

        if max_val is not None:
            violations = int((series > max_val).sum())
            passed = violations == 0
            results.append({
                "check": f"value_range_max:{col}",
                "category": "statistical",
                "file": file_key,
                "passed": passed,
                "message": (
                    f"Column '{col}' has {violations} values above maximum {max_val}"
                    if not passed
                    else f"Column '{col}' all values <= {max_val}"
                ),
            })

    return results


def check_distribution_bounds(df: pd.DataFrame, filename: str, expectations: dict) -> list[dict]:
    file_key = os.path.basename(filename)
    columns = expectations.get(file_key, {}).get("columns", {})
    results = []

    for col, spec in columns.items():
        if col not in df.columns:
            continue

        series = df[col].dropna()
        if not pd.api.types.is_numeric_dtype(series):
            continue

        actual_mean = float(series.mean())
        actual_std = float(series.std())

        mean_min = spec.get("mean_min")
        mean_max = spec.get("mean_max")
        std_max = spec.get("std_max")

        if mean_min is not None:
            passed = actual_mean >= mean_min
            results.append({
                "check": f"mean_lower_bound:{col}",
                "category": "statistical",
                "file": file_key,
                "passed": passed,
                "message": (
                    f"Column '{col}' mean {actual_mean:.4f} below lower bound {mean_min}"
                    if not passed
                    else f"Column '{col}' mean {actual_mean:.4f} >= {mean_min}"
                ),
            })

        if mean_max is not None:
            passed = actual_mean <= mean_max
            results.append({
                "check": f"mean_upper_bound:{col}",
                "category": "statistical",
                "file": file_key,
                "passed": passed,
                "message": (
                    f"Column '{col}' mean {actual_mean:.4f} exceeds upper bound {mean_max}"
                    if not passed
                    else f"Column '{col}' mean {actual_mean:.4f} <= {mean_max}"
                ),
            })

        if std_max is not None:
            passed = actual_std <= std_max
            results.append({
                "check": f"std_upper_bound:{col}",
                "category": "statistical",
                "file": file_key,
                "passed": passed,
                "message": (
                    f"Column '{col}' std {actual_std:.4f} exceeds max {std_max}"
                    if not passed
                    else f"Column '{col}' std {actual_std:.4f} within bounds"
                ),
            })

    return results


def check_outliers(df: pd.DataFrame, filename: str, expectations: dict) -> list[dict]:
    file_key = os.path.basename(filename)
    columns = expectations.get(file_key, {}).get("columns", {})
    results = []

    for col, spec in columns.items():
        if col not in df.columns:
            continue
        if not spec.get("check_outliers", False):
            continue

        series = df[col].dropna()
        if not pd.api.types.is_numeric_dtype(series):
            continue

        max_outlier_ratio = spec.get("max_outlier_ratio", 0.05)
        q1 = series.quantile(0.25)
        q3 = series.quantile(0.75)
        iqr = q3 - q1
        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr

        outlier_count = int(((series < lower) | (series > upper)).sum())
        outlier_ratio = outlier_count / len(series) if len(series) > 0 else 0
        passed = outlier_ratio <= max_outlier_ratio

        results.append({
            "check": f"outlier_ratio:{col}",
            "category": "statistical",
            "file": file_key,
            "passed": passed,
            "message": (
                f"Column '{col}' outlier ratio {outlier_ratio:.2%} exceeds "
                f"threshold {max_outlier_ratio:.2%}"
                if not passed
                else f"Column '{col}' outlier ratio {outlier_ratio:.2%} within threshold"
            ),
        })

    return results


def check_categorical_coverage(df: pd.DataFrame, filename: str, expectations: dict) -> list[dict]:
    file_key = os.path.basename(filename)
    columns = expectations.get(file_key, {}).get("columns", {})
    results = []

    for col, spec in columns.items():
        if col not in df.columns:
            continue

        allowed_values = spec.get("allowed_values")
        if not allowed_values:
            continue

        actual_values = set(df[col].dropna().unique().tolist())
        unexpected = actual_values - set(allowed_values)
        passed = len(unexpected) == 0

        results.append({
            "check": f"categorical_values:{col}",
            "category": "statistical",
            "file": file_key,
            "passed": passed,
            "message": (
                f"Column '{col}' has unexpected values: {unexpected}"
                if not passed
                else f"Column '{col}' values within allowed set"
            ),
        })

    return results


def run_statistical_checks(repo_path: str) -> list[dict]:
    expectations = _load_expectations(repo_path)
    output_files = _find_output_files(repo_path)

    if not output_files:
        return []

    results = []
    for filepath in output_files:
        try:
            if filepath.endswith(".parquet"):
                df = pd.read_parquet(filepath)
            else:
                df = pd.read_csv(filepath)

            results.extend(check_value_ranges(df, filepath, expectations))
            results.extend(check_distribution_bounds(df, filepath, expectations))
            results.extend(check_outliers(df, filepath, expectations))
            results.extend(check_categorical_coverage(df, filepath, expectations))

        except Exception as e:
            results.append({
                "check": "statistical_check_error",
                "category": "statistical",
                "file": os.path.basename(filepath),
                "passed": False,
                "message": f"Error running statistical checks: {e}",
            })

    return results