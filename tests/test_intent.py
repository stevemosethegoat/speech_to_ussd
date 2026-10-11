"""Tests for intent module."""

import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import numpy as np
from sklearn.datasets import make_classification

from src.intent.features import extract_features
from src.intent.predict import (
    load_model, load_vectorizer, predict_intent, evaluate_model
)


def test_extract_features():
    texts = ["hello world", "send money"]
    features, vectorizer = extract_features(texts)
    assert features.shape[0] == 2


def test_predict_intent_with_mock_model():
    """Test predict_intent with a mock model and vectorizer."""
    # Create mock objects
    mock_model = Mock()
    mock_model.predict_proba.return_value = np.array([[0.1, 0.9]])  # [send_money: 0.9]
    
    mock_vectorizer = Mock()
    mock_vectorizer.transform.return_value = [[0.1, 0.2, 0.3]]
    
    # Test prediction
    intent, confidence = predict_intent("send money", mock_model, mock_vectorizer)
    
    assert intent == "send_money" or intent == "SEND_MONEY"
    assert confidence == 0.9
    assert mock_vectorizer.transform.called


def test_predict_intent_with_mock_svm_model():
    """Test predict_intent with a mock SVM-like model."""
    # Create mock objects for SVM-like model
    mock_model = Mock()
    mock_model.predict_proba = None  # No predict_proba for SVM
    mock_model.decision_function.return_value = np.array([0.5])  # Confidence
    
    mock_vectorizer = Mock()
    mock_vectorizer.transform.return_value = [[0.1, 0.2, 0.3]]
    
    # Test prediction
    intent, confidence = predict_intent("send money", mock_model, mock_vectorizer)
    
    assert intent == "send_money" or intent == "SEND_MONEY"
    assert 0.0 <= confidence <= 1.0
    assert mock_vectorizer.transform.called


def test_predict_intent_with_none_model():
    """Test predict_intent when model is None."""
    intent, confidence = predict_intent("send money", None, None)
    
    assert intent == "unknown"
    assert confidence == 0.0


def test_predict_intent_with_exception():
    """Test predict_intent when model raises an exception."""
    # Create mock objects that will raise an exception
    mock_model = Mock()
    mock_model.predict.side_effect = Exception("Model error")
    
    mock_vectorizer = Mock()
    
    # Test prediction with exception handling
    intent, confidence = predict_intent("send money", mock_model, mock_vectorizer)
    
    assert intent == "unknown"
    assert confidence == 0.0


def test_load_model_with_valid_path(tmpdir):
    """Test load_model with a valid model file."""
    # Create a temporary directory with a mock model file
    model_dir = Path(tmpdir) / "test_models"
    model_dir.mkdir()
    
    # Create a mock model file
    model_path = model_dir / "test_model.pkl"
    
    # Create mock model data
    mock_model = Mock()
    mock_model.predict = Mock(return_value=[0, 1, 0])
    
    # Save mock model using joblib
    import joblib
    joblib.dump(mock_model, str(model_path))
    
    # Test loading
    loaded_model = load_model("test_model", str(model_dir))
    assert loaded_model is not None


def test_load_model_with_invalid_path():
    """Test load_model with an invalid model directory."""
    # Test with non-existent directory
    with pytest.raises(FileNotFoundError):
        load_model("test_model", "/non/existent/path")
    
    # Test with existent directory but non-existent model file
    with tempfile.TemporaryDirectory() as tmpdir:
        with pytest.raises(FileNotFoundError):
            load_model("test_model", tmpdir)


def test_load_vectorizer():
    """Test load_vectorizer with a valid vectorizer file."""
    # Create a temporary directory with a mock vectorizer file
    with tempfile.TemporaryDirectory() as tmpdir:
        vectorizer_path = Path(tmpdir) / "vectorizer.pkl"
        
        # Create a mock vectorizer
        mock_vectorizer = Mock()
        
        # Save mock vectorizer using joblib
        import joblib
        joblib.dump(mock_vectorizer, str(vectorizer_path))
        
        # Test loading
        loaded_vectorizer = load_vectorizer(str(vectorizer_path))
        assert loaded_vectorizer is not None


def test_evaluate_model():
    """Test evaluate_model with mock data."""
    # Create mock model
    mock_model = Mock()
    mock_model.predict.return_value = np.array([0, 1, 0, 1])
    
    # Create mock test data
    X_test = np.random.rand(4, 10)
    y_test = np.array([0, 1, 0, 1])
    
    # Test evaluation
    result = evaluate_model(mock_model, X_test, y_test)
    
    assert "accuracy" in result
    assert "f1_score" in result
    assert "predictions" in result
    assert len(result["predictions"]) == 4
    assert result["accuracy"] > 0


def test_evaluate_model_with_none_model():
    """Test evaluate_model with None model."""
    result = evaluate_model(None, np.array([[1, 2, 3]]), np.array([0]))
    
    assert result["accuracy"] == 0.0
    assert result["f1_score"] == 0.0


def test_predict_intent_with_real_sample():
    """Integration test with real sample data."""
    # Sample texts and expected intents
    test_cases = [
        ("check my balance", "CHECK_BALANCE"),
        ("send 5000 to john", "SEND_MONEY"),
        ("buy airtime", "BUY_AIRTIME"),
    ]
    
    for text, expected_intent in test_cases:
        # Mock the model and vectorizer
        mock_model = Mock()
        mock_model.predict.return_value = [expected_intent]
        mock_model.predict_proba.return_value = np.array([[0.1, 0.1, 0.8]])
        
        mock_vectorizer = Mock()
        mock_vectorizer.transform.return_value = [[0.1, 0.2, 0.3]]
        
        intent, confidence = predict_intent(text, mock_model, mock_vectorizer)
        
        # Should return the expected intent (case insensitive)
        assert intent.upper() == expected_intent.upper()
        assert 0.0 <= confidence <= 1.0
