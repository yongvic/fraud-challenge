"""
Notification client et jeton de contestation.

Posture : tant qu'un humain n'a pas confirmé la fraude, le message reste une
*alerte de vigilance*, pas une accusation. On informe, on donne un montant
reconnaissable, l'action prise, et surtout un canal officiel de contestation
(droit de réponse). Aucun détail technique (scores, reason codes, autres
clients) n'est exposé au client.
"""

from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime, timedelta, timezone

from aegis.config import CONFIG, PII_SALT
from aegis.data.ingest import mask_id

TOKEN_TTL_HOURS = 72


def contestation_token(transaction_id: str, user_id: str | None) -> str:
    """Jeton signé à usage unique pour le portail de contestation.

    Format : base64(payload).signature_courte. La signature lie le jeton au
    secret serveur (ici un sel de démo ; en production un HMAC + KMS).
    """
    expires = (datetime.now(timezone.utc) + timedelta(hours=TOKEN_TTL_HOURS))
    payload = {
        "tid": transaction_id,
        "uid": user_id,
        "exp": expires.isoformat(timespec="seconds"),
    }
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    body = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
    sig = hashlib.sha256((PII_SALT + body).encode("utf-8")).hexdigest()[:10]
    return f"{body}.{sig}"


def decode_token(token: str) -> dict | None:
    """Vérifie la signature et l'expiration d'un jeton. None si invalide."""
    try:
        body, sig = token.split(".", 1)
    except ValueError:
        return None
    expected = hashlib.sha256((PII_SALT + body).encode("utf-8")).hexdigest()[:10]
    if sig != expected:
        return None
    try:
        pad = "=" * (-len(body) % 4)
        payload = json.loads(base64.urlsafe_b64decode(body + pad))
    except (ValueError, json.JSONDecodeError):
        return None
    try:
        exp = datetime.fromisoformat(payload["exp"])
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
    except (KeyError, ValueError):
        return None
    payload["expired"] = datetime.now(timezone.utc) > exp
    return payload


def _fmt_amount(amount, currency) -> str:
    if not isinstance(amount, (int, float)):
        return "une opération récente"
    txt = f"{amount:,.2f}".replace(",", " ").replace(".", ",")
    return f"{txt} {currency or CONFIG.base_currency}".strip()


def build_client_email(decision: dict, portal_base: str = "https://aegis.exemple/contestation") -> dict:
    """Construit la notification client (texte + HTML + jeton)."""
    tid = decision.get("transaction_id")
    token = contestation_token(tid, decision.get("user_id"))
    link = f"{portal_base}?t={token}"
    amount = _fmt_amount(decision.get("amount"), decision.get("currency"))
    merchant = decision.get("merchant") or "un commerçant"
    when = decision.get("timestamp") or "récemment"
    masked = mask_id(decision.get("user_id"))

    subject = "Vérification de sécurité sur votre compte"

    body_text = (
        f"Bonjour,\n\n"
        f"Notre dispositif de sécurité a détecté une opération inhabituelle sur "
        f"votre compte (référence {masked}) :\n\n"
        f"  • Montant : {amount}\n"
        f"  • Commerçant : {merchant}\n"
        f"  • Date : {when}\n\n"
        f"Par précaution, cette opération fait l'objet d'une vérification. "
        f"Si vous êtes bien à l'origine de cette opération, aucune action n'est "
        f"nécessaire. Dans le cas contraire, ou si vous souhaitez apporter des "
        f"précisions, vous disposez d'un droit de réponse :\n\n"
        f"  {link}\n\n"
        f"Ce lien sécurisé expire dans {TOKEN_TTL_HOURS} heures. Pour votre "
        f"sécurité, nous ne vous demanderons jamais votre code confidentiel.\n\n"
        f"L'équipe Sécurité {CONFIG.product_name}"
    )

    body_html = (
        f"<p>Bonjour,</p>"
        f"<p>Notre dispositif de sécurité a détecté une opération inhabituelle "
        f"sur votre compte (référence <b>{masked}</b>) :</p>"
        f"<p style='margin:10px 0'>"
        f"<b>Montant</b> : {amount}<br>"
        f"<b>Commerçant</b> : {merchant}<br>"
        f"<b>Date</b> : {when}</p>"
        f"<p>Par précaution, cette opération fait l'objet d'une vérification. "
        f"Si vous en êtes bien à l'origine, aucune action n'est nécessaire. "
        f"Sinon, vous disposez d'un droit de réponse :</p>"
        f"<p><a class='mail-btn' href='{link}'>Vérifier ou contester cette opération</a></p>"
        f"<div class='mail-fine'>Ce lien sécurisé expire dans {TOKEN_TTL_HOURS} h. "
        f"Pour votre sécurité, nous ne vous demanderons jamais votre code "
        f"confidentiel ni vos identifiants complets.</div>"
    )

    return {
        "transaction_id": tid,
        "subject": subject,
        "recipient": masked,
        "token": token,
        "link": link,
        "body_text": body_text,
        "body_html": body_html,
    }
