"""
Validates the raw dataset and produces a stratified train/validation/test
split with NO overlap between splits (a duplicate text is a real form of
data leakage — if a near-identical row appears in both train and test, the
test-set accuracy would be measuring memorization, not generalization).

Run:
    python training/split_dataset.py
Reads data/raw/complaints.csv, writes data/processed/{train,val,test}.csv.
"""
import sys
from pathlib import Path
from typing import Tuple

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings
from app.schemas.analysis_schema import ComplaintCategory, Department, SeverityLevel

REQUIRED_COLUMNS = ("text", "category", "severity", "department")
VALID_CATEGORIES = {c.value for c in ComplaintCategory}
VALID_SEVERITIES = {s.value for s in SeverityLevel}
VALID_DEPARTMENTS = {d.value for d in Department}


class DatasetValidationError(ValueError):
    pass


def validate_dataset(df: pd.DataFrame) -> None:
    """Raises DatasetValidationError with a clear, specific message on any
    problem — never silently proceeds with a malformed dataset."""
    missing_columns = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing_columns:
        raise DatasetValidationError(f"Dataset is missing required column(s): {missing_columns}")

    if len(df) == 0:
        raise DatasetValidationError("Dataset is empty.")

    empty_text_count = df["text"].isna().sum() + (df["text"].astype(str).str.strip() == "").sum()
    if empty_text_count > 0:
        raise DatasetValidationError(f"Dataset contains {empty_text_count} row(s) with empty/missing text.")

    for column, valid_values in (
        ("category", VALID_CATEGORIES),
        ("severity", VALID_SEVERITIES),
        ("department", VALID_DEPARTMENTS),
    ):
        invalid = set(df[column].unique()) - valid_values
        if invalid:
            raise DatasetValidationError(f"Column '{column}' contains unrecognized value(s): {invalid}")

    for column in ("category", "severity", "department"):
        counts = df[column].value_counts()
        too_few = counts[counts < 3]
        if not too_few.empty:
            raise DatasetValidationError(
                f"Column '{column}' has label(s) with fewer than 3 examples "
                f"(cannot be safely split 3 ways): {too_few.to_dict()}"
            )


def deduplicate(df: pd.DataFrame) -> pd.DataFrame:
    """Drops exact-duplicate text rows BEFORE splitting — the single most
    direct source of train/test leakage for a text classifier."""
    before = len(df)
    df = df.drop_duplicates(subset=["text"]).reset_index(drop=True)
    removed = before - len(df)
    if removed:
        print(f"Removed {removed} duplicate text row(s) before splitting.")
    return df


def stratified_split(
    df: pd.DataFrame, train_ratio: float, val_ratio: float, test_ratio: float, seed: int
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Splits WITHIN each category so every split has a representative mix of
    categories (a plain random split could, by chance, starve one category
    from the test set entirely)."""
    total = train_ratio + val_ratio + test_ratio
    if abs(total - 1.0) > 1e-6:
        raise DatasetValidationError(f"train/val/test ratios must sum to 1.0, got {total}")

    train_parts, val_parts, test_parts = [], [], []
    for _, group in df.groupby("category"):
        shuffled = group.sample(frac=1.0, random_state=seed).reset_index(drop=True)
        n = len(shuffled)
        n_train = int(round(n * train_ratio))
        n_val = int(round(n * val_ratio))
        train_parts.append(shuffled.iloc[:n_train])
        val_parts.append(shuffled.iloc[n_train:n_train + n_val])
        test_parts.append(shuffled.iloc[n_train + n_val:])

    train_df = pd.concat(train_parts).sample(frac=1.0, random_state=seed).reset_index(drop=True)
    val_df = pd.concat(val_parts).sample(frac=1.0, random_state=seed).reset_index(drop=True)
    test_df = pd.concat(test_parts).sample(frac=1.0, random_state=seed).reset_index(drop=True)
    return train_df, val_df, test_df


def assert_no_leakage(train_df: pd.DataFrame, val_df: pd.DataFrame, test_df: pd.DataFrame) -> None:
    train_texts = set(train_df["text"])
    val_texts = set(val_df["text"])
    test_texts = set(test_df["text"])
    overlap_train_val = train_texts & val_texts
    overlap_train_test = train_texts & test_texts
    overlap_val_test = val_texts & test_texts
    if overlap_train_val or overlap_train_test or overlap_val_test:
        raise DatasetValidationError(
            "Data leakage detected between splits: "
            f"train∩val={len(overlap_train_val)}, train∩test={len(overlap_train_test)}, "
            f"val∩test={len(overlap_val_test)}"
        )


def main():
    raw_path = Path(settings.RAW_DATA_DIR) / "complaints.csv"
    if not raw_path.exists():
        raise FileNotFoundError(
            f"{raw_path} not found — run training/generate_synthetic_dataset.py first, "
            "or place your own labelled data/raw/complaints.csv (see README.md)."
        )

    df = pd.read_csv(raw_path)
    validate_dataset(df)
    df = deduplicate(df)

    train_df, val_df, test_df = stratified_split(
        df, settings.TRAIN_RATIO, settings.VAL_RATIO, settings.TEST_RATIO, settings.SPLIT_RANDOM_SEED
    )
    assert_no_leakage(train_df, val_df, test_df)

    processed_dir = Path(settings.PROCESSED_DATA_DIR)
    processed_dir.mkdir(parents=True, exist_ok=True)
    train_df.to_csv(processed_dir / "train.csv", index=False)
    val_df.to_csv(processed_dir / "val.csv", index=False)
    test_df.to_csv(processed_dir / "test.csv", index=False)

    print(f"Validated {len(df)} rows (post-dedup).")
    print(f"Split: train={len(train_df)}, val={len(val_df)}, test={len(test_df)}")
    print("No leakage between splits — confirmed.")
    print(f"Written to {processed_dir}/")


if __name__ == "__main__":
    main()
