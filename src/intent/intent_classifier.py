"""Enhanced intent classifier with improved accuracy and robustness.

This module provides a complete intent classification pipeline with:
- Advanced text preprocessing
- Multiple model training with cross-validation
- Model evaluation with comprehensive metrics
- Confidence scoring and uncertainty estimation
- Model persistence and loading
- Feature importance analysis
"""

import os
import numpy as np
import joblib
from typing import Dict, List, Tuple, Optional, Union
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.model_selection import (
    train_test_split, cross_val_score, StratifiedKFold
)
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier, VotingClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.svm import SVC
from sklearn.metrics import (
    accuracy_score, f1_score, precision_score, recall_score,
    roc_auc_score, confusion_matrix, classification_report
)
import warnings
warnings.filterwarnings('ignore')


class EnhancedIntentClassifier:
    """Enhanced intent classifier with improved accuracy and robustness."""
    
    def __init__(self, ngram_range=(1, 2), max_features=1000, 
                 cv_folds=5, random_state=42):
        """Initialize the enhanced intent classifier.
        
        Args:
            ngram_range: Range of n-grams to use (default: (1, 2))
            max_features: Maximum number of features for TF-IDF (default: 1000)
            cv_folds: Number of cross-validation folds (default: 5)
            random_state: Random seed for reproducibility (default: 42)
        """
        self.ngram_range = ngram_range
        self.max_features = max_features
        self.cv_folds = cv_folds
        self.random_state = random_state
        
        # Model configurations
        self.model_configs = {
            "logistic_regression": {
                "model": LogisticRegression(
                    max_iter=2000, random_state=random_state,
                    class_weight='balanced'
                ),
                "params": {"C": 1.0, "solver": "liblinear"}
            },
            "decision_tree": {
                "model": DecisionTreeClassifier(
                    random_state=random_state,
                    class_weight='balanced',
                    max_depth=10
                ),
                "params": {"max_depth": 10, "min_samples_split": 5}
            },
            "random_forest": {
                "model": RandomForestClassifier(
                    random_state=random_state,
                    class_weight='balanced',
                    n_estimators=200
                ),
                "params": {"n_estimators": 200, "max_depth": 15}
            },
            "mlp": {
                "model": MLPClassifier(
                    hidden_layer_sizes=(100, 50),
                    max_iter=1000,
                    random_state=random_state,
                    alpha=0.0001
                ),
                "params": {"hidden_layer_sizes": (100, 50), "alpha": 0.0001}
            },
            "svm": {
                "model": SVC(
                    probability=True,
                    random_state=random_state,
                    class_weight='balanced'
                ),
                "params": {"C": 1.0, "kernel": "rbf", "gamma": "scale"}
            }
        }
        
        # Components
        self.vectorizer = None
        self.label_encoder = None
        self.trained_models = {}
        self.model_performance = {}
        self.is_trained = False
    
    def preprocess_text(self, text: str) -> str:
        """Preprocess and normalize text.
        
        Args:
            text: Input text to preprocess
            
        Returns:
            Preprocessed text
        """
        if not text or not isinstance(text, str):
            return ""
        
        # Convert to lowercase
        text = text.lower()
        
        # Remove extra whitespace
        text = " ".join(text.split())
        
        # Remove special characters but keep basic punctuation
        import re
        text = re.sub(r'[^\w\s\-\.]', ' ', text)
        
        return text
    
    def create_feature_matrix(self, texts: List[str], fit: bool = True) -> Tuple[np.ndarray, TfidfVectorizer]:
        """Create TF-IDF feature matrix from texts.
        
        Args:
            texts: List of text samples
            fit: Whether to fit the vectorizer or just transform
            
        Returns:
            Tuple of (feature_matrix, vectorizer)
        """
        # Preprocess texts
        processed_texts = [self.preprocess_text(text) for text in texts]
        
        # Create and fit/transform vectorizer
        self.vectorizer = TfidfVectorizer(
            ngram_range=self.ngram_range,
            max_features=self.max_features,
            stop_words=None,  # Keep all words for intent classification
            lowercase=True
        )
        
        if fit:
            X = self.vectorizer.fit_transform(processed_texts)
        else:
            X = self.vectorizer.transform(processed_texts)
        
        return X.toarray(), self.vectorizer
    
    def prepare_labels(self, intents: List[str], fit: bool = True) -> LabelEncoder:
        """Prepare and encode labels.
        
        Args:
            intents: List of intent labels
            fit: Whether to fit the label encoder or just transform
            
        Returns:
            Fitted LabelEncoder
        """
        self.label_encoder = LabelEncoder()
        
        if fit:
            y_encoded = self.label_encoder.fit_transform(intents)
        else:
            y_encoded = self.label_encoder.transform(intents)
        
        return y_encoded
    
    def train_single_model(self, model_name: str, X_train: np.ndarray, 
                          y_train: np.ndarray, X_val: np.ndarray,
                          y_val: np.ndarray) -> Dict:
        """Train a single model with cross-validation.
        
        Args:
            model_name: Name of the model to train
            X_train: Training features
            y_train: Training labels
            X_val: Validation features
            y_val: Validation labels
            
        Returns:
            Dictionary with model performance metrics
        """
        if model_name not in self.model_configs:
            raise ValueError(f"Unknown model: {model_name}")
        
        config = self.model_configs[model_name]
        model = config["model"]
        
        # Cross-validation on training data
        cv_scores = cross_val_score(
            model, X_train, y_train,
            cv=StratifiedKFold(n_splits=self.cv_folds, shuffle=True, random_state=self.random_state),
            scoring='f1'
        )
        
        # Train on full training set
        model.fit(X_train, y_train)
        
        # Validate on validation set
        y_pred = model.predict(X_val)
        val_accuracy = accuracy_score(y_val, y_pred)
        val_f1 = f1_score(y_val, y_pred, average='weighted')
        val_precision = precision_score(y_val, y_pred, average='weighted', zero_division=0)
        val_recall = recall_score(y_val, y_pred, average='weighted', zero_division=0)
        
        # Store model
        self.trained_models[model_name] = model
        
        # Calculate confidence scores for validation set
        if hasattr(model, 'predict_proba'):
            probas = model.predict_proba(X_val)
            confidence_scores = np.max(probas, axis=1)
        elif hasattr(model, 'decision_function'):
            decision_scores = model.decision_function(X_val)
            # Convert decision scores to confidence (0-1 range)
            if decision_scores.max() > decision_scores.min():
                confidence_scores = (decision_scores - decision_scores.min()) / (
                    decision_scores.max() - decision_scores.min() + 1e-8
                )
            else:
                confidence_scores = np.ones(len(decision_scores)) * 0.5
        else:
            confidence_scores = np.ones(len(y_val)) * 0.5
        
        performance = {
            'cv_f1_mean': np.mean(cv_scores),
            'cv_f1_std': np.std(cv_scores),
            'val_accuracy': val_accuracy,
            'val_f1': val_f1,
            'val_precision': val_precision,
            'val_recall': val_recall,
            'confidence_mean': np.mean(confidence_scores),
            'confidence_std': np.std(confidence_scores),
            'model_config': config
        }
        
        self.model_performance[model_name] = performance
        return performance
    
    def train_ensemble(self, X_train: np.ndarray, y_train: np.ndarray,
                      X_val: np.ndarray, y_val: np.ndarray) -> Dict:
        """Train an ensemble model using voting classifier.
        
        Args:
            X_train: Training features
            y_train: Training labels
            X_val: Validation features
            y_val: Validation labels
            
        Returns:
            Dictionary with ensemble model performance metrics
        """
        # Select best models for ensemble (usually RF and LR)
        ensemble_models = {
            name: self.trained_models[name]
            for name in ['random_forest', 'logistic_regression']
            if name in self.trained_models
        }
        
        if len(ensemble_models) < 2:
            print("Warning: Need at least 2 models for ensemble. Using single best model.")
            return self.model_performance.get('random_forest', {})
        
        # Create voting classifier
        estimators = [
            (name, model) for name, model in ensemble_models.items()
        ]
        
        ensemble = VotingClassifier(
            estimators=estimators,
            voting='soft',  # Use probability averaging
            n_jobs=-1
        )
        
        # Cross-validation on training data
        cv_scores = cross_val_score(
            ensemble, X_train, y_train,
            cv=StratifiedKFold(n_splits=self.cv_folds, shuffle=True, random_state=self.random_state),
            scoring='f1'
        )
        
        # Train ensemble
        ensemble.fit(X_train, y_train)
        self.trained_models['ensemble'] = ensemble
        
        # Validate on validation set
        y_pred = ensemble.predict(X_val)
        y_proba = ensemble.predict_proba(X_val) if hasattr(ensemble, 'predict_proba') else None
        
        val_accuracy = accuracy_score(y_val, y_pred)
        val_f1 = f1_score(y_val, y_pred, average='weighted')
        val_precision = precision_score(y_val, y_pred, average='weighted', zero_division=0)
        val_recall = recall_score(y_val, y_pred, average='weighted', zero_division=0)
        
        # Calculate confidence scores
        if y_proba is not None:
            confidence_scores = np.max(y_proba, axis=1)
        else:
            confidence_scores = np.ones(len(y_val)) * 0.5
        
        performance = {
            'cv_f1_mean': np.mean(cv_scores),
            'cv_f1_std': np.std(cv_scores),
            'val_accuracy': val_accuracy,
            'val_f1': val_f1,
            'val_precision': val_precision,
            'val_recall': val_recall,
            'confidence_mean': np.mean(confidence_scores),
            'confidence_std': np.std(confidence_scores),
            'model_config': {'type': 'ensemble'}
        }
        
        self.model_performance['ensemble'] = performance
        return performance
    
    def predict_intent(self, text: str, model_name: str = 'ensemble') -> Tuple[str, float]:
        """Predict intent for a single text.
        
        Args:
            text: Input text to classify
            model_name: Name of model to use for prediction
            
        Returns:
            Tuple of (predicted_intent, confidence_score)
        """
        if not self.is_trained:
            raise ValueError("Model not trained. Call train() method first.")
        
        if model_name not in self.trained_models:
            raise ValueError(f"Model not trained: {model_name}")
        
        if self.vectorizer is None or self.label_encoder is None:
            raise ValueError("Vectorizer or label encoder not initialized.")
        
        # Preprocess text
        processed_text = self.preprocess_text(text)
        
        # Transform features
        X = self.vectorizer.transform([processed_text])
        
        # Predict
        model = self.trained_models[model_name]
        
        if hasattr(model, 'predict_proba'):
            y_pred = model.predict(X)[0]
            probas = model.predict_proba(X)[0]
            confidence = np.max(probas)
        elif hasattr(model, 'decision_function'):
            y_pred = model.predict(X)[0]
            decision = model.decision_function(X)[0]
            confidence = (decision - decision.min()) / (decision.max() - decision.min() + 1e-8)
        else:
            y_pred = model.predict(X)[0]
            confidence = 0.5
        
        # Convert to original label
        intent = self.label_encoder.inverse_transform([y_pred])[0]
        
        return intent, float(confidence)
    
    def train(self, texts: List[str], intents: List[str],
              test_size: float = 0.2, use_ensemble: bool = True) -> Dict:
        """Train the intent classifier.
        
        Args:
            texts: List of text samples
            intents: List of intent labels
            test_size: Proportion of data for validation (default: 0.2)
            use_ensemble: Whether to create ensemble model (default: True)
            
        Returns:
            Dictionary with training and validation performance metrics
        """
        print("Preparing data...")
        
        # Create feature matrix
        X, self.vectorizer = self.create_feature_matrix(texts, fit=True)
        
        # Prepare labels
        y = self.prepare_labels(intents, fit=True)
        
        # Split data
        X_train, X_val, y_train, y_val = train_test_split(
            X, y, test_size=test_size, random_state=self.random_state,
            stratify=y
        )
        
        print(f"Training data: {X_train.shape[0]} samples")
        print(f"Validation data: {X_val.shape[0]} samples")
        print(f"Features: {X_train.shape[1]}")
        print(f"Classes: {len(np.unique(y))} - {self.label_encoder.classes_}")
        
        # Train individual models
        print("\nTraining individual models...")
        model_performance = {}
        
        for model_name in self.model_configs.keys():
            print(f"\n--- Training {model_name} ---")
            perf = self.train_single_model(model_name, X_train, y_train, X_val, y_val)
            model_performance[model_name] = perf
            print(f"  CV F1: {perf['cv_f1_mean']:.4f} ± {perf['cv_f1_std']:.4f}")
            print(f"  Val Accuracy: {perf['val_accuracy']:.4f}")
            print(f"  Val F1 Score: {perf['val_f1']:.4f}")
            print(f"  Avg Confidence: {perf['confidence_mean']:.4f}")
        
        # Train ensemble if requested
        if use_ensemble:
            print("\n--- Training ensemble model ---")
            ensemble_perf = self.train_ensemble(X_train, y_train, X_val, y_val)
            model_performance['ensemble'] = ensemble_perf
            print(f"  CV F1: {ensemble_perf['cv_f1_mean']:.4f} ± {ensemble_perf['cv_f1_std']:.4f}")
            print(f"  Val Accuracy: {ensemble_perf['val_accuracy']:.4f}")
            print(f"  Val F1 Score: {ensemble_perf['val_f1']:.4f}")
        
        # Select best model for deployment
        best_model_name = max(
            model_performance.keys(),
            key=lambda x: model_performance[x]['val_f1']
        )
        
        print(f"\nBest performing model: {best_model_name}")
        print(f"Performance: {model_performance[best_model_name]['val_f1']:.4f} F1 score")
        
        self.is_trained = True
        
        return {
            'model_performance': model_performance,
            'best_model': best_model_name,
            'vectorizer': self.vectorizer,
            'label_encoder': self.label_encoder,
            'X_train_shape': X_train.shape,
            'X_val_shape': X_val.shape
        }
    
    def save(self, model_path: str, vectorizer_path: str = None,
             label_encoder_path: str = None) -> None:
        """Save trained model to disk.
        
        Args:
            model_path: Path to save model
            vectorizer_path: Path to save vectorizer (optional)
            label_encoder_path: Path to save label encoder (optional)
        """
        if not self.is_trained:
            raise ValueError("Model not trained. Call train() method first.")
        
        # Save main model
        model_data = {
            'trained_models': self.trained_models,
            'model_performance': self.model_performance,
            'vectorizer': self.vectorizer,
            'label_encoder': self.label_encoder,
            'model_configs': self.model_configs,
            'ngram_range': self.ngram_range,
            'max_features': self.max_features,
            'cv_folds': self.cv_folds,
            'random_state': self.random_state
        }
        
        joblib.dump(model_data, model_path)
        
        # Save additional components if paths provided
        if vectorizer_path:
            joblib.dump(self.vectorizer, vectorizer_path)
        
        if label_encoder_path:
            joblib.dump(self.label_encoder, label_encoder_path)
        
        print(f"Model saved to: {model_path}")
    
    def load(self, model_path: str) -> 'EnhancedIntentClassifier':
        """Load trained model from disk.
        
        Args:
            model_path: Path to saved model
            
        Returns:
            Loaded EnhancedIntentClassifier instance
        """
        model_data = joblib.load(model_path)
        
        # Create new instance
        classifier = EnhancedIntentClassifier(
            ngram_range=model_data['ngram_range'],
            max_features=model_data['max_features'],
            cv_folds=model_data['cv_folds'],
            random_state=model_data['random_state']
        )
        
        # Restore attributes
        classifier.trained_models = model_data['trained_models']
        classifier.model_performance = model_data['model_performance']
        classifier.vectorizer = model_data['vectorizer']
        classifier.label_encoder = model_data['label_encoder']
        classifier.model_configs = model_data['model_configs']
        classifier.is_trained = True
        
        return classifier
    
    def get_feature_importance(self) -> Dict[str, np.ndarray]:
        """Get feature importance for models that support it.
        
        Returns:
            Dictionary with feature importance for each model
        """
        if not self.is_trained:
            raise ValueError("Model not trained. Call train() method first.")
        
        feature_importance = {}
        
        for model_name, model in self.trained_models.items():
            if hasattr(model, 'feature_importances_'):
                # Tree-based models (Random Forest, Decision Tree)
                feature_importance[model_name] = model.feature_importances_
            elif hasattr(model, 'coef_'):
                # Linear models (Logistic Regression)
                coef = model.coef_
                if coef.shape[0] == 1:
                    feature_importance[model_name] = np.abs(coef[0])
                else:
                    # Multi-class case
                    feature_importance[model_name] = np.mean(np.abs(coef), axis=0)
            else:
                # For models without feature importance, return None
                feature_importance[model_name] = None
        
        return feature_importance
    
    def print_model_summary(self) -> None:
        """Print a summary of the trained model."""
        if not self.is_trained:
            print("Model not trained yet.")
            return
        
        print("\n" + "="*60)
        print("ENHANCED INTENT CLASSIFIER SUMMARY")
        print("="*60)
        print(f"Number of classes: {len(self.label_encoder.classes_)}")
        print(f"Classes: {self.label_encoder.classes_}")
        print(f"Number of features: {self.vectorizer.vocabulary_.__len__()}")
        print(f"N-gram range: {self.ngram_range}")
        print(f"Max features: {self.max_features}")
        
        print("\nModel Performance:")
        for model_name, perf in self.model_performance.items():
            print(f"  {model_name.upper()}:")
            print(f"    CV F1: {perf['cv_f1_mean']:.4f} ± {perf['cv_f1_std']:.4f}")
            print(f"    Val Accuracy: {perf['val_accuracy']:.4f}")
            print(f"    Val F1 Score: {perf['val_f1']:.4f}")
            print(f"    Val Precision: {perf['val_precision']:.4f}")
            print(f"    Val Recall: {perf['val_recall']:.4f}")
            print(f"    Avg Confidence: {perf['confidence_mean']:.4f}")
        
        # Get best model
        best_model = max(
            self.model_performance.keys(),
            key=lambda x: self.model_performance[x]['val_f1']
        )
        
        print(f"\nRecommended model for deployment: {best_model.upper()}")
        print("="*60 + "\n")