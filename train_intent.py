"""Train the intent classifier from the processed CSV.

Produces:
    models/intent_classifier/<model_name>.pkl   (sklearn model)
    models/vectorizer.pkl                        (fitted TfidfVectorizer)
"""

import pandas as pd
import joblib
from pathlib import Path
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, f1_score, classification_report


def main():
    # ---- Load data ----
    csv_path = "data/processed/intent_train.csv"
    df = pd.read_csv(csv_path)
    print(f"Loaded {len(df)} rows from {csv_path}")
    print(f"\nIntent distribution:\n{df['intent'].value_counts()}\n")

    # Prefer the cleaned transcript, fall back to raw
    text_col = "clean_transcript" if "clean_transcript" in df.columns else "transcript"
    df = df.dropna(subset=[text_col, "intent"])
    X_text = df[text_col].astype(str).tolist()
    y = df["intent"].astype(str).tolist()

    # ---- Vectorize ----
    vectorizer = TfidfVectorizer(ngram_range=(1, 2), max_features=1000)
    X = vectorizer.fit_transform(X_text)
    print(f"Feature matrix: {X.shape}")

    # ---- Split ----
    X_train, X_val, y_train, y_val = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    # ---- Train models ----
    models = {
        "logistic_regression": LogisticRegression(
            max_iter=1000, class_weight="balanced"
        ),
        "decision_tree": DecisionTreeClassifier(
            random_state=42, class_weight="balanced", max_depth=10
        ),
        "random_forest": RandomForestClassifier(
            random_state=42, class_weight="balanced", n_estimators=200
        ),
    }

    results = {}
    for name, model in models.items():
        model.fit(X_train, y_train)
        preds = model.predict(X_val)
        acc = accuracy_score(y_val, preds)
        f1 = f1_score(y_val, preds, average="weighted")
        results[name] = {"acc": acc, "f1": f1}
        print(f"{name:20s}  acc={acc:.4f}  f1={f1:.4f}")

    # ---- Save all models + vectorizer ----
    model_dir = Path("models/intent_classifier")
    model_dir.mkdir(parents=True, exist_ok=True)

    for name, model in models.items():
        joblib.dump(model, model_dir / f"{name}.pkl")
        print(f"Saved {model_dir / f'{name}.pkl'}")

    # ⚠️ predict.py loads this from models/vectorizer.pkl
    joblib.dump(vectorizer, "models/vectorizer.pkl")
    print(f"Saved models/vectorizer.pkl")

    # ---- Save best model name ----
    best = max(results, key=lambda k: results[k]["f1"])
    (model_dir / "best_model.txt").write_text(best)
    print(f"\nBest model: {best}")

    # ---- Show report for the best ----
    print(f"\nClassification report ({best}):")
    print(classification_report(y_val, models[best].predict(X_val)))


if __name__ == "__main__":
    main()
