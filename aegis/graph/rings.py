"""
Détection de réseaux de fraude par graphe (Python pur, union-find).

Les fraudeurs opèrent rarement seuls : plusieurs comptes « mules » partagent un
même marchand de cashout, un même pays et une fenêtre temporelle resserrée. On
relie ces transactions et on cherche les *composantes connexes* (les anneaux).

On utilise une structure union-find (Disjoint Set Union) : O(n) en pratique,
zéro dépendance externe. Plus crédible et plus robuste qu'un import de networkx
pour ce besoin précis.
"""

from __future__ import annotations

from fraud_detection import _parse_timestamp


class _UnionFind:
    def __init__(self, n: int):
        self.parent = list(range(n))
        self.rank = [0] * n

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        if self.rank[ra] < self.rank[rb]:
            ra, rb = rb, ra
        self.parent[rb] = ra
        if self.rank[ra] == self.rank[rb]:
            self.rank[ra] += 1


def detect_rings(transactions, min_size: int = 3, window_hours: float = 48.0):
    """Détecte les réseaux de comptes liés.

    Deux transactions sont liées si elles partagent le même (marchand, pays),
    impliquent des clients différents, et tombent dans une fenêtre temporelle
    commune. Un réseau = un groupe d'au moins ``min_size`` clients distincts.

    Renvoie une liste de dicts : {members, transactions, merchant, country, size}.
    """
    txs = [t for t in (transactions or []) if isinstance(t, dict)]
    n = len(txs)
    if n == 0:
        return []

    uf = _UnionFind(n)
    # Regroupe les indices par clé (marchand, pays).
    buckets: dict[tuple, list[int]] = {}
    for i, tx in enumerate(txs):
        merchant = tx.get("merchant")
        country = tx.get("country")
        if not merchant or not country:
            continue
        buckets.setdefault((merchant, country), []).append(i)

    window_s = window_hours * 3600.0
    for key, idxs in buckets.items():
        for a in range(len(idxs)):
            for b in range(a + 1, len(idxs)):
                i, j = idxs[a], idxs[b]
                # Clients différents (sinon ce n'est pas un réseau).
                if txs[i].get("user_id") == txs[j].get("user_id"):
                    continue
                di = _parse_timestamp(txs[i].get("timestamp"))
                dj = _parse_timestamp(txs[j].get("timestamp"))
                if di and dj and abs((di - dj).total_seconds()) > window_s:
                    continue
                uf.union(i, j)

    # Regroupe par composante.
    comps: dict[int, list[int]] = {}
    for i in range(n):
        comps.setdefault(uf.find(i), []).append(i)

    rings = []
    for members in comps.values():
        users = {txs[i].get("user_id") for i in members}
        if len(users) >= min_size:
            sample = txs[members[0]]
            rings.append({
                "members": sorted(u for u in users if u),
                "transactions": [txs[i].get("transaction_id") for i in members],
                "indices": members,
                "merchant": sample.get("merchant"),
                "country": sample.get("country"),
                "size": len(users),
            })
    rings.sort(key=lambda r: r["size"], reverse=True)
    return rings


def ring_score_by_index(transactions, min_size: int = 3, window_hours: float = 48.0):
    """Mappe chaque index de transaction -> score de risque réseau [0,1]."""
    rings = detect_rings(transactions, min_size=min_size, window_hours=window_hours)
    scores: dict[int, float] = {}
    for ring in rings:
        # Plus le réseau est grand, plus le risque est élevé (saturé à 0.9).
        s = min(0.9, 0.5 + 0.1 * ring["size"])
        for idx in ring["indices"]:
            scores[idx] = max(scores.get(idx, 0.0), s)
    return scores, rings
