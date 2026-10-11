"""Intent prediction using trained classifiers."""

import joblib
import os
from sklearn.metrics import accuracy_score, f1_score


def load_model(model_name, model_dir="models/intent_classifier"):
    """Load a trained classifier."""
    # Check if model directory exists
    if not os.path.exists(model_dir):
        raise FileNotFoundError(f"Model directory not found: {model_dir}")
    
    # Check if the specific model file exists
    model_path = os.path.join(model_dir, f"{model_name}.pkl")
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Model file not found: {model_path}")
    
    return joblib.load(model_path)


def load_vectorizer(vectorizer_path="models/vectorizer.pkl"):
    """Load the fitted TF-IDF vectorizer."""
    if not os.path.exists(vectorizer_path):
        raise FileNotFoundError(f"Vectorizer file not found: {vectorizer_path}")
    return joblib.load(vectorizer_path)


def predict_intent(text, model, vectorizer):
    """Predict intent for a given text.
    
    Returns:
        tuple: (predicted_intent, confidence_score)
    """
    if model is None or vectorizer is None:
        return "unknown", 0.0
    
    try:
        # Transform text using the vectorizer
        features = vectorizer.transform([text])
        
        # Get prediction
        pred = model.predict(features)[0]
        
        # Get confidence score
        if hasattr(model, "predict_proba"):
            proba = model.predict_proba(features).max()
        elif hasattr(model, "decision_function"):
            # For SVM-like models
            confidence = model.decision_function(features)[0]
            proba = (confidence - confidence.min()) / (confidence.max() - confidence.min() + 1e-8)
        else:
            # Fallback to 0.0 if no confidence score available
            proba = 0.0
            
        return pred, proba
    except Exception as e:
        print(f"Warning: prediction failed for text '{text}': {e}")
        return "unknown", 0.0


def evaluate_model(model, X_test, y_test):
    """Evaluate model performance on test data.
    
    Returns:
        dict: Dictionary containing accuracy and F1 score
    """
    if model is None:
        return {"accuracy": 0.0, "f1_score": 0.0}
    
    try:
        # Get predictions
        preds = model.predict(X_test)
        
        # Calculate metrics
        accuracy = accuracy_score(y_test, preds)
        f1 = f1_score(y_test, preds, average="weighted")
        
        return {
            "accuracy": accuracy,
            "f1_score": f1,
            "predictions": preds.tolist()
        }
    except Exception as e:
        print(f"Warning: evaluation failed: {e}")
        return {"accuracy": 0.0, "f1_score": 0.0, "predictions": []}
