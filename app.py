"""
Interface Streamlit — Poste de supervision anti-fraude (édition complète).

Le jury lance :  streamlit run app.py

Fonctionnalités :
  - Triage des alertes (recherche, filtres, décomposition des signaux)
  - Fiche client 360°, simulateur « Et si ? », comparaison naïf vs physique
  - Mode démo guidé pour le jury, export CSV, carte voyage impossible
"""

from datetime import datetime, timedelta, timezone
from io import StringIO
from pathlib import Path

import pandas as pd
import streamlit as st

from fraud_detection import (
    COUNTRY_CENTROIDS,
    SIGNAL_LABELS,
    analyze_signals,
    build_client_profile,
    composite_score,
    detect_fraud,
    detect_fraud_naive,
    get_travel_info,
    load_transactions,
)

SAMPLE_CSV = Path(__file__).parent / "data" / "sample_transactions.csv"

RISK = {
    "Critique": "#fb7185",
    "Élevé": "#fbbf24",
    "Modéré": "#60a5fa",
    "Sain": "#34d399",
}

REASON_HELP = {
    "Montant nul ou négatif":
        "Un paiement de 0 ou un montant négatif n'a pas de sens commercial.",
    "Montant très supérieur à l'habitude du client":
        "Montant très au-dessus de la médiane personnelle du client.",
    "Deux pays différents en trop peu de temps":
        "Trajet physiquement impossible (distance réelle ÷ vitesse avion).",
    "Champs obligatoires manquants":
        "Données essentielles absentes.",
    "Fréquence de transactions anormale":
        "Rafale typique d'un test de carte volée.",
    "Transaction conforme au profil du client":
        "Cohérent avec l'historique du client.",
}

DEMO_STEPS = [
    {"id": "T-001", "title": "Transaction normale",
     "text": "Dépense habituelle (~50 EUR). Aucune alerte : le profil client est respecté."},
    {"id": "T-004", "title": "Montant aberrant",
     "text": "4 800 EUR chez une bijouterie à 3h du matin : 100× la médiane du client."},
    {"id": "T-010", "title": "Voyage impossible (départ)",
     "text": "Paris 10h00. Prochaine opération à Tokyo 40 min après : physiquement impossible."},
    {"id": "T-030", "title": "Faux positif évité",
     "text": "FR puis US 3 jours plus tard : le détecteur naïf (3h) alerterait à tort. Notre moteur physique, non."},
]


# ── Helpers ───────────────────────────────────────────────────────────────
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
          html, body, [class*="css"], .stMarkdown { font-family: 'Plus Jakarta Sans', system-ui, sans-serif; color: #e4e4e7; }
          .block-container { padding-top: 2rem; max-width: 1280px; }
          [data-testid="stSidebar"] { background: #111113; border-right: 1px solid #1f1f23; }
          .mono { font-family: 'JetBrains Mono', monospace; font-variant-numeric: tabular-nums; }
          .app-title { font-size: 1.85rem; font-weight: 800; color: #fafafa; letter-spacing: -0.02em; }
          .app-sub { color: #a1a1aa; font-size: .94rem; max-width: 65ch; }
          .summary { border: 1px solid #1f1f23; background: #131316; border-radius: 14px;
            padding: 16px 20px; margin: 16px 0 8px; color: #d4d4d8; }
          .summary b { color: #fafafa; }
          .kpi-strip { display: grid; grid-template-columns: repeat(5, 1fr);
            border: 1px solid #1f1f23; border-radius: 14px; overflow: hidden; background: #131316; }
          .kpi { padding: 16px 18px; border-right: 1px solid #1f1f23; }
          .kpi:last-child { border-right: none; }
          .kpi .lbl { color: #8b8b93; font-size: .72rem; font-weight: 600; text-transform: uppercase; }
          .kpi .val { font-size: 1.7rem; font-weight: 700; color: #fafafa; margin-top: 4px; }
          .kpi .hint { color: #71717a; font-size: .76rem; }
          .alert { border: 1px solid var(--edge); background: var(--bg); border-radius: 14px;
            padding: 16px 18px; margin-bottom: 12px; }
          .alert.demo-focus { outline: 2px solid #34d399; outline-offset: 2px; }
          .alert-top { display: flex; align-items: center; gap: 10px; }
          .dot { width: 9px; height: 9px; border-radius: 50%; background: var(--c); }
          .tid { font-weight: 700; color: #fafafa; }
          .chip { font-size: .72rem; font-weight: 700; color: #0a0a0b; background: var(--c);
            padding: 3px 10px; border-radius: 999px; }
          .why { color: #a1a1aa; font-size: .86rem; margin-top: 10px; border-top: 1px solid #1f1f23;
            padding-top: 10px; }
          .empty { border: 1px dashed #2a2a30; border-radius: 14px; padding: 40px 20px; text-align: center;
            color: #a1a1aa; }
          .empty .big { color: #fafafa; font-weight: 700; font-size: 1.1rem; }
          .travel-box { border: 1px solid #1f1f23; background: #131316; border-radius: 14px;
            padding: 16px; margin: 8px 0; }
          @media (max-width: 900px) { .kpi-strip { grid-template-columns: 1fr 1fr; } }
          @media (prefers-reduced-motion: reduce) { * { transition: none !important; } }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _build_dataframe(transactions, results) -> pd.DataFrame:
    by_id = {r["transaction_id"]: r for r in results}
    rows = []
    for i, tx in enumerate(transactions):
        r = by_id.get(tx.get("transaction_id"), {})
        score = float(r.get("fraud_score", 0.0))
        sigs = analyze_signals(transactions, i)
        rows.append({
            "Index": i,
            "ID": tx.get("transaction_id"),
            "Client": tx.get("user_id"),
            "Montant": tx.get("amount"),
            "Devise": tx.get("currency"),
            "Commerçant": tx.get("merchant"),
            "Pays": tx.get("country"),
            "Date": tx.get("timestamp"),
            "Carte présente": tx.get("card_present"),
            "Score": round(score, 2),
            "Score composite": composite_score(sigs),
            "Suspecte": bool(r.get("is_suspicious", False)),
            "Niveau": _risk_band(score),
            "Motif": r.get("reason", "—"),
        })
    return pd.DataFrame(rows)


def _render_signal_bars(transactions, index):
    signals = analyze_signals(transactions, index)
    if not signals:
        st.caption("Aucun signal de risque détecté.")
        return
    for key, val in sorted(signals.items(), key=lambda x: -x[1]):
        label = SIGNAL_LABELS.get(key, key)
        st.progress(min(1.0, val), text=f"{label} — {val:.2f}")
    st.caption(f"Score composite (affichage) : **{composite_score(signals):.2f}**")


def _render_alert_card(row, transactions, highlight=False):
    color = RISK[row["Niveau"]]
    key = _reason_key(row["Motif"])
    demo_cls = " demo-focus" if highlight else ""
    idx = int(row["Index"])
    st.markdown(
        f"<div class='alert{demo_cls}' style='--c:{color};--edge:{color}55;--bg:{color}0f'>"
        f"<div class='alert-top'><span class='dot'></span>"
        f"<span class='tid'>{row['ID']}</span><span style='flex:1'></span>"
        f"<span class='chip'>{row['Niveau']} · <span class='mono'>{row['Score']:.2f}</span></span></div>"
        f"<div style='color:#fafafa;font-weight:600;margin:8px 0 2px'>{row['Motif']}</div>"
        f"<div style='color:#a1a1aa;font-size:.86rem'>Client <b>{row['Client']}</b> · "
        f"{_fmt_amount(row['Montant'], row['Devise'])} · {row['Commerçant'] or '—'} · "
        f"{row['Pays'] or '—'} · {_fmt_date(row['Date'])}</div>"
        f"<div class='why'>{REASON_HELP.get(key, '')}</div></div>",
        unsafe_allow_html=True,
    )
    travel = get_travel_info(transactions, idx)
    if travel:
        st.markdown(
            f"<div class='travel-box'><b>Voyage analysé</b> : {travel['country_from']} → "
            f"{travel['country_to']}<br>Distance <span class='mono'>{travel['distance_km'] or '?'} km</span> · "
            f"Temps min <span class='mono'>{travel['min_hours']} h</span> · "
            f"Écoulé <span class='mono'>{travel['actual_hours']} h</span></div>",
            unsafe_allow_html=True,
        )
    with st.expander("Décomposition des signaux"):
        _render_signal_bars(transactions, idx)


def _export_alerts_csv(df):
    flagged = df[df["Suspecte"]].copy()
    buf = StringIO()
    flagged.to_csv(buf, index=False)
    return buf.getvalue()


# ── Interface principale ──────────────────────────────────────────────────
def render_interface(transactions: list[dict], results: list[dict]) -> None:
    _inject_css()
    df = _build_dataframe(transactions, results)

    total = len(df)
    alerts = int(df["Suspecte"].sum()) if total else 0
    rate = (alerts / total * 100) if total else 0.0
    amount_at_risk = df.loc[df["Suspecte"], "Montant"].apply(
        lambda x: x if isinstance(x, (int, float)) and x > 0 else 0).sum()
    all_clients = df["Client"].nunique()
    alert_clients = df.loc[df["Suspecte"], "Client"].nunique()
    protected = all_clients - alert_clients

    st.markdown(
        f"<div class='summary'>Sur <b>{total}</b> transactions, <b>{alerts}</b> alerte(s), "
        f"<b>{protected}</b> client(s) protégé(s) sans fausse alerte. "
        f"Exposition : <b class='mono'>{amount_at_risk:,.0f}</b>.</div>".replace(",", " "),
        unsafe_allow_html=True,
    )

    st.markdown(
        "<div class='kpi-strip'>"
        f"<div class='kpi'><div class='lbl'>Transactions</div><div class='val mono'>{total}</div></div>"
        f"<div class='kpi'><div class='lbl'>Alertes</div>"
        f"<div class='val mono' style='color:{RISK['Critique']}'>{alerts}</div></div>"
        f"<div class='kpi'><div class='lbl'>Clients protégés</div>"
        f"<div class='val mono' style='color:{RISK['Sain']}'>{protected}</div></div>"
        f"<div class='kpi'><div class='lbl'>Taux</div><div class='val mono'>{rate:.0f}%</div></div>"
        f"<div class='kpi'><div class='lbl'>À risque</div><div class='val mono'>{amount_at_risk:,.0f}</div></div>"
        "</div>".replace(",", " "),
        unsafe_allow_html=True,
    )

    st.download_button(
        "Exporter les alertes (CSV)",
        data=_export_alerts_csv(df),
        file_name="rapport_alertes.csv",
        mime="text/csv",
    )

    tabs = st.tabs([
        "Alertes", "Vue d'ensemble", "Fiche client 360°",
        "Simulateur Et si ?", "Comparaison naïf", "Démo jury", "Tout",
    ])

    # ── Alertes ───────────────────────────────────────────────────────
    with tabs[0]:
        c1, c2, c3 = st.columns([1, 1, 1])
        search = c1.text_input("Rechercher par ID", placeholder="T-004, U2…")
        sel_client = c2.selectbox(
            "Client", ["Tous"] + sorted(df["Client"].dropna().unique()))
        only_crit = c3.toggle("Critique uniquement", value=True)

        view = df[df["Suspecte"]].copy()
        if search:
            view = view[view["ID"].astype(str).str.contains(search, case=False, na=False)]
        if sel_client != "Tous":
            view = view[view["Client"] == sel_client]
        if only_crit:
            view = view[view["Niveau"] == "Critique"]
        view = view.sort_values("Score", ascending=False)

        if view.empty:
            st.markdown("<div class='empty'><div class='big'>Aucune alerte</div>"
                        "Élargissez les filtres ou consultez l'onglet Tout.</div>",
                        unsafe_allow_html=True)
        for _, row in view.iterrows():
            _render_alert_card(row, transactions)

    # ── Vue d'ensemble ────────────────────────────────────────────────
    with tabs[1]:
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("###### Motifs d'alerte")
            flagged = df[df["Suspecte"]]
            if len(flagged):
                counts = flagged["Motif"].apply(_reason_key).value_counts()
                st.bar_chart(counts, horizontal=True, color=RISK["Élevé"])
            else:
                st.caption("Aucune alerte.")
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

        st.markdown("###### Voyages impossibles détectés")
        for i, tx in enumerate(transactions):
            info = get_travel_info(transactions, i)
            if info and info.get("impossible"):
                st.markdown(
                    f"**{tx.get('transaction_id')}** ({info['country_from']} → "
                    f"{info['country_to']}) : distance **{info['distance_km']} km**, "
                    f"minimum **{info['min_hours']} h**, écoulé **{info['actual_hours']} h**"
                )

    # ── Fiche client 360° ─────────────────────────────────────────────
    with tabs[2]:
        clients = sorted(df["Client"].dropna().unique())
        if not clients:
            st.info("Aucun client.")
        else:
            uid = st.selectbox("Choisir un client", clients)
            profile = build_client_profile(transactions, uid)
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Opérations", profile["transaction_count"])
            med = profile["median_amount"]
            c2.metric("Médiane", f"{med:,.0f}" if med else "—")
            c3.metric("Pays", ", ".join(profile["countries"]) or "—")
            c4.metric("Devises", ", ".join(profile["currencies"]) or "—")

            amounts = [t["amount"] for t in profile["timeline"]
                       if isinstance(t.get("amount"), (int, float))]
            if amounts:
                st.line_chart(pd.Series(amounts, name="Montant"))

            st.markdown("###### Chronologie")
            tl = pd.DataFrame(profile["timeline"])
            if not tl.empty:
                tl["Date affichée"] = tl["timestamp"].apply(_fmt_date)
                st.dataframe(
                    tl[["transaction_id", "Date affichée", "amount", "country", "merchant"]],
                    use_container_width=True, hide_index=True,
                )

            client_alerts = df[(df["Client"] == uid) & df["Suspecte"]]
            if not client_alerts.empty:
                st.markdown("###### Alertes de ce client")
                for _, row in client_alerts.iterrows():
                    _render_alert_card(row, transactions)

    # ── Simulateur Et si ? ────────────────────────────────────────────
    with tabs[3]:
        st.caption("Modifiez une transaction et observez le verdict en direct.")
        ids = [tx.get("transaction_id") for tx in transactions]
        pick = st.selectbox("Transaction de base", ids)
        base_idx = ids.index(pick)
        base = dict(transactions[base_idx])

        c1, c2, c3 = st.columns(3)
        sim_amount = c1.number_input("Montant", value=float(base.get("amount") or 0.0))
        sim_country = c2.text_input("Pays (code ISO)", value=base.get("country") or "FR")
        sim_hours = c3.slider("Heure (décalage depuis base)", -72, 72, 0)

        base_dt = _parse_dt(base.get("timestamp"))
        if base_dt:
            new_dt = base_dt + timedelta(hours=sim_hours)
            sim_ts = new_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        else:
            sim_ts = base.get("timestamp")

        sim_tx = {**base, "amount": sim_amount, "country": sim_country,
                  "timestamp": sim_ts}
        sim_batch = list(transactions)
        sim_batch[base_idx] = sim_tx
        sim_result = detect_fraud(sim_batch)[base_idx]
        sim_sigs = analyze_signals(sim_batch, base_idx)

        col_l, col_r = st.columns(2)
        with col_l:
            orig = results[base_idx]
            st.markdown("**Verdict original**")
            st.write(f"Score : {orig['fraud_score']:.2f}")
            st.write(f"Suspecte : {orig['is_suspicious']}")
            st.write(orig["reason"])
        with col_r:
            st.markdown("**Verdict simulé**")
            color = RISK["Critique"] if sim_result["is_suspicious"] else RISK["Sain"]
            st.markdown(f"<span style='color:{color};font-weight:700'>"
                        f"Score : {sim_result['fraud_score']:.2f}</span>",
                        unsafe_allow_html=True)
            st.write(f"Suspecte : {sim_result['is_suspicious']}")
            st.write(sim_result["reason"])

        st.markdown("###### Signaux simulés")
        _render_signal_bars(sim_batch, base_idx)

    # ── Comparaison naïf vs physique ──────────────────────────────────
    with tabs[4]:
        st.caption("Le détecteur naïf alerte sur tout changement de pays en moins de 3 h. "
                   "Notre moteur physique évite les faux positifs (ex. FR → US en 3 jours).")
        naive = detect_fraud_naive(transactions)
        cmp_rows = []
        for i, (our, nav) in enumerate(zip(results, naive)):
            cmp_rows.append({
                "ID": transactions[i].get("transaction_id"),
                "Pays": transactions[i].get("country"),
                "Notre verdict": "Alerte" if our["is_suspicious"] else "OK",
                "Naïf (3h)": "Alerte" if nav["is_suspicious"] else "OK",
                "Différence": our["is_suspicious"] != nav["is_suspicious"],
            })
        cmp_df = pd.DataFrame(cmp_rows)
        st.dataframe(cmp_df, use_container_width=True, hide_index=True)
        diff = cmp_df[cmp_df["Différence"]]
        if not diff.empty:
            st.success(f"{len(diff)} cas où notre moteur est plus précis que le naïf.")
            st.dataframe(diff, use_container_width=True, hide_index=True)
        else:
            st.info("Mêmes verdicts sur ce lot (normal si peu de voyages longs).")

    # ── Démo jury ─────────────────────────────────────────────────────
    with tabs[5]:
        if "demo_step" not in st.session_state:
            st.session_state.demo_step = 0

        step = st.session_state.demo_step
        if step < len(DEMO_STEPS):
            d = DEMO_STEPS[step]
            st.markdown(f"### Étape {step + 1}/{len(DEMO_STEPS)} — {d['title']}")
            st.info(d["text"])
            row = df[df["ID"] == d["id"]]
            if not row.empty:
                _render_alert_card(row.iloc[0], transactions, highlight=True)
            c1, c2 = st.columns(2)
            label = "Terminer la démo" if step == len(DEMO_STEPS) - 1 else "Étape suivante"
            if c1.button(label, type="primary"):
                st.session_state.demo_step = step + 1
                st.rerun()
            if c2.button("Recommencer la démo"):
                st.session_state.demo_step = 0
                st.rerun()
        else:
            st.success("Démo terminée. Explorez le simulateur ou la comparaison naïf.")
            if st.button("Recommencer"):
                st.session_state.demo_step = 0
                st.rerun()

    # ── Tout ──────────────────────────────────────────────────────────
    with tabs[6]:
        st.dataframe(
            df.drop(columns=["Index"]),
            use_container_width=True, hide_index=True,
            column_config={
                "Score": st.column_config.ProgressColumn("Score", 0.0, 1.0, "%.2f"),
                "Score composite": st.column_config.ProgressColumn("Composite", 0.0, 1.0, "%.2f"),
                "Suspecte": st.column_config.CheckboxColumn("Suspecte"),
            },
        )


def _parse_dt(ts):
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


def main() -> None:
    st.set_page_config(
        page_title="Supervision anti-fraude — INTELO2026",
        page_icon="◆",
        layout="wide",
    )
    _inject_css()

    st.markdown(
        "<div style='color:#71717a;font-size:.72rem;font-weight:600;"
        "letter-spacing:.15em;text-transform:uppercase'>Hackathon INTELO2026</div>"
        "<div class='app-title'>Poste de supervision anti-fraude</div>"
        "<div class='app-sub'>Détection explicable, simulation en direct, fiches clients "
        "et comparaison naïf vs physique. Pensé pour un agent et un jury non technique.</div>",
        unsafe_allow_html=True,
    )

    with st.sidebar:
        st.markdown("#### Données")
        use_sample = st.toggle("Jeu d'exemple", value=True)
        transactions: list[dict] = []
        if use_sample:
            transactions = load_transactions(str(SAMPLE_CSV))
            st.caption(f"{len(transactions)} transactions")
        else:
            uploaded = st.file_uploader("Importer un CSV", type=["csv"])
            if uploaded:
                tmp = Path(".streamlit_upload.csv")
                tmp.write_bytes(uploaded.getvalue())
                transactions = load_transactions(str(tmp))
                tmp.unlink(missing_ok=True)
                st.caption(f"{len(transactions)} transactions importées")

        st.markdown("---")
        st.markdown("#### Règles du moteur")
        with st.expander("Montant & profil"):
            st.caption("Médiane robuste par client. Alerte si ≥ 5× l'habitude.")
        with st.expander("Voyage impossible"):
            st.caption("Distance réelle entre pays ÷ 1000 km/h (vitesse avion).")
        with st.expander("Signaux secondaires (UI)"):
            st.caption("Horaire nuit, carte absente, commerçant à risque, doublon, devise inhabituelle.")
        with st.expander("Rafales & champs"):
            st.caption("4+ opérations en 2 min, ou champs obligatoires manquants.")

        if st.button("Lancer la démo jury"):
            st.session_state.demo_step = 0
            st.session_state.goto_demo = True

    if not transactions:
        st.markdown("<div class='empty'><div class='big'>Aucune donnée</div>"
                    "Chargez le jeu d'exemple ou un CSV.</div>", unsafe_allow_html=True)
        return

    try:
        results = detect_fraud(transactions)
    except NotImplementedError:
        st.error("Implémentez detect_fraud dans fraud_detection.py.")
        return
    except Exception as exc:
        st.error(f"Erreur : {exc}")
        return

    render_interface(transactions, results)


if __name__ == "__main__":
    main()
