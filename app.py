"""
Interface Streamlit — Poste de supervision anti-fraude.

Le jury lance :  streamlit run app.py

Conception (skill "impeccable") :
  - contraste vérifié, typographie Plus Jakarta Sans + JetBrains Mono (chiffres) ;
  - palette neutre disciplinée + couleurs sémantiques de risque uniquement ;
  - aucune anti-pattern (pas de bordure latérale colorée, pas de texte dégradé,
    pas de glow décoratif), états vide / chargement soignés ;
  - pensée pour un public NON technique : une phrase de synthèse, un tri clair
    des alertes, et le « pourquoi » de chaque décision en langage simple.

Le contrat technique est respecté : l'appel à detect_fraud / load_transactions
n'est pas modifié.
"""

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st

from fraud_detection import COUNTRY_CENTROIDS, detect_fraud, load_transactions

SAMPLE_CSV = Path(__file__).parent / "data" / "sample_transactions.csv"

# Couleurs sémantiques par niveau de risque (usage fonctionnel, pas décoratif).
RISK = {
    "Critique": "#fb7185",
    "Élevé": "#fbbf24",
    "Modéré": "#60a5fa",
    "Sain": "#34d399",
}

# Explication pédagogique de chaque type de motif (pour le public non technique).
REASON_HELP = {
    "Montant nul ou négatif":
        "Un paiement de 0 ou un montant négatif n'a pas de sens commercial : "
        "souvent un bug exploité ou une manipulation.",
    "Montant très supérieur à l'habitude du client":
        "Ce montant dépasse largement les dépenses habituelles de ce client "
        "(comparaison à sa médiane personnelle, robuste aux exceptions).",
    "Deux pays différents en trop peu de temps":
        "La carte a servi dans deux pays alors que le trajet est physiquement "
        "impossible dans le délai (distance réelle ÷ vitesse max d'un avion).",
    "Champs obligatoires manquants":
        "Des informations essentielles de la transaction sont absentes : "
        "donnée incomplète ou tentative de contournement des contrôles.",
    "Fréquence de transactions anormale":
        "Rafale d'opérations en très peu de temps : signature classique d'un "
        "test de carte volée.",
    "Transaction conforme au profil du client":
        "Rien d'anormal : montant, lieu et rythme cohérents avec l'historique.",
}


# ──────────────────────────────────────────────────────────────────────────
#  Helpers de présentation
# ──────────────────────────────────────────────────────────────────────────
def _risk_band(score: float) -> str:
    if score >= 0.8:
        return "Critique"
    if score >= 0.5:
        return "Élevé"
    if score > 0.0:
        return "Modéré"
    return "Sain"


def _reason_key(reason: str) -> str:
    for key in REASON_HELP:
        if reason.startswith(key):
            return key
    return reason


def _fmt_amount(amount, currency) -> str:
    if not isinstance(amount, (int, float)):
        return "montant manquant"
    txt = f"{amount:,.2f}".replace(",", " ").replace(".", ",")
    return f"{txt} {currency or ''}".strip()


def _fmt_date(ts) -> str:
    if not ts:
        return "date manquante"
    try:
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.strftime("%d/%m · %Hh%M")
    except (ValueError, TypeError):
        return str(ts)


def _inject_css() -> None:
    st.markdown(
        """
        <style>
          @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;600&display=swap');

          .stApp { background: #0a0a0b; }
          html, body, [class*="css"], .stMarkdown, .stApp {
            font-family: 'Plus Jakarta Sans', system-ui, sans-serif;
            color: #e4e4e7;
          }
          .block-container { padding-top: 2.2rem; max-width: 1240px; }
          [data-testid="stSidebar"] { background: #111113; border-right: 1px solid #1f1f23; }
          .mono { font-family: 'JetBrains Mono', monospace; font-variant-numeric: tabular-nums; }

          /* En-tête */
          .app-eyebrow { color:#71717a; font-size:.72rem; font-weight:600;
            letter-spacing:.18em; text-transform:uppercase; }
          .app-title { font-size:1.9rem; font-weight:800; letter-spacing:-0.02em;
            color:#fafafa; margin:.2rem 0 .1rem; line-height:1.1; }
          .app-sub { color:#a1a1aa; font-size:.95rem; max-width:65ch; }

          /* Phrase de synthèse */
          .summary { border:1px solid #1f1f23; background:#131316;
            border-radius:14px; padding:16px 20px; margin:18px 0 8px;
            font-size:1.05rem; color:#d4d4d8; line-height:1.5; }
          .summary b { color:#fafafa; }

          /* Bandeau KPI : un seul panneau, séparateurs fins (pas de cartes spammées) */
          .kpi-strip { display:grid; grid-template-columns:repeat(4,1fr);
            border:1px solid #1f1f23; border-radius:14px; overflow:hidden;
            background:#131316; margin:6px 0 4px; }
          .kpi { padding:18px 20px; border-right:1px solid #1f1f23; }
          .kpi:last-child { border-right:none; }
          .kpi .lbl { color:#8b8b93; font-size:.74rem; font-weight:600;
            letter-spacing:.04em; text-transform:uppercase; }
          .kpi .val { font-size:1.9rem; font-weight:700; color:#fafafa;
            margin-top:6px; }
          .kpi .hint { color:#71717a; font-size:.78rem; margin-top:2px; }

          /* Cartes d'alerte : bordure pleine teintée (jamais de bordure latérale) */
          .alert { border:1px solid var(--edge); background:var(--bg);
            border-radius:14px; padding:16px 18px; margin-bottom:12px; }
          .alert-top { display:flex; align-items:center; gap:10px; }
          .dot { width:9px; height:9px; border-radius:50%; background:var(--c);
            flex:0 0 auto; }
          .tid { font-weight:700; color:#fafafa; font-size:1.02rem; }
          .grow { flex:1; }
          .chip { font-size:.74rem; font-weight:700; color:#0a0a0b;
            background:var(--c); padding:3px 10px; border-radius:999px; }
          .reason { color:#fafafa; font-weight:600; margin:10px 0 2px;
            font-size:1.0rem; }
          .meta { color:#a1a1aa; font-size:.86rem; }
          .track { height:6px; border-radius:999px; background:#26262b;
            margin-top:12px; overflow:hidden; }
          .fill { height:100%; border-radius:999px; background:var(--c); }
          .why { color:#a1a1aa; font-size:.86rem; margin-top:10px;
            border-top:1px solid #1f1f23; padding-top:10px; line-height:1.5; }

          .empty { border:1px dashed #2a2a30; border-radius:16px;
            padding:48px 24px; text-align:center; color:#a1a1aa; }
          .empty .big { color:#fafafa; font-weight:700; font-size:1.15rem;
            margin-bottom:6px; }

          /* Anneau de taux d'alerte (CSS pur, non générique) */
          .ring-wrap { display:flex; align-items:center; gap:20px;
            border:1px solid #1f1f23; background:#131316; border-radius:14px;
            padding:20px; }
          .ring { width:104px; height:104px; border-radius:50%; flex:0 0 auto;
            display:grid; place-items:center;
            background:conic-gradient(var(--c) calc(var(--p)*1%), #26262b 0); }
          .ring .inner { width:78px; height:78px; border-radius:50%;
            background:#131316; display:grid; place-items:center; }
          .ring .pct { font-weight:700; color:#fafafa; font-size:1.3rem; }
          @media (prefers-reduced-motion: reduce) { * { transition:none !important; } }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _build_dataframe(transactions, results) -> pd.DataFrame:
    by_id = {r["transaction_id"]: r for r in results}
    rows = []
    for tx in transactions:
        r = by_id.get(tx.get("transaction_id"), {})
        score = float(r.get("fraud_score", 0.0))
        rows.append({
            "ID": tx.get("transaction_id"),
            "Client": tx.get("user_id"),
            "Montant": tx.get("amount"),
            "Devise": tx.get("currency"),
            "Commerçant": tx.get("merchant"),
            "Pays": tx.get("country"),
            "Date": tx.get("timestamp"),
            "Score": round(score, 2),
            "Suspecte": bool(r.get("is_suspicious", False)),
            "Niveau": _risk_band(score),
            "Motif": r.get("reason", "—"),
        })
    return pd.DataFrame(rows)


# ──────────────────────────────────────────────────────────────────────────
#  Interface principale
# ──────────────────────────────────────────────────────────────────────────
def render_interface(transactions: list[dict], results: list[dict]) -> None:
    """Poste de supervision : synthèse, tri des alertes, explications."""
    _inject_css()
    df = _build_dataframe(transactions, results)

    total = len(df)
    alerts = int(df["Suspecte"].sum()) if total else 0
    rate = (alerts / total * 100) if total else 0.0
    amount_at_risk = df.loc[df["Suspecte"], "Montant"].apply(
        lambda x: x if isinstance(x, (int, float)) and x > 0 else 0).sum()
    clients_touched = df.loc[df["Suspecte"], "Client"].nunique()

    # Phrase de synthèse en langage simple.
    if alerts:
        st.markdown(
            f"<div class='summary'>Sur <b>{total}</b> transactions analysées, "
            f"<b>{alerts}</b> méritent une vérification "
            f"(<b>{clients_touched}</b> client·s concerné·s), pour une exposition "
            f"de <b class='mono'>{amount_at_risk:,.0f}</b> environ. Les autres "
            f"sont conformes au profil habituel.</div>".replace(",", " "),
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f"<div class='summary'>Les <b>{total}</b> transactions analysées sont "
            f"<b>conformes</b> aux profils habituels. Aucune alerte.</div>",
            unsafe_allow_html=True,
        )

    # Bandeau KPI.
    st.markdown(
        "<div class='kpi-strip'>"
        f"<div class='kpi'><div class='lbl'>Transactions</div>"
        f"<div class='val mono'>{total}</div>"
        f"<div class='hint'>analysées</div></div>"
        f"<div class='kpi'><div class='lbl'>Alertes</div>"
        f"<div class='val mono' style='color:{RISK['Critique']}'>{alerts}</div>"
        f"<div class='hint'>à examiner</div></div>"
        f"<div class='kpi'><div class='lbl'>Taux d'alerte</div>"
        f"<div class='val mono'>{rate:.0f}%</div>"
        f"<div class='hint'>des opérations</div></div>"
        f"<div class='kpi'><div class='lbl'>Montant à risque</div>"
        f"<div class='val mono'>{amount_at_risk:,.0f}</div>"
        f"<div class='hint'>exposition</div></div>"
        "</div>".replace(",", " "),
        unsafe_allow_html=True,
    )

    tab_triage, tab_overview, tab_all = st.tabs(
        ["Alertes à traiter", "Vue d'ensemble", "Toutes les transactions"])

    # ── Onglet 1 : triage des alertes ──────────────────────────────────
    with tab_triage:
        c1, c2 = st.columns([1, 1])
        clients = ["Tous les clients"] + sorted(
            c for c in df["Client"].dropna().unique())
        sel_client = c1.selectbox("Filtrer par client", clients,
                                  label_visibility="collapsed")
        levels = c2.multiselect(
            "Niveaux de risque", ["Critique", "Élevé", "Modéré"],
            default=["Critique", "Élevé", "Modéré"],
            label_visibility="collapsed", placeholder="Niveaux de risque")

        view = df[df["Suspecte"]].copy()
        if sel_client != "Tous les clients":
            view = view[view["Client"] == sel_client]
        if levels:
            view = view[view["Niveau"].isin(levels)]
        view = view.sort_values("Score", ascending=False)

        if not len(view):
            st.markdown(
                "<div class='empty'><div class='big'>Rien à traiter ici</div>"
                "Aucune alerte ne correspond aux filtres. Élargissez la sélection "
                "ou consultez « Toutes les transactions ».</div>",
                unsafe_allow_html=True,
            )
        for _, row in view.iterrows():
            color = RISK[row["Niveau"]]
            key = _reason_key(row["Motif"])
            st.markdown(
                f"<div class='alert' style='--c:{color};"
                f"--edge:{color}55;--bg:{color}0f'>"
                f"<div class='alert-top'><span class='dot'></span>"
                f"<span class='tid'>{row['ID']}</span><span class='grow'></span>"
                f"<span class='chip'>{row['Niveau']} · "
                f"<span class='mono'>{row['Score']:.2f}</span></span></div>"
                f"<div class='reason'>{row['Motif']}</div>"
                f"<div class='meta'>Client <b>{row['Client']}</b> · "
                f"{_fmt_amount(row['Montant'], row['Devise'])} · "
                f"{row['Commerçant'] or 'commerçant inconnu'} · "
                f"{row['Pays'] or 'pays inconnu'} · {_fmt_date(row['Date'])}</div>"
                f"<div class='track'><div class='fill' "
                f"style='width:{row['Score']*100:.0f}%'></div></div>"
                f"<div class='why'>{REASON_HELP.get(key, '')}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )

    # ── Onglet 2 : vue d'ensemble ──────────────────────────────────────
    with tab_overview:
        col_a, col_b = st.columns([1, 1])
        with col_a:
            pct = rate
            ring_color = (RISK["Critique"] if pct >= 30
                          else RISK["Élevé"] if pct >= 10 else RISK["Sain"])
            st.markdown(
                f"<div class='ring-wrap'><div class='ring' "
                f"style='--p:{pct:.0f};--c:{ring_color}'>"
                f"<div class='inner'><span class='pct mono'>{pct:.0f}%</span>"
                f"</div></div><div><div style='color:#fafafa;font-weight:700;"
                f"font-size:1.05rem'>Part de transactions signalées</div>"
                f"<div style='color:#a1a1aa;font-size:.88rem;margin-top:4px'>"
                f"{alerts} alerte·s sur {total} opérations</div></div></div>",
                unsafe_allow_html=True,
            )
            st.markdown("###### Pourquoi ça alerte")
            flagged = df[df["Suspecte"]]
            if len(flagged):
                counts = flagged["Motif"].apply(_reason_key).value_counts()
                st.bar_chart(counts, horizontal=True, color=RISK["Élevé"])
            else:
                st.caption("Aucun motif d'alerte.")
        with col_b:
            st.markdown("###### Carte des risques")
            map_rows = []
            for _, r in df.iterrows():
                cen = COUNTRY_CENTROIDS.get(r["Pays"])
                if cen:
                    map_rows.append({
                        "lat": cen[0], "lon": cen[1],
                        "size": 120000 if r["Suspecte"] else 35000,
                        "color": RISK["Critique"] if r["Suspecte"] else RISK["Sain"],
                    })
            if map_rows:
                st.map(pd.DataFrame(map_rows), latitude="lat", longitude="lon",
                       size="size", color="color")
            else:
                st.caption("Pays non localisables.")

    # ── Onglet 3 : tableau complet ─────────────────────────────────────
    with tab_all:
        st.dataframe(
            df,
            use_container_width=True, hide_index=True,
            column_config={
                "Score": st.column_config.ProgressColumn(
                    "Score", min_value=0.0, max_value=1.0, format="%.2f"),
                "Suspecte": st.column_config.CheckboxColumn("Suspecte"),
            },
        )


def main() -> None:
    st.set_page_config(
        page_title="Supervision anti-fraude — INTELO2026",
        page_icon="◆",
        layout="wide",
    )
    _inject_css()

    st.markdown(
        "<div class='app-eyebrow'>Hackathon INTELO2026</div>"
        "<div class='app-title'>Poste de supervision anti-fraude</div>"
        "<div class='app-sub'>Chaque transaction est analysée, scorée et "
        "expliquée en langage clair. L'objectif : repérer les fraudes sans "
        "déranger les clients honnêtes.</div>",
        unsafe_allow_html=True,
    )

    with st.sidebar:
        st.markdown("#### Données")
        use_sample = st.toggle("Jeu d'exemple", value=True)
        transactions: list[dict] = []
        if use_sample:
            transactions = load_transactions(str(SAMPLE_CSV))
            st.caption(f"{len(transactions)} transactions chargées")
        else:
            uploaded = st.file_uploader("Importer un CSV", type=["csv"])
            if uploaded:
                tmp = Path(".streamlit_upload.csv")
                tmp.write_bytes(uploaded.getvalue())
                transactions = load_transactions(str(tmp))
                tmp.unlink(missing_ok=True)
                st.caption(f"{len(transactions)} transactions importées")

        st.markdown("---")
        st.markdown("#### Comment l'IA décide")
        st.markdown(
            "- Montant nul ou négatif\n"
            "- Montant anormal vs habitude du client (médiane robuste)\n"
            "- Voyage impossible (distance réelle ÷ vitesse max d'un avion)\n"
            "- Champs obligatoires manquants\n"
            "- Rafale de transactions (test de carte)\n\n"
            "Chaque alerte est justifiée et scorée de 0 à 1."
        )

    if not transactions:
        st.markdown(
            "<div class='empty'><div class='big'>Aucune donnée chargée</div>"
            "Activez le jeu d'exemple ou importez un CSV dans le panneau de "
            "gauche pour lancer l'analyse.</div>",
            unsafe_allow_html=True,
        )
        return

    try:
        results = detect_fraud(transactions)
    except NotImplementedError:
        st.error("Implémentez d'abord detect_fraud dans fraud_detection.py.")
        return
    except Exception as exc:  # robustesse de l'affichage
        st.error(f"Erreur pendant l'analyse : {exc}")
        return

    render_interface(transactions, results)


if __name__ == "__main__":
    main()
