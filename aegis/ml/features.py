"""
Ingénierie des caractéristiques (feature engineering) pour la détection
d'anomalies.

On transforme chaque transaction en un vecteur numérique comparable, en la
replaçant dans le contexte du client (écart à sa médiane, rareté du pays,
vélocité). C'est ce contexte qui permet au modèle de distinguer une opération
réellement anormale d'une simple grosse dépense légitime.
"""

from __future__ import annotations

import statistics
from math import log1p

import numpy as np

from fraud_detection import _parse_timestamp

FEATURE_NAMES = [
    "log_amount",          # ordre de grandeur du montant
    "amount_ratio",        # montant / médiane du client
    "hour_sin",            # heure (encodage cyclique)
    "hour_cos",
    "card_absent",         # carte non présente
    "country_rarity",      # rareté du pays pour ce client
    "user_velocity",       # nb d'opérations du client (intensité)
    "currency_novelty",    # devise jamais vue chez ce client
]


def _profiles(transactions):
    medians, countries, currencies, counts = {}, {}, {}, {}
    for tx in transactions:
        if not isinstance(tx, dict):
            continue
        uid = tx.get("user_id")
        counts[uid] = counts.get(uid, 0) + 1
        amt = tx.get("amount")
        if isinstance(amt, (int, float)) and amt > 0:
            medians.setdefault(uid, []).append(float(amt))
        c = tx.get("country")
        if c:
            countries.setdefault(uid, {})
            countries[uid][c] = countries[uid].get(c, 0) + 1
        cur = tx.get("currency")
        if cur:
            currencies.setdefault(uid, set()).add(cur)
    median_amount = {u: statistics.median(v) for u, v in medians.items() if v}
    return median_amount, countries, currencies, counts


def _row(tx, median_amount, countries, currencies, counts):
    uid = tx.get("user_id")
    amt = tx.get("amount")
    amt = float(amt) if isinstance(amt, (int, float)) else 0.0

    med = median_amount.get(uid, 0.0)
    log_amount = log1p(abs(amt))
    amount_ratio = (amt / med) if med > 0 else (1.0 if amt <= 0 else 5.0)

    dt = _parse_timestamp(tx.get("timestamp"))
    hour = dt.hour if dt else 12
    hour_sin = np.sin(2 * np.pi * hour / 24)
    hour_cos = np.cos(2 * np.pi * hour / 24)

    card_absent = 1.0 if tx.get("card_present") is False else 0.0

    cmap = countries.get(uid, {})
    total_c = sum(cmap.values()) or 1
    c = tx.get("country")
    country_rarity = 1.0 - (cmap.get(c, 0) / total_c) if c else 1.0

    user_velocity = log1p(counts.get(uid, 1))

    known_cur = currencies.get(uid, set())
    cur = tx.get("currency")
    currency_novelty = 1.0 if (cur and cur not in known_cur and len(known_cur) >= 1) else 0.0

    return [log_amount, amount_ratio, hour_sin, hour_cos, card_absent,
            country_rarity, user_velocity, currency_novelty]


def build_feature_matrix(transactions) -> np.ndarray:
    """Construit la matrice de features (n_transactions x n_features)."""
    txs = [t for t in (transactions or []) if isinstance(t, dict)]
    if not txs:
        return np.zeros((0, len(FEATURE_NAMES)))
    median_amount, countries, currencies, counts = _profiles(txs)
    rows = [_row(tx, median_amount, countries, currencies, counts) for tx in txs]
    matrix = np.array(rows, dtype=float)
    matrix = np.nan_to_num(matrix, nan=0.0, posinf=0.0, neginf=0.0)
    return matrix
