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


def _load_expectations(repo_path: str) -> dict[str, Any]:
    expectations_path = os.path.join(repo_path, "dataflow_expectations.yml")
    if os.path.exists(expectations_path):
        import yaml
        with open(expectations_path) as f:
            return yaml.safe_load(f)
    return {}


def check_schema(df: pd.DataFrame, filename: str, expectations: dict) -> list[dict]:
    results = []
    file_key = os.path.basename(filename)
    expected_columns = expectations.get(file_key, {}).get("columns", {})

    if not expected_columns:
        results.append({
            "check": "schema_definition",
            "category": "structural",
            "file": file_key,
            "passed": True,
            "message": "No schema expectations defined. Skipped.",
        })
        return results

    for col, spec in expected_columns.items():
        exists = col in df.columns
        results.append({
            "check": f"column_exists:{col}",
            "category": "structural",
            "file": file_key,
            "passed": exists,
            "message": f"Column '{col}' {'found' if exists else 'MISSING'} in {file_key}",
        })
        if not exists:
            continue

        if "dtype" in spec:
            actual_dtype = str(df[col].dtype)
            expected_dtype = spec["dtype"]
            dtype_ok = expected_dtype in actual_dtype
            results.append({
                "check": f"column_dtype:{col}",
                "category": "structural",
                "file": file_key,
                "passed": dtype_ok,
                "message": (
                    f"Column '{col}' dtype is '{actual_dtype}', "
                    f"expected '{expected_dtype}'"
                ),
            })

        if spec.get("nullable") is False:
            null_count = int(df[col].isna().sum())
            passed = null_count == 0
            results.append({
                "check": f"column_not_null:{col}",
                "category": "structural",
                "file": file_key,
                "passed": passed,
                "message": (
                    f"Column '{col}' has {null_count} nulls"
                    if not passed
                    else f"Column '{col}' has no nulls"
                ),
            })

    return results


def check_row_count(df: pd.DataFrame, filename: str, expectations: dict) -> list[dict]:
    file_key = os.path.basename(filename)
    file_exp = expectations.get(file_key, {})
    row_count = len(df)
    results = []

    min_rows = file_exp.get("min_rows")
    max_rows = file_exp.get("max_rows")

    if min_rows is not None:
        passed = row_count >= min_rows
        results.append({
            "check": "row_count_minimum",
            "category": "structural",
            "file": file_key,
            "passed": passed,
            "message": f"Row count {row_count} {'>=' if passed else '<'} minimum {min_rows}",
        })

    if max_rows is not None:
        passed = row_count <= max_rows
        results.append({
            "check": "row_count_maximum",
            "category": "structural",
            "file": file_key,
            "passed": passed,
            "message": f"Row count {row_count} {'<=' if passed else '>'} maximum {max_rows}",
        })

    if min_rows is None and max_rows is None:
        results.append({
            "check": "row_count",
            "category": "structural",
            "file": file_key,
            "passed": row_count > 0,
            "message": f"Row count: {row_count}",
        })

    return results


def check_primary_key(df: pd.DataFrame, filename: str, expectations: dict) -> list[dict]:
    file_key = os.path.basename(filename)
    pk_cols = expectations.get(file_key, {}).get("primary_key", [])

    if not pk_cols:
        return []

    present = [c for c in pk_cols if c in df.columns]
    if len(present) != len(pk_cols):
        missing = set(pk_cols) - set(present)
        return [{
            "check": "primary_key_columns_exist",
            "category": "structural",
            "file": file_key,
            "passed": False,
            "message": f"Primary key columns missing: {missing}",
        }]

    duplicate_count = int(df.duplicated(subset=pk_cols).sum())
    passed = duplicate_count == 0
    return [{
        "check": "primary_key_uniqueness",
        "category": "structural",
        "file": file_key,
        "passed": passed,
        "message": (
            f"Primary key {pk_cols} has {duplicate_count} duplicates"
            if not passed
            else f"Primary key {pk_cols} is unique"
        ),
    }]


def run_structural_checks(repo_path: str) -> list[dict]:
    expectations = _load_expectations(repo_path)
    output_files = _find_output_files(repo_path)

    if not output_files:
        return [{
            "check": "outputs_exist",
            "category": "structural",
            "file": "outputs/",
            "passed": False,
            "message": "No output files found in outputs/ directory",
        }]

    results = []
    for filepath in output_files:
        try:
            if filepath.endswith(".parquet"):
                df = pd.read_parquet(filepath)
            else:
                df = pd.read_csv(filepath)

            results.extend(check_schema(df, filepath, expectations))
            results.extend(check_row_count(df, filepath, expectations))
            results.extend(check_primary_key(df, filepath, expectations))

        except Exception as e:
            results.append({
                "check": "file_readable",
                "category": "structural",
                "file": os.path.basename(filepath),
                "passed": False,
                "message": f"Could not read file: {e}",
            })

    return results