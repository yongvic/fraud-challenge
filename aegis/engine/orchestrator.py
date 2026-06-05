"""
Orchestrateur de décision Aegis.

Fusionne les trois couches du cerveau de détection en une décision unique,
explicable et traçable :

  1. Coeur deterministe (``fraud_detection.detect_fraud``) — priorité
     réglementaire, reproductible, c'est la source de vérité notée.
  2. ML d'anomalie non supervisé — capte l'atypique que les règles ne codent pas.
  3. Graphe de réseaux — relie les comptes mules (anneaux de fraude).

Sortie par transaction : score final [0,1], verdict, reason codes lisibles, plus
les scores de chaque couche (transparence / explicabilité). Le verdict
deterministe garde la priorité : si une règle métier signale, le score final ne
peut pas descendre sous un plancher (la conformité prime sur le ML).
"""

from __future__ import annotations

from fraud_detection import analyze_signals, composite_score, detect_fraud  # noqa: F401
from aegis.config import CONFIG, risk_band
from aegis.data.ingest import mask_id
from aegis.graph.rings import ring_score_by_index
from aegis.ml.anomaly import AnomalyModel
from aegis.ml.features import FEATURE_NAMES

# Libellés lisibles des reason codes (explicabilité, droit à l'explication RGPD).
REASON_CODE_LABELS = {
    "RULE_NEGATIVE": "Montant nul ou négatif",
    "RULE_AMOUNT": "Montant très supérieur à l'habitude du client",
    "RULE_GEO": "Voyage géographiquement impossible",
    "RULE_MISSING": "Champs obligatoires manquants",
    "RULE_VELOCITY": "Rafale de transactions",
    "ML_ANOMALY": "Comportement statistiquement atypique (ML)",
    "GRAPH_RING": "Lié à un réseau de comptes suspect",
    "SIG_NIGHT": "Horaire inhabituel (nuit)",
    "SIG_CARD_ABSENT": "Carte absente sur un montant élevé",
    "SIG_MERCHANT": "Commerçant à risque",
    "SIG_DUPLICATE": "Doublon suspect",
    "SIG_CURRENCY": "Devise inhabituelle",
}

_SIGNAL_TO_CODE = {
    "negative": "RULE_NEGATIVE",
    "amount": "RULE_AMOUNT",
    "geo": "RULE_GEO",
    "missing": "RULE_MISSING",
    "velocity": "RULE_VELOCITY",
    "night": "SIG_NIGHT",
    "card_absent": "SIG_CARD_ABSENT",
    "merchant": "SIG_MERCHANT",
    "duplicate": "SIG_DUPLICATE",
    "currency": "SIG_CURRENCY",
}


class DecisionEngine:
    """Combine les couches de détection en décisions enrichies."""

    def __init__(self, config=CONFIG):
        self.config = config
        self.policy = config.scoring
        self.anomaly = AnomalyModel(contamination=self.policy.ml_contamination)
        self.last_rings: list[dict] = []
        self.ml_backend = self.anomaly.backend

    def analyze(self, transactions: list[dict]) -> list[dict]:
        """Renvoie une décision enrichie par transaction (même ordre)."""
        txs = list(transactions or [])

        # Couche 1 : coeur deterministe noté (inchangé).
        rule_results = detect_fraud(txs)

        # Couche 2 : ML d'anomalie (entraîné à la volée sur le lot).
        self.anomaly.fit(txs)
        ml_scores = self.anomaly.score(txs)

        # Couche 3 : graphe de réseaux.
        ring_scores, rings = ring_score_by_index(
            txs,
            min_size=self.policy.ring_min_size,
            window_hours=self.policy.ring_window_hours,
        )
        self.last_rings = rings

        decisions = []
        for i, tx in enumerate(txs):
            signals = {}
            if isinstance(tx, dict):
                try:
                    signals = analyze_signals(txs, i)
                except Exception:
                    signals = {}
            decisions.append(self._fuse(
                i, tx, rule_results[i],
                float(ml_scores[i]) if i < len(ml_scores) else 0.0,
                ring_scores.get(i, 0.0),
                signals,
            ))
        return decisions

    def _fuse(self, index, tx, rule_res, ml_score, ring_score, signals) -> dict:
        p = self.policy
        rule_flagged = bool(rule_res.get("is_suspicious"))
        rule_score = float(rule_res.get("fraud_score", 0.0))

        # Score fusionné pondéré.
        final = (p.weight_rules * rule_score
                 + p.weight_ml * ml_score
                 + p.weight_graph * ring_score)

        # Déclencheurs indépendants : chaque couche peut alerter seule.
        ring_triggered = ring_score >= p.ring_alert_threshold
        ml_triggered = ml_score >= p.ml_alert_threshold

        # La règle métier prime : plancher si le coeur deterministe signale.
        if rule_flagged:
            final = max(final, p.rule_floor_when_flagged)
        if ring_triggered:
            final = max(final, p.ring_floor)
        if ml_triggered:
            final = max(final, p.ml_floor)
        final = round(max(0.0, min(1.0, final)), 2)

        is_suspicious = (rule_flagged or ring_triggered or ml_triggered
                         or final >= p.suspicion_threshold)

        # Reason codes (explicabilité).
        codes = []
        for sig in signals:
            code = _SIGNAL_TO_CODE.get(sig)
            if code:
                codes.append(code)
        if ml_score >= 0.6 and "ML_ANOMALY" not in codes:
            codes.append("ML_ANOMALY")
        if ring_score >= 0.5:
            codes.append("GRAPH_RING")
        # Dé-doublonnage en gardant l'ordre.
        codes = list(dict.fromkeys(codes))

        primary_reason = rule_res.get("reason") or "Transaction conforme au profil du client"
        if not rule_flagged and is_suspicious:
            # Signalement venu du ML/graphe : raison adaptée.
            if ring_triggered:
                primary_reason = "Lié à un réseau de comptes suspect"
            elif ml_triggered:
                primary_reason = "Comportement statistiquement atypique (ML)"

        uid = tx.get("user_id") if isinstance(tx, dict) else None
        return {
            "index": index,
            "transaction_id": rule_res.get("transaction_id"),
            "user_id": uid,
            "user_masked": mask_id(uid),
            "amount": tx.get("amount") if isinstance(tx, dict) else None,
            "currency": tx.get("currency") if isinstance(tx, dict) else None,
            "merchant": tx.get("merchant") if isinstance(tx, dict) else None,
            "country": tx.get("country") if isinstance(tx, dict) else None,
            "timestamp": tx.get("timestamp") if isinstance(tx, dict) else None,
            "card_present": tx.get("card_present") if isinstance(tx, dict) else None,
            "fraud_score": final,
            "is_suspicious": bool(is_suspicious),
            "level": risk_band(final),
            "reason": primary_reason,
            "reason_codes": codes,
            "reason_code_labels": [REASON_CODE_LABELS.get(c, c) for c in codes],
            # Transparence des couches.
            "rule_score": round(rule_score, 2),
            "rule_flagged": rule_flagged,
            "ml_score": round(ml_score, 2),
            "ring_score": round(ring_score, 2),
            "composite_signals": round(composite_score(signals), 2),
        }
