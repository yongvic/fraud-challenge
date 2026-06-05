"""
Persistance des dossiers et piste d'audit (SQLite, stdlib — zéro dépendance).

Modélise le cycle de vie opérationnel réel d'une cellule anti-fraude :
chaque alerte devient un *dossier* qu'un analyste investigue et tranche. Chaque
action est journalisée dans une piste d'audit *append-only* (exigence de
conformité : qui a décidé quoi, quand et pourquoi).

La boucle de feedback (dispositions analystes) alimente les métriques de
qualité du modèle (precision, taux de faux positifs).
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

# Cycle de vie d'un dossier.
CASE_STATUSES = ["Nouveau", "En investigation", "Fraude confirmée", "Faux positif"]

# Dispositions terminales (utilisées pour la boucle de feedback / metriques).
TERMINAL_FRAUD = "Fraude confirmée"
TERMINAL_LEGIT = "Faux positif"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class CaseStore:
    """Accès SQLite aux dossiers, décisions et piste d'audit."""

    def __init__(self, db_path: Path | str):
        self.db_path = str(db_path)
        self._init_schema()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        return conn

    def _init_schema(self) -> None:
        with self._conn() as c:
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS cases (
                    transaction_id TEXT PRIMARY KEY,
                    user_id        TEXT,
                    amount         REAL,
                    currency       TEXT,
                    country        TEXT,
                    merchant       TEXT,
                    score          REAL,
                    level          TEXT,
                    reason         TEXT,
                    reason_codes   TEXT,
                    status         TEXT,
                    assignee       TEXT,
                    notes          TEXT,
                    created_at     TEXT,
                    updated_at     TEXT
                )
                """
            )
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_log (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts          TEXT,
                    actor       TEXT,
                    action      TEXT,
                    transaction_id TEXT,
                    detail      TEXT
                )
                """
            )

    # ── Audit (append-only) ────────────────────────────────────────────
    def log(self, actor: str, action: str, transaction_id: str | None = None,
            detail: str = "") -> None:
        with self._conn() as c:
            c.execute(
                "INSERT INTO audit_log (ts, actor, action, transaction_id, detail)"
                " VALUES (?, ?, ?, ?, ?)",
                (_now(), actor, action, transaction_id, detail),
            )

    def audit_trail(self, limit: int = 500) -> list[dict]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    # ── Dossiers ───────────────────────────────────────────────────────
    def upsert_case(self, decision: dict, actor: str = "system") -> None:
        """Crée le dossier d'une alerte s'il n'existe pas (idempotent)."""
        tid = decision.get("transaction_id")
        if not tid:
            return
        with self._conn() as c:
            existing = c.execute(
                "SELECT transaction_id FROM cases WHERE transaction_id = ?",
                (tid,),
            ).fetchone()
            if existing:
                return
            c.execute(
                """
                INSERT INTO cases (transaction_id, user_id, amount, currency,
                    country, merchant, score, level, reason, reason_codes,
                    status, assignee, notes, created_at, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    tid, decision.get("user_id"), decision.get("amount"),
                    decision.get("currency"), decision.get("country"),
                    decision.get("merchant"), decision.get("fraud_score"),
                    decision.get("level"), decision.get("reason"),
                    json.dumps(decision.get("reason_codes", []), ensure_ascii=False),
                    "Nouveau", None, "", _now(), _now(),
                ),
            )
        self.log(actor, "Dossier créé", tid,
                 f"score={decision.get('fraud_score')}")

    def sync_alerts(self, decisions: list[dict], actor: str = "system") -> int:
        """Crée des dossiers pour toutes les décisions suspectes. Renvoie le nb créé."""
        before = len(self.list_cases())
        for d in decisions:
            if d.get("is_suspicious"):
                self.upsert_case(d, actor=actor)
        return len(self.list_cases()) - before

    def list_cases(self, status: str | None = None) -> list[dict]:
        query = "SELECT * FROM cases"
        params: tuple = ()
        if status and status != "Tous":
            query += " WHERE status = ?"
            params = (status,)
        query += " ORDER BY score DESC"
        with self._conn() as c:
            rows = c.execute(query, params).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            try:
                d["reason_codes"] = json.loads(d.get("reason_codes") or "[]")
            except (json.JSONDecodeError, TypeError):
                d["reason_codes"] = []
            out.append(d)
        return out

    def get_case(self, transaction_id: str) -> dict | None:
        with self._conn() as c:
            r = c.execute(
                "SELECT * FROM cases WHERE transaction_id = ?",
                (transaction_id,),
            ).fetchone()
        return dict(r) if r else None

    def update_status(self, transaction_id: str, status: str,
                      actor: str, note: str = "") -> None:
        if status not in CASE_STATUSES:
            return
        with self._conn() as c:
            c.execute(
                "UPDATE cases SET status = ?, updated_at = ? WHERE transaction_id = ?",
                (status, _now(), transaction_id),
            )
            if note:
                c.execute(
                    "UPDATE cases SET notes = COALESCE(notes,'') || ? "
                    "WHERE transaction_id = ?",
                    (f"[{_now()}] {actor}: {note}\n", transaction_id),
                )
        self.log(actor, f"Statut -> {status}", transaction_id, note)

    def assign(self, transaction_id: str, assignee: str, actor: str) -> None:
        with self._conn() as c:
            c.execute(
                "UPDATE cases SET assignee = ?, updated_at = ? WHERE transaction_id = ?",
                (assignee, _now(), transaction_id),
            )
        self.log(actor, f"Assigné à {assignee}", transaction_id)

    # ── Boucle de feedback / métriques ─────────────────────────────────
    def feedback_metrics(self) -> dict:
        """Métriques de qualité issues des dispositions analystes."""
        cases = self.list_cases()
        resolved = [c for c in cases
                    if c["status"] in (TERMINAL_FRAUD, TERMINAL_LEGIT)]
        confirmed = sum(1 for c in resolved if c["status"] == TERMINAL_FRAUD)
        false_pos = sum(1 for c in resolved if c["status"] == TERMINAL_LEGIT)
        n = len(resolved)
        precision = (confirmed / n) if n else None
        fp_rate = (false_pos / n) if n else None
        return {
            "total_cases": len(cases),
            "resolved": n,
            "confirmed_fraud": confirmed,
            "false_positives": false_pos,
            "precision": precision,
            "false_positive_rate": fp_rate,
        }

    def reset(self) -> None:
        """Réinitialise le magasin (utile pour la démo)."""
        with self._conn() as c:
            c.execute("DELETE FROM cases")
            c.execute("DELETE FROM audit_log")
        self.log("system", "Réinitialisation du magasin")
