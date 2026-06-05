"""
Abstraction d'ingestion des transactions.

- Lecture CSV (réutilise ``load_transactions`` du moteur noté, sans le modifier).
- Simulation d'un flux temps réel (batches chronologiques) pour la supervision.
- Masquage des identifiants (PII) pour l'affichage et les exports (RGPD :
  minimisation des données, pseudonymisation).
- Rapport de qualité des données (champs manquants, doublons, anomalies de
  format) — un vrai pipeline mesure la qualité avant de décider.
"""

from __future__ import annotations

import hashlib

from fraud_detection import _parse_timestamp, load_transactions
from aegis.config import PII_SALT


def load_from_csv(path: str) -> list[dict]:
    """Charge des transactions depuis un CSV via le loader noté (inchangé)."""
    return load_transactions(path)


def mask_id(value: str | None, keep: int = 2) -> str:
    """Pseudonymise un identifiant : préfixe lisible + hash court stable.

    Exemple : ``U1`` -> ``U1·a3f9``. Permet de relier les opérations d'un même
    client sans exposer l'identifiant brut.
    """
    if not value:
        return "—"
    digest = hashlib.sha256((PII_SALT + str(value)).encode("utf-8")).hexdigest()
    return f"{str(value)[:keep]}·{digest[:4]}"


def stream_batches(transactions: list[dict], batch_size: int = 1):
    """Génère des lots chronologiques pour simuler un flux temps réel.

    Les transactions sont triées par horodatage (les non datées en fin), puis
    émises par paquets de ``batch_size``. Permet de « rejouer » la journée.
    """
    def _key(tx):
        dt = _parse_timestamp(tx.get("timestamp")) if isinstance(tx, dict) else None
        # Les non datées passent en dernier (timestamp max).
        return (dt is None, dt)

    ordered = sorted(
        [t for t in (transactions or []) if isinstance(t, dict)],
        key=_key,
    )
    for i in range(0, len(ordered), max(1, batch_size)):
        yield ordered[: i + batch_size]


def data_quality_report(transactions: list[dict]) -> dict:
    """Mesure la qualité du lot avant analyse (observabilité des données)."""
    txs = [t for t in (transactions or []) if isinstance(t, dict)]
    total = len(txs)
    if total == 0:
        return {"total": 0, "completeness": 1.0, "issues": []}

    fields = ["timestamp", "user_id", "amount", "currency", "merchant",
              "country", "card_present"]
    missing_counts = {f: 0 for f in fields}
    bad_amount = 0
    bad_timestamp = 0
    seen_ids = set()
    duplicate_ids = 0

    for tx in txs:
        for f in fields:
            if tx.get(f) is None:
                missing_counts[f] += 1
        amt = tx.get("amount")
        if amt is None or (isinstance(amt, (int, float)) and amt <= 0):
            bad_amount += 1
        if tx.get("timestamp") and _parse_timestamp(tx.get("timestamp")) is None:
            bad_timestamp += 1
        tid = tx.get("transaction_id")
        if tid in seen_ids:
            duplicate_ids += 1
        seen_ids.add(tid)

    filled = sum(1 for tx in txs for f in fields if tx.get(f) is not None)
    completeness = filled / (total * len(fields))

    issues = []
    for f, n in missing_counts.items():
        if n:
            issues.append({"type": "Champ manquant", "field": f, "count": n})
    if bad_amount:
        issues.append({"type": "Montant nul/négatif/absent", "field": "amount",
                       "count": bad_amount})
    if bad_timestamp:
        issues.append({"type": "Horodatage illisible", "field": "timestamp",
                       "count": bad_timestamp})
    if duplicate_ids:
        issues.append({"type": "Identifiant dupliqué", "field": "transaction_id",
                       "count": duplicate_ids})

    return {
        "total": total,
        "completeness": round(completeness, 3),
        "missing": missing_counts,
        "issues": issues,
    }
