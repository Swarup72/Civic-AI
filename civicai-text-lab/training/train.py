"""
Trains the TF-IDF + Logistic Regression classifiers (category, severity,
department) on data/processed/train.csv and saves the artifacts
app/services/classifier_service.py expects to load:

    models/trained/vectorizer.pkl
    models/trained/category_model.pkl
    models/trained/severity_model.pkl
    models/trained/department_model.pkl
    models/trained/metadata.json

Does NOT touch data/processed/test.csv — that split is reserved entirely for
training/evaluate.py, so a reported test-set metric is never contaminated by
having influenced training in any way (not even via early stopping/model
selection, which is what data/processed/val.csv is for instead).

Run:
    python training/train.py
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings
from app.services.preprocessing_service import normalize_text

HEADS = ("category", "severity", "department")
MODEL_VERSION_PREFIX = "textlab-tfidf-logreg"


def _load_split(name: str) -> pd.DataFrame:
    path = Path(settings.PROCESSED_DATA_DIR) / f"{name}.csv"
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found — run training/split_dataset.py first "
            "(which itself requires training/generate_synthetic_dataset.py "
            "to have produced data/raw/complaints.csv, unless you've supplied your own)."
        )
    return pd.read_csv(path)


def main():
    train_df = _load_split("train")
    val_df = _load_split("val")

    # Preprocess with the EXACT SAME normalize_text() the live API uses at
    # inference time - training on differently-processed text than what the
    # API will feed the model at request time is a subtle but real form of
    # train/serve skew.
    train_texts = train_df["text"].apply(normalize_text).tolist()
    val_texts = val_df["text"].apply(normalize_text).tolist()

    vectorizer = TfidfVectorizer(lowercase=False, ngram_range=(1, 2), min_df=2, max_features=8000)
    # lowercase=False: normalize_text() already lowercases - avoid doing it twice
    # and avoid the vectorizer's own tokenizer disagreeing with ours.
    X_train = vectorizer.fit_transform(train_texts)
    X_val = vectorizer.transform(val_texts)

    heads = {}
    val_accuracy = {}
    for head_name in HEADS:
        y_train = train_df[head_name]
        y_val = val_df[head_name]

        classifier = LogisticRegression(max_iter=1000, C=1.0)
        classifier.fit(X_train, y_train)
        heads[head_name] = classifier

        val_predictions = classifier.predict(X_val)
        val_accuracy[head_name] = round(float(accuracy_score(y_val, val_predictions)), 4)

    model_dir = Path(settings.MODEL_DIR)
    model_dir.mkdir(parents=True, exist_ok=True)

    joblib.dump(vectorizer, model_dir / "vectorizer.pkl")
    for head_name, classifier in heads.items():
        joblib.dump(classifier, model_dir / f"{head_name}_model.pkl")

    model_version = f"{MODEL_VERSION_PREFIX}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    metadata = {
        "modelVersion": model_version,
        "trainedAt": datetime.now(timezone.utc).isoformat(),
        "trainRows": len(train_df),
        "valRows": len(val_df),
        "heads": list(HEADS),
        "vectorizer": {
            "type": "TfidfVectorizer",
            "ngram_range": [1, 2],
            "min_df": 2,
            "max_features": 8000,
            "vocabularySize": len(vectorizer.vocabulary_),
        },
        "classifier": {"type": "LogisticRegression", "max_iter": 1000, "C": 1.0},
        # Validation-set accuracy is reported here for a quick sanity check
        # during training ONLY - the authoritative, held-out metric is
        # training/evaluate.py's report against data/processed/test.csv,
        # which this script never reads or trains on.
        "validationAccuracy": val_accuracy,
        "datasetNote": (
            "Trained on a synthetic, template-generated dataset "
            "(training/generate_synthetic_dataset.py) — category/department "
            "are template-driven and separate near-perfectly by design; "
            "severity has deliberate label noise and shared cross-category "
            "vocabulary, so its accuracy is a more honest, non-trivial "
            "number. See training/evaluate.py's report and README.md."
        ),
    }
    (model_dir / "metadata.json").write_text(json.dumps(metadata, indent=2))

    print(f"Saved model artifacts to {model_dir}/")
    print(f"Model version: {model_version}")
    print(f"Validation accuracy (sanity check only — see evaluate.py for the real test-set metrics):")
    for head_name, acc in val_accuracy.items():
        print(f"  {head_name}: {acc}")


if __name__ == "__main__":
    main()
