"""
Modèle de détection d'anomalies non supervisé.

Le modèle apprend « la normalité » d'un lot de transactions, sans étiquettes,
puis attribue à chacune un score d'anomalie (0 = normal, 1 = très atypique).

Conception résiliente (exigence : ne jamais planter) :
- si ``scikit-learn`` est disponible -> IsolationForest (standard industriel) ;
- sinon -> repli en numpy pur (distance de Mahalanobis robuste), qui donne un
  score d'anomalie crédible sans aucune dépendance lourde.

Le modèle est entraîné à la volée sur le lot courant : pas d'état caché, donc
totalement reproductible et auditable.
"""

from __future__ import annotations

import numpy as np

from aegis.ml.features import FEATURE_NAMES, build_feature_matrix

try:  # dépendance optionnelle
    from sklearn.ensemble import IsolationForest  # type: ignore
    _HAS_SKLEARN = True
except Exception:  # pragma: no cover - dépend de l'environnement
    _HAS_SKLEARN = False


def _sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-x))


def _chi2_survival(d2: np.ndarray, k: int) -> np.ndarray:
    """P(chi2_k > d2) approx. via Wilson-Hilferty (numpy pur, sans scipy).

    Sous l'hypothèse de normalité, le carré de la distance de Mahalanobis suit
    une loi du chi-2 à k degrés de liberté. Le score d'anomalie est alors
    1 - survie : un point typique obtient un score bas, un point extrême un
    score proche de 1.
    """
    if k <= 0:
        return np.zeros_like(d2)
    # Transformation de Wilson-Hilferty vers une loi normale standard.
    term = np.cbrt(np.maximum(d2, 1e-12) / k)
    mean = 1.0 - 2.0 / (9.0 * k)
    std = np.sqrt(2.0 / (9.0 * k))
    z = (term - mean) / std
    # CDF normale standard via erf.
    from math import erf
    cdf = np.array([0.5 * (1.0 + erf(v / np.sqrt(2.0))) for v in z])
    return np.clip(cdf, 0.0, 1.0)


class AnomalyModel:
    """Encapsule l'entraînement et le scoring d'anomalie."""

    def __init__(self, contamination: float = 0.12, random_state: int = 42):
        self.contamination = contamination
        self.random_state = random_state
        self.backend = "isolation_forest" if _HAS_SKLEARN else "mahalanobis_numpy"
        self._model = None
        self._mean = None
        self._inv_cov = None
        self._fitted = False

    def fit(self, transactions) -> "AnomalyModel":
        X = build_feature_matrix(transactions)
        if X.shape[0] < 4:
            # Trop peu de données pour apprendre une normalité fiable.
            self._fitted = False
            return self
        if _HAS_SKLEARN:
            self._model = IsolationForest(
                contamination=min(0.5, max(0.01, self.contamination)),
                random_state=self.random_state,
                n_estimators=200,
            )
            self._model.fit(X)
        else:
            self._mean = X.mean(axis=0)
            cov = np.cov(X, rowvar=False)
            cov += np.eye(cov.shape[0]) * 1e-6  # régularisation
            try:
                self._inv_cov = np.linalg.inv(cov)
            except np.linalg.LinAlgError:
                self._inv_cov = np.linalg.pinv(cov)
        self._fitted = True
        return self

    def score(self, transactions) -> np.ndarray:
        """Renvoie un score d'anomalie [0,1] par transaction."""
        X = build_feature_matrix(transactions)
        if not self._fitted or X.shape[0] == 0:
            return np.zeros(X.shape[0])
        if _HAS_SKLEARN and self._model is not None:
            # decision_function : positif = normal, négatif = anormal.
            # Sigmoïde -> un point normal obtient un score bas (< 0.5).
            decision = self._model.decision_function(X)
            return _sigmoid(-decision * 4.0)
        # Repli Mahalanobis : distance^2 -> probabilité d'anomalie (chi-2).
        diff = X - self._mean
        d2 = np.einsum("ij,jk,ik->i", diff, self._inv_cov, diff)
        k = X.shape[1]
        return _chi2_survival(d2, k)

    def top_features(self, transactions, index: int, k: int = 3) -> list[str]:
        """Caractéristiques les plus atypiques d'une transaction (explicabilité)."""
        X = build_feature_matrix(transactions)
        if X.shape[0] == 0 or index >= X.shape[0]:
            return []
        mean = X.mean(axis=0)
        std = X.std(axis=0) + 1e-9
        z = np.abs((X[index] - mean) / std)
        order = np.argsort(z)[::-1][:k]
        return [FEATURE_NAMES[i] for i in order if z[i] > 1.0]
