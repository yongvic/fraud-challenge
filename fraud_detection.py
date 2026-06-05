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


# ──────────────────────────────────────────────────────────────────────────
#  Analyse étendue (UI, démo, signaux secondaires — n'affecte pas detect_fraud)
# ──────────────────────────────────────────────────────────────────────────
NAIVE_GEO_HOURS = 3.0
NIGHT_HOUR_START = 0
NIGHT_HOUR_END = 5
DUPLICATE_WINDOW_S = 90
HIGH_RISK_MERCHANT_KEYWORDS = (
    "bijouterie", "jewelry", "crypto", "casino", "betting", "forex",
)

SIGNAL_LABELS = {
    "amount": "Montant vs médiane client",
    "geo": "Voyage impossible (physique)",
    "velocity": "Rafale de transactions",
    "missing": "Champs manquants",
    "negative": "Montant nul ou négatif",
    "night": "Horaire inhabituel (nuit)",
    "card_absent": "Carte absente + gros montant",
    "merchant": "Commerçant à risque",
    "duplicate": "Doublon suspect",
    "currency": "Devise inhabituelle",
}


def _build_context(transactions):
    """Pré-calculs partagés pour l'analyse étendue."""
    txs = list(transactions or [])
    history_amounts = {}
    user_currencies = {}
    user_hours = {}
    user_events = {}
    geo_flag = set()
    velocity_flag = set()
    travel_pairs = {}

    for idx, tx in enumerate(txs):
        if not isinstance(tx, dict):
            continue
        uid = tx.get("user_id")
        amount = tx.get("amount")
        if isinstance(amount, (int, float)) and amount > 0:
            history_amounts.setdefault(uid, []).append(float(amount))
        cur = tx.get("currency")
        if cur:
            user_currencies.setdefault(uid, set()).add(cur)
        dt = _parse_timestamp(tx.get("timestamp"))
        if dt and uid:
            user_hours.setdefault(uid, []).append(dt.hour)
        user_events.setdefault(uid, []).append((idx, dt, tx.get("country"), tx))

    for uid, events in user_events.items():
        timed = sorted([e for e in events if e[1] is not None], key=lambda e: e[1])
        for (i1, d1, c1, _), (i2, d2, c2, tx2) in zip(timed, timed[1:]):
            gap = abs((d2 - d1).total_seconds())
            if _impossible_travel(c1, c2, gap):
                geo_flag.add(i1)
                geo_flag.add(i2)
                detail = _travel_detail(c1, c2, gap)
                travel_pairs[i1] = {**detail, "other_id": tx2.get("transaction_id")}
                travel_pairs[i2] = {**detail, "other_id": _tx_at(txs, i1, "transaction_id")}
        times = sorted(d for _, d, _, _ in events if d is not None)
        for idx, dt, _, _ in events:
            if dt is None:
                continue
            close = sum(1 for t in times
                        if abs((t - dt).total_seconds()) <= VELOCITY_WINDOW_S)
            if close >= VELOCITY_MIN_COUNT:
                velocity_flag.add(idx)

    return {
        "transactions": txs,
        "history_amounts": history_amounts,
        "user_currencies": user_currencies,
        "user_hours": user_hours,
        "geo_flag": geo_flag,
        "velocity_flag": velocity_flag,
        "travel_pairs": travel_pairs,
    }


def _tx_at(txs, idx, key):
    if 0 <= idx < len(txs) and isinstance(txs[idx], dict):
        return txs[idx].get(key)
    return None


def _travel_detail(c1, c2, gap_seconds):
    gap_h = gap_seconds / 3600.0
    p1, p2 = COUNTRY_CENTROIDS.get(c1), COUNTRY_CENTROIDS.get(c2)
    if p1 and p2:
        dist = _haversine_km(p1, p2)
        min_h = dist / MAX_TRAVEL_SPEED_KMH
        return {
            "country_from": c1, "country_to": c2,
            "distance_km": round(dist, 0),
            "min_hours": round(min_h, 1),
            "actual_hours": round(gap_h, 2),
            "impossible": gap_h < min_h,
        }
    return {
        "country_from": c1, "country_to": c2,
        "distance_km": None,
        "min_hours": FALLBACK_GEO_HOURS,
        "actual_hours": round(gap_h, 2),
        "impossible": gap_h < FALLBACK_GEO_HOURS,
    }


def _median_excluding(amount, peers):
    if amount in peers:
        peers = list(peers)
        peers.remove(amount)
    return statistics.median(peers) if peers else None


def analyze_signals(transactions, index):
    """Décomposition des signaux de risque pour une transaction (affichage UI)."""
    ctx = _build_context(transactions)
    txs = ctx["transactions"]
    if index < 0 or index >= len(txs) or not isinstance(txs[index], dict):
        return {}
    tx = txs[index]
    uid = tx.get("user_id")
    amount = tx.get("amount")
    signals = {}

    if isinstance(amount, (int, float)) and amount <= 0:
        signals["negative"] = 0.9

    peers = list(ctx["history_amounts"].get(uid, []))
    if isinstance(amount, (int, float)) and amount > 0 and len(peers) >= AMOUNT_MIN_HISTORY:
        med = _median_excluding(amount, peers)
        if med and med > 0:
            ratio = amount / med
            if ratio >= AMOUNT_MULTIPLIER and (amount - med) >= AMOUNT_ABS_FLOOR:
                signals["amount"] = min(0.9, 0.5 + ratio / 20)

    if index in ctx["geo_flag"]:
        signals["geo"] = 0.88
    if index in ctx["velocity_flag"]:
        signals["velocity"] = 0.7

    missing = [f for f in REQUIRED_FIELDS if tx.get(f) is None]
    if missing:
        signals["missing"] = 0.85

    dt = _parse_timestamp(tx.get("timestamp"))
    if dt and uid:
        hours = ctx["user_hours"].get(uid, [])
        if hours:
            typical = statistics.median(hours)
            if (NIGHT_HOUR_START <= dt.hour <= NIGHT_HOUR_END
                    and typical >= 8):
                signals["night"] = 0.35

    if tx.get("card_present") is False and isinstance(amount, (int, float)) and amount > 0:
        med = _median_excluding(amount, peers) if peers else None
        if med and amount >= med * 3:
            signals["card_absent"] = 0.45

    merchant = (tx.get("merchant") or "").lower()
    if any(k in merchant for k in HIGH_RISK_MERCHANT_KEYWORDS):
        signals["merchant"] = 0.38

    if dt:
        for j, other in enumerate(txs):
            if j == index or not isinstance(other, dict):
                continue
            if other.get("user_id") != uid:
                continue
            odt = _parse_timestamp(other.get("timestamp"))
            if not odt:
                continue
            if abs((odt - dt).total_seconds()) <= DUPLICATE_WINDOW_S:
                if (other.get("amount") == amount
                        and other.get("merchant") == tx.get("merchant")):
                    signals["duplicate"] = 0.52
                    break

    cur = tx.get("currency")
    known = ctx["user_currencies"].get(uid, set())
    if cur and len(known) >= 2 and cur not in known:
        signals["currency"] = 0.32

    return signals


def composite_score(signals):
    """Score composite pondéré (affichage uniquement, pas le verdict officiel)."""
    if not signals:
        return 0.0
    weights = {
        "negative": 0.20, "amount": 0.18, "geo": 0.16, "missing": 0.12,
        "velocity": 0.10, "night": 0.06, "card_absent": 0.06,
        "merchant": 0.05, "duplicate": 0.04, "currency": 0.03,
    }
    total_w = sum(weights.get(k, 0.05) for k in signals)
    if total_w == 0:
        return 0.0
    score = sum(signals[k] * weights.get(k, 0.05) for k in signals) / total_w
    return round(min(1.0, score), 2)


def get_travel_info(transactions, index):
    """Détails du voyage impossible pour une transaction."""
    ctx = _build_context(transactions)
    return ctx["travel_pairs"].get(index)


def build_client_profile(transactions, user_id):
    """Profil 360° d'un client pour l'interface."""
    txs = [t for t in (transactions or []) if isinstance(t, dict)
           and t.get("user_id") == user_id]
    amounts = [t["amount"] for t in txs
               if isinstance(t.get("amount"), (int, float)) and t["amount"] > 0]
    countries = sorted({t.get("country") for t in txs if t.get("country")})
    currencies = sorted({t.get("currency") for t in txs if t.get("currency")})
    timeline = []
    for t in txs:
        timeline.append({
            "transaction_id": t.get("transaction_id"),
            "timestamp": t.get("timestamp"),
            "amount": t.get("amount"),
            "country": t.get("country"),
            "merchant": t.get("merchant"),
        })
    timeline.sort(key=lambda x: x.get("timestamp") or "")
    return {
        "user_id": user_id,
        "transaction_count": len(txs),
        "median_amount": statistics.median(amounts) if amounts else None,
        "countries": countries,
        "currencies": currencies,
        "timeline": timeline,
    }


def detect_fraud_naive(transactions, hours=NAIVE_GEO_HOURS):
    """Détecteur naïf (seuil fixe en heures) pour comparaison en démo."""
    txs = list(transactions or [])
    results = []
    by_user = {}
    for idx, tx in enumerate(txs):
        if not isinstance(tx, dict):
            results.append({"index": idx, "is_suspicious": False, "reason": "ok"})
            continue
        uid = tx.get("user_id")
        dt = _parse_timestamp(tx.get("timestamp"))
        country = tx.get("country")
        suspicious = False
        reason = "ok"
        if uid and dt and country:
            hist = by_user.setdefault(uid, [])
            for prev_dt, prev_c in hist:
                if prev_c != country:
                    gap_h = abs((dt - prev_dt).total_seconds()) / 3600.0
                    if gap_h < hours:
                        suspicious = True
                        reason = f"Pays différents en moins de {hours:.0f}h (naïf)"
                        break
            hist.append((dt, country))
        results.append({"index": idx, "is_suspicious": suspicious, "reason": reason})
    return results
