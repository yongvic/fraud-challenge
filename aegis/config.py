"""
Configuration centralisée d'Aegis.

Principe entreprise : aucun « nombre magique » dispersé dans le code. Tous les
seuils, poids et politiques de décision sont déclarés ici, versionnés, et
modifiables sans toucher à la logique. C'est la base d'une gouvernance de
politique de risque (policy management) auditable.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from pathlib import Path

# Racine du projet et stockage local (SQLite).
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
SAMPLE_CSV = DATA_DIR / "sample_transactions.csv"
DB_PATH = ROOT / ".aegis_store.db"

# Sel de hachage des identifiants (PII) pour l'affichage. En production il
# proviendrait d'un coffre de secrets (Vault/KMS), pas du code.
PII_SALT = "aegis-demo-salt-2026"

# Bandes de risque (score 0-1 -> niveau lisible).
RISK_BANDS = [
    (0.80, "Critique"),
    (0.50, "Élevé"),
    (0.0001, "Modéré"),
    (-1.0, "Sain"),
]

# Palette sémantique (réutilisée par l'UI ; usage fonctionnel, pas décoratif).
RISK_COLORS = {
    "Critique": "#fb7185",
    "Élevé": "#fbbf24",
    "Modéré": "#60a5fa",
    "Sain": "#34d399",
}


@dataclass
class ScoringPolicy:
    """Politique de scoring de l'orchestrateur (combinaison des couches)."""

    # Seuil de signalement final.
    suspicion_threshold: float = 0.50

    # Poids de fusion des trois couches du cerveau de détection.
    weight_rules: float = 0.60      # coeur deterministe (priorité réglementaire)
    weight_ml: float = 0.25         # anomalie non supervisée
    weight_graph: float = 0.15      # réseaux de fraude

    # Borne basse : si le coeur deterministe signale, le score final ne peut pas
    # descendre sous ce plancher (la règle métier prime sur le ML).
    rule_floor_when_flagged: float = 0.70

    # ML : contamination supposée (proportion d'anomalies attendue).
    ml_contamination: float = 0.12
    # Au-delà de ce score, le ML déclenche seul une alerte (anomalie forte).
    ml_alert_threshold: float = 0.85
    ml_floor: float = 0.60

    # Graphe : taille minimale d'un groupe pour parler de « réseau ».
    ring_min_size: int = 3
    # Fenêtre (heures) de rapprochement marchand+pays pour le graphe.
    ring_window_hours: float = 48.0
    # Au-delà de ce score réseau, le graphe déclenche seul une alerte.
    ring_alert_threshold: float = 0.70
    ring_floor: float = 0.78


@dataclass
class AppConfig:
    """Configuration applicative globale."""

    product_name: str = "Aegis"
    tagline: str = "Financial Crime Intelligence Platform"
    organization: str = "INTELO2026"
    base_currency: str = "EUR"

    # Hypothèse économique pour estimer les pertes évitées (démo Direction) :
    # part d'une alerte vraie qui se serait traduite en perte sèche.
    assumed_loss_recovery_rate: float = 0.85

    scoring: ScoringPolicy = field(default_factory=ScoringPolicy)

    def to_dict(self) -> dict:
        return asdict(self)


# Instance par défaut (importée partout). Modifiable à chaud depuis l'UI.
CONFIG = AppConfig()


def risk_band(score: float) -> str:
    """Convertit un score (0-1) en niveau de risque lisible."""
    try:
        s = float(score)
    except (TypeError, ValueError):
        return "Sain"
    for threshold, label in RISK_BANDS:
        if s >= threshold:
            return label
    return "Sain"
