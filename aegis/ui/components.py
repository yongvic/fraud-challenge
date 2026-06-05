"""
Composants UI réutilisables (premium, cohérents avec le design system).

Évite la duplication entre pages : en-têtes, bandeau KPI, cartes d'alerte
explicables, barres de couches, états vides.
"""

from __future__ import annotations

from datetime import datetime, timezone

import streamlit as st

from aegis.config import RISK_COLORS

LAYER_COLORS = {
    "Règles": "#fb7185",
    "ML anomalie": "#60a5fa",
    "Réseau": "#a855f7",
}


def page_header(eyebrow: str, title: str, subtitle: str = "") -> None:
    html = f"<div class='eyebrow'>{eyebrow}</div><div class='page-title'>{title}</div>"
    if subtitle:
        html += f"<div class='page-sub'>{subtitle}</div>"
    st.markdown(html, unsafe_allow_html=True)


def fmt_amount(amount, currency) -> str:
    if not isinstance(amount, (int, float)):
        return "montant manquant"
    txt = f"{amount:,.2f}".replace(",", " ").replace(".", ",")
    return f"{txt} {currency or ''}".strip()


def fmt_date(ts) -> str:
    if not ts:
        return "date manquante"
    try:
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.strftime("%d/%m · %Hh%M")
    except (ValueError, TypeError):
        return str(ts)


def kpi_strip(items: list[tuple[str, str, str]]) -> None:
    """items : liste de (label, valeur, indice). Valeur peut contenir une couleur via #."""
    cells = []
    for label, value, hint in items:
        cells.append(
            f"<div class='kpi'><div class='lbl'>{label}</div>"
            f"<div class='val mono'>{value}</div>"
            f"<div class='hint'>{hint}</div></div>"
        )
    st.markdown(
        f"<div class='kpi-strip' style='--n:{len(items)}'>{''.join(cells)}</div>",
        unsafe_allow_html=True,
    )


def layer_bars(decision: dict) -> str:
    """Barres de contribution des trois couches (transparence du score)."""
    rows = [
        ("Règles", decision.get("rule_score", 0.0), LAYER_COLORS["Règles"]),
        ("ML anomalie", decision.get("ml_score", 0.0), LAYER_COLORS["ML anomalie"]),
        ("Réseau", decision.get("ring_score", 0.0), LAYER_COLORS["Réseau"]),
    ]
    bars = ""
    for name, val, color in rows:
        bars += (
            f"<div class='layer'><div class='lname'>{name}</div>"
            f"<div class='track'><div class='fill' style='width:{val*100:.0f}%;"
            f"background:{color}'></div></div>"
            f"<div class='lval mono'>{val:.2f}</div></div>"
        )
    return f"<div class='layer-bars'>{bars}</div>"


def alert_card(decision: dict, focus: bool = False, masked: bool = True) -> None:
    """Carte d'alerte explicable (score, couches, reason codes, justification)."""
    level = decision.get("level", "Sain")
    color = RISK_COLORS.get(level, "#64748b")
    user = decision.get("user_masked") if masked else decision.get("user_id")
    codes = decision.get("reason_code_labels") or []
    codes_html = "".join(f"<span class='code'>{c}</span>" for c in codes)
    focus_cls = " focus" if focus else ""

    st.markdown(
        f"<div class='alert{focus_cls}' style='--c:{color};--edge:{color}55;--bg:{color}0f'>"
        f"<div class='alert-top'><span class='dot'></span>"
        f"<span class='tid'>{decision.get('transaction_id')}</span>"
        f"<span style='flex:1'></span>"
        f"<span class='chip'>{level} · <span class='mono'>{decision.get('fraud_score', 0):.2f}</span></span>"
        f"</div>"
        f"<div class='reason'>{decision.get('reason', '')}</div>"
        f"<div class='meta'>Client <b>{user}</b> · "
        f"{fmt_amount(decision.get('amount'), decision.get('currency'))} · "
        f"{decision.get('merchant') or '—'} · {decision.get('country') or '—'} · "
        f"{fmt_date(decision.get('timestamp'))}</div>"
        f"<div class='codes'>{codes_html}</div>"
        f"{layer_bars(decision)}"
        f"</div>",
        unsafe_allow_html=True,
    )


def empty_state(title: str, text: str) -> None:
    st.markdown(
        f"<div class='empty'><div class='big'>{title}</div>{text}</div>",
        unsafe_allow_html=True,
    )


def panel(html: str) -> None:
    st.markdown(f"<div class='panel'>{html}</div>", unsafe_allow_html=True)
