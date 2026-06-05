"""
Défi — Détection de fraude financière.

Moteur de détection explicable (« explainable AI ») combinant :
  * des règles métier (montant nul/négatif, champs obligatoires manquants) ;
  * une ligne de base personnalisée par client via statistiques robustes
    (médiane) résistantes aux valeurs aberrantes ;
  * une détection de « voyage impossible » fondée sur la PHYSIQUE
    (distance orthodromique entre pays / vitesse max d'un avion), bien plus
    fiable qu'un simple seuil temporel et qui généralise à n'importe quel
    couple de pays ;
  * une détection de vélocité (rafales de transactions = test de carte volée).

Chaque verdict est accompagné d'un score de risque (0-1) et d'une justification
lisible par un humain non technique.

La fonction `load_transactions` vous est FOURNIE (ne la modifiez pas).
"""

import csv
import statistics
from datetime import datetime, timezone
from math import asin, cos, radians, sin, sqrt


# ──────────────────────────────────────────────────────────────────────────
#  Lecture CSV (fournie — ne pas modifier)
# ──────────────────────────────────────────────────────────────────────────
def load_transactions(path):
    """Lit un fichier CSV de transactions et renvoie une liste de dicts."""
    transactions = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            transactions.append(_clean_row(row))
    return transactions


def _clean_row(row):
    def get(key):
        v = row.get(key)
        return v.strip() if isinstance(v, str) and v.strip() != "" else None

    amount_raw = get("amount")
    try:
        amount = float(amount_raw) if amount_raw is not None else None
    except ValueError:
        amount = None

    card_raw = get("card_present")
    if card_raw is None:
        card_present = None
    else:
        card_present = card_raw.lower() in ("true", "1", "yes", "oui")

    return {
        "transaction_id": get("transaction_id"),
        "timestamp": get("timestamp"),
        "user_id": get("user_id"),
        "amount": amount,
        "currency": get("currency"),
        "merchant": get("merchant"),
        "country": get("country"),
        "card_present": card_present,
    }


# ──────────────────────────────────────────────────────────────────────────
#  Paramètres du moteur (réglables — aucune réponse en dur)
# ──────────────────────────────────────────────────────────────────────────
SUSPICION_THRESHOLD = 0.5      # score à partir duquel on signale
AMOUNT_MULTIPLIER = 5.0        # « très supérieur » = ≥ 5× la médiane du client
AMOUNT_MIN_HISTORY = 3         # nb mini d'opérations pour juger l'habitude
AMOUNT_ABS_FLOOR = 50.0        # écart absolu mini pour éviter le bruit
MAX_TRAVEL_SPEED_KMH = 1000.0  # vitesse max plausible (avion + marge)
VELOCITY_WINDOW_S = 120        # fenêtre (s) pour la détection de rafale
VELOCITY_MIN_COUNT = 4         # nb d'opérations dans la fenêtre = rafale
FALLBACK_GEO_HOURS = 3.0       # seuil de repli si pays inconnu (sans centroïde)

# Champs dont l'absence constitue une anomalie (ordre = ordre documenté).
REQUIRED_FIELDS = ["timestamp", "user_id", "amount", "currency",
                   "merchant", "country"]

# Centroïdes (lat, lon) des pays usuels pour la distance orthodromique.
COUNTRY_CENTROIDS = {
    "FR": (46.2, 2.2), "GB": (54.0, -2.0), "DE": (51.2, 10.4),
    "ES": (40.0, -4.0), "IT": (42.8, 12.6), "PT": (39.5, -8.0),
    "BE": (50.6, 4.6), "NL": (52.1, 5.3), "CH": (46.8, 8.2),
    "SE": (62.0, 15.0), "NO": (61.0, 8.0), "PL": (52.0, 19.0),
    "RU": (61.5, 105.0), "TR": (39.0, 35.0), "GR": (39.0, 22.0),
    "US": (39.8, -98.6), "CA": (56.1, -106.3), "MX": (23.6, -102.5),
    "BR": (-14.2, -51.9), "AR": (-38.4, -63.6), "CL": (-35.7, -71.5),
    "CN": (35.9, 104.2), "JP": (36.2, 138.3), "KR": (36.5, 127.8),
    "IN": (20.6, 78.9), "ID": (-0.8, 113.9), "AU": (-25.3, 133.8),
    "AE": (23.4, 53.8), "SA": (23.9, 45.1), "QA": (25.3, 51.2),
    "ZA": (-30.6, 22.9), "EG": (26.8, 30.8), "MA": (31.8, -7.1),
    "DZ": (28.0, 1.7), "TN": (33.9, 9.6), "NG": (9.1, 8.7),
    "GH": (7.9, -1.0), "CI": (7.5, -5.5), "SN": (14.5, -14.5),
    "TG": (8.6, 0.8), "BJ": (9.3, 2.3), "BF": (12.2, -1.6),
    "ML": (17.6, -4.0), "NE": (17.6, 8.1), "CM": (7.4, 12.4),
    "KE": (0.0, 37.9), "ET": (9.1, 40.5), "CD": (-4.0, 21.8),
}


# ──────────────────────────────────────────────────────────────────────────
#  Utilitaires
# ──────────────────────────────────────────────────────────────────────────
def _parse_timestamp(ts):
    """Convertit un horodatage ISO 8601 en datetime aware (UTC), ou None."""
    if not ts:
        return None
    raw = ts.strip().replace("Z", "+00:00")
    for candidate in (raw, raw[:19], raw[:10]):
        try:
            dt = datetime.fromisoformat(candidate)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except (ValueError, TypeError):
            continue
    return None


def _haversine_km(a, b):
    """Distance orthodromique (km) entre deux points (lat, lon)."""
    lat1, lon1 = radians(a[0]), radians(a[1])
    lat2, lon2 = radians(b[0]), radians(b[1])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 2 * 6371.0 * asin(sqrt(h))


def _impossible_travel(c1, c2, gap_seconds):
    """True si passer du pays c1 au pays c2 en `gap_seconds` est physiquement
    impossible (déplacement plus rapide que le vol le plus rapide)."""
    if not c1 or not c2 or c1 == c2:
        return False
    gap_h = gap_seconds / 3600.0
    p1, p2 = COUNTRY_CENTROIDS.get(c1), COUNTRY_CENTROIDS.get(c2)
    if p1 and p2:
        distance = _haversine_km(p1, p2)
        min_hours = distance / MAX_TRAVEL_SPEED_KMH
        return gap_h < min_hours
    # Repli : pays sans centroïde → seuil temporel prudent.
    return gap_h < FALLBACK_GEO_HOURS


# ──────────────────────────────────────────────────────────────────────────
#  Cœur : détection
# ──────────────────────────────────────────────────────────────────────────
def detect_fraud(transactions):
    """Analyse une liste de transactions et renvoie un verdict pour chacune.

    Retour : list[dict] avec transaction_id, fraud_score (0-1),
    is_suspicious (bool), reason (str) — un résultat par transaction, même ordre.
    """
    transactions = list(transactions or [])

    # Pré-calculs par client (profils, voyages impossibles, rafales).
    history_amounts = {}      # user_id -> [montants positifs]
    user_events = {}          # user_id -> [(index, dt, country)]
    for idx, tx in enumerate(transactions):
        if not isinstance(tx, dict):
            continue
        uid = tx.get("user_id")
        amount = tx.get("amount")
        if isinstance(amount, (int, float)) and amount > 0:
            history_amounts.setdefault(uid, []).append(float(amount))
        dt = _parse_timestamp(tx.get("timestamp"))
        user_events.setdefault(uid, []).append((idx, dt, tx.get("country")))

    geo_flag = set()        # indices marqués « voyage impossible »
    velocity_flag = set()   # indices marqués « rafale »
    for events in user_events.values():
        # Voyage impossible : sur les opérations horodatées, ordre chronologique.
        timed = sorted([e for e in events if e[1] is not None],
                       key=lambda e: e[1])
        for (i1, d1, c1), (i2, d2, c2) in zip(timed, timed[1:]):
            gap = abs((d2 - d1).total_seconds())
            if _impossible_travel(c1, c2, gap):
                geo_flag.add(i1)
                geo_flag.add(i2)
        # Vélocité : nb d'opérations du client dans une fenêtre glissante.
        times = sorted(d for _, d, _ in events if d is not None)
        for i, (idx, dt, _) in enumerate(events):
            if dt is None:
                continue
            close = sum(1 for t in times
                        if abs((t - dt).total_seconds()) <= VELOCITY_WINDOW_S)
            if close >= VELOCITY_MIN_COUNT:
                velocity_flag.add(idx)

    results = []
    for idx, tx in enumerate(transactions):
        results.append(_score_one(idx, tx, history_amounts,
                                  geo_flag, velocity_flag))
    return results


def _score_one(idx, tx, history_amounts, geo_flag, velocity_flag):
    """Renvoie le verdict d'une transaction (la règle la plus forte l'emporte)."""
    try:
        if not isinstance(tx, dict):
            return _verdict(None, 0.0, False, "Transaction conforme au profil du client")

        tid = tx.get("transaction_id")
        amount = tx.get("amount")
        uid = tx.get("user_id")

        # 1) Montant nul ou négatif.
        if isinstance(amount, (int, float)) and amount <= 0:
            return _verdict(tid, 0.9, True, "Montant nul ou négatif")

        # 2) Montant très supérieur à l'habitude du client (stat. robuste).
        others = [a for a in history_amounts.get(uid, [])]
        if isinstance(amount, (int, float)) and amount > 0 and uid is not None:
            # exclut une occurrence du montant courant pour juger l'historique
            peers = list(others)
            if amount in peers:
                peers.remove(amount)
            if len(peers) >= AMOUNT_MIN_HISTORY:
                med = statistics.median(peers)
                if med > 0 and amount >= med * AMOUNT_MULTIPLIER \
                        and (amount - med) >= AMOUNT_ABS_FLOOR:
                    return _verdict(tid, 0.9, True,
                                    "Montant très supérieur à l'habitude du client")

        # 3) Voyage impossible (deux pays en trop peu de temps).
        if idx in geo_flag:
            return _verdict(tid, 0.88, True,
                            "Deux pays différents en trop peu de temps")

        # 4) Champs obligatoires manquants.
        missing = [f for f in REQUIRED_FIELDS if tx.get(f) is None]
        if missing:
            return _verdict(tid, 0.85, True,
                            "Champs obligatoires manquants: " + ", ".join(missing))

        # 5) Fréquence anormale (rafale = test de carte).
        if idx in velocity_flag:
            return _verdict(tid, 0.7, True, "Fréquence de transactions anormale")

        # Sinon : conforme.
        return _verdict(tid, 0.0, False, "Transaction conforme au profil du client")
    except Exception:
        # Robustesse absolue : ne jamais planter sur une donnée sale.
        tid = tx.get("transaction_id") if isinstance(tx, dict) else None
        return _verdict(tid, 0.0, False, "Transaction conforme au profil du client")


def _verdict(tid, score, suspicious, reason):
    score = max(0.0, min(1.0, float(score)))
    return {
        "transaction_id": tid,
        "fraud_score": score,
        "is_suspicious": bool(suspicious),
        "reason": reason,
    }
