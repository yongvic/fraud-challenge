"""Couche d'apprentissage automatique (détection d'anomalies non supervisée)."""

from aegis.ml.features import build_feature_matrix, FEATURE_NAMES
from aegis.ml.anomaly import AnomalyModel

__all__ = ["AnomalyModel", "build_feature_matrix", "FEATURE_NAMES"]
