"""
CSV/record loading, column validation, date parsing, numeric validation, and
normalization into a clean internal DataFrame every other service can trust.

Core discipline, per the task brief: **never silently drop a required
record with bad data.** A row-level problem in a REQUIRED field is collected
and raised as part of one clear, specific DatasetValidationError — never
quietly dropped or coerced. Missing OPTIONAL fields get documented defaults
(app/config.py's DEFAULT_* settings) instead of being rejected, since a
missing optional field is a normal, expected case (e.g. an unresolved
complaint genuinely has no resolvedAt yet).
"""
import io
from pathlib import Path
from typing import List, Union

import pandas as pd

from app.config import settings
from app.schemas.analytics_schema import (
    ComplaintStatus,
    LocationSensitivity,
    REQUIRED_COLUMNS,
    SeverityLevel,
)


class DatasetValidationError(ValueError):
    """Raised with a clear, specific, multi-issue message — never a single
    vague 'invalid data' string. Every issue names the column and the exact
    row index(es) affected."""


def load_csv(source: Union[str, Path, bytes, bytearray, io.IOBase]) -> pd.DataFrame:
    """Loads a CSV from a file path, raw bytes (e.g. an uploaded file's
    contents), or an already-open buffer. Raises DatasetValidationError (not
    a raw pandas exception) on anything that isn't parseable as CSV at all."""
    try:
        if isinstance(source, (bytes, bytearray)):
            return pd.read_csv(io.BytesIO(source))
        return pd.read_csv(source)
    except DatasetValidationError:
        raise
    except Exception as e:
        raise DatasetValidationError(f"Could not parse file as CSV: {e}")


def records_to_dataframe(records: List[dict]) -> pd.DataFrame:
    if not records:
        raise DatasetValidationError("No records provided — nothing to analyze.")
    return pd.DataFrame.from_records(records)


def validate_not_empty(df: pd.DataFrame) -> None:
    if len(df) == 0:
        raise DatasetValidationError("Dataset is empty — no rows to analyze.")


def validate_columns(df: pd.DataFrame) -> None:
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise DatasetValidationError(
            f"Dataset is missing required column(s): {missing}. "
            f"Required columns are: {list(REQUIRED_COLUMNS)}."
        )


def _is_blank(series: pd.Series) -> pd.Series:
    return series.isna() | (series.astype(str).str.strip() == "")


def validate_required_fields(df: pd.DataFrame) -> None:
    """Row-level validation of every REQUIRED column. Collects every problem
    found across every column into ONE raised error, rather than stopping at
    the first issue (a user fixing a malformed CSV wants the whole list, not
    one problem at a time)."""
    errors: List[str] = []

    id_blank_rows = df.index[_is_blank(df["id"])].tolist()
    if id_blank_rows:
        errors.append(f"Column 'id' is missing/empty for row(s): {id_blank_rows}")

    duplicate_ids = df["id"][df["id"].duplicated(keep=False)].dropna().unique().tolist()
    if duplicate_ids:
        errors.append(f"Column 'id' must be unique — duplicate value(s) found: {duplicate_ids}")

    for column in ("category", "department", "area"):
        blank_rows = df.index[_is_blank(df[column])].tolist()
        if blank_rows:
            errors.append(f"Column '{column}' is missing/empty for row(s): {blank_rows}")

    valid_severities = {s.value for s in SeverityLevel}
    invalid_severity_rows = df.index[~df["severity"].isin(valid_severities)].tolist()
    if invalid_severity_rows:
        errors.append(
            f"Column 'severity' has invalid/missing value(s) for row(s) {invalid_severity_rows} "
            f"(must be one of {sorted(valid_severities)})"
        )

    valid_statuses = {s.value for s in ComplaintStatus}
    invalid_status_rows = df.index[~df["status"].isin(valid_statuses)].tolist()
    if invalid_status_rows:
        errors.append(
            f"Column 'status' has invalid/missing value(s) for row(s) {invalid_status_rows} "
            f"(must be one of {sorted(valid_statuses)})"
        )

    if errors:
        raise DatasetValidationError("Dataset failed validation:\n- " + "\n- ".join(errors))


def parse_dates(df: pd.DataFrame) -> pd.DataFrame:
    """createdAt is REQUIRED — every row must have a parseable date, or the
    whole dataset is rejected with the exact offending row indices.
    resolvedAt is OPTIONAL — genuinely blank is fine (not yet resolved), but
    a value that's PRESENT and unparseable is a real data problem, not a
    silently-ignored one.

    IMPORTANT: uses format="mixed" — pandas' default date parsing infers ONE
    format from the column and silently returns NaT for any row in a
    different (but still perfectly valid) format, e.g. a column mixing
    "...Z" and "...+00:00" timestamps. That's exactly the kind of messy,
    real-world CSV data this validation exists to handle correctly, not
    reject as if every row were actually broken (a real bug caught by this
    project's own test suite, not a hypothetical concern)."""
    df = df.copy()

    parsed_created = pd.to_datetime(df["createdAt"], errors="coerce", utc=True, format="mixed")
    bad_created_rows = df.index[parsed_created.isna()].tolist()
    if bad_created_rows:
        raise DatasetValidationError(
            f"Column 'createdAt' has missing/unparseable date value(s) for row(s): {bad_created_rows}"
        )
    df["createdAt"] = parsed_created

    if "resolvedAt" in df.columns:
        originally_blank = _is_blank(df["resolvedAt"])
        parsed_resolved = pd.to_datetime(df["resolvedAt"], errors="coerce", utc=True, format="mixed")
        bad_resolved_rows = df.index[parsed_resolved.isna() & ~originally_blank].tolist()
        if bad_resolved_rows:
            raise DatasetValidationError(
                f"Column 'resolvedAt' has unparseable (non-blank) date value(s) for row(s): {bad_resolved_rows}"
            )
        df["resolvedAt"] = parsed_resolved
    else:
        # documented default: missing resolvedAt column -> "not resolved" for
        # every row. Built via to_datetime (not a bare `pd.NaT` scalar
        # assignment) specifically to get the SAME tz-aware dtype as
        # `createdAt` above — a bare `df["resolvedAt"] = pd.NaT` produces a
        # naive datetime64[ns] column, which then raises a real
        # TypeError the moment it's compared against a tz-aware column
        # below (caught by this project's own test suite, not hypothetical).
        df["resolvedAt"] = pd.to_datetime(pd.Series([None] * len(df), index=df.index), utc=True)

    both_present = df["resolvedAt"].notna() & df["createdAt"].notna()
    inverted_rows = df.index[both_present & (df["resolvedAt"] < df["createdAt"])].tolist()
    if inverted_rows:
        raise DatasetValidationError(
            f"Column 'resolvedAt' is BEFORE 'createdAt' for row(s): {inverted_rows} — logically invalid data."
        )

    return df


def validate_and_default_numeric(df: pd.DataFrame) -> pd.DataFrame:
    """supportCount/affectedUsers: missing -> documented default (see
    app/config.py). PRESENT but non-numeric or negative -> a real validation
    error, never silently coerced away (a garbled number is a data-quality
    problem worth surfacing, not hiding behind a default)."""
    df = df.copy()

    for column, default in (
        ("supportCount", settings.DEFAULT_SUPPORT_COUNT),
        ("affectedUsers", settings.DEFAULT_AFFECTED_USERS),
    ):
        if column not in df.columns:
            df[column] = default
            continue

        raw = df[column]
        blank = _is_blank(raw)
        numeric = pd.to_numeric(raw, errors="coerce")

        invalid_rows = df.index[numeric.isna() & ~blank].tolist()
        if invalid_rows:
            raise DatasetValidationError(
                f"Column '{column}' has non-numeric value(s) for row(s): {invalid_rows}"
            )

        negative_rows = df.index[(numeric < 0) & ~blank].tolist()
        if negative_rows:
            raise DatasetValidationError(
                f"Column '{column}' has negative value(s) for row(s): {negative_rows} — must be >= 0."
            )

        df[column] = numeric.fillna(default).astype(int)

    return df


def apply_categorical_defaults(df: pd.DataFrame) -> pd.DataFrame:
    """locationSensitivity: missing -> documented default 'Medium'. PRESENT
    but not one of Low/Medium/High is a real validation error."""
    df = df.copy()
    valid_values = {s.value for s in LocationSensitivity}

    if "locationSensitivity" not in df.columns:
        df["locationSensitivity"] = settings.DEFAULT_LOCATION_SENSITIVITY
        return df

    blank = _is_blank(df["locationSensitivity"])
    invalid_rows = df.index[~blank & ~df["locationSensitivity"].isin(valid_values)].tolist()
    if invalid_rows:
        raise DatasetValidationError(
            f"Column 'locationSensitivity' has invalid value(s) for row(s): {invalid_rows} "
            f"(must be one of {sorted(valid_values)})"
        )
    df.loc[blank, "locationSensitivity"] = settings.DEFAULT_LOCATION_SENSITIVITY
    return df


def normalize_records(df: pd.DataFrame) -> pd.DataFrame:
    """The single entry point every caller should use. Raises
    DatasetValidationError with a clear, specific message on any problem;
    returns a fully normalized, analysis-ready DataFrame otherwise."""
    validate_not_empty(df)
    validate_columns(df)
    validate_required_fields(df)
    df = parse_dates(df)
    df = validate_and_default_numeric(df)
    df = apply_categorical_defaults(df)
    return df.reset_index(drop=True)


def load_and_normalize_csv(source: Union[str, Path, bytes, bytearray, io.IOBase]) -> pd.DataFrame:
    return normalize_records(load_csv(source))


def load_and_normalize_records(records: List[dict]) -> pd.DataFrame:
    return normalize_records(records_to_dataframe(records))
