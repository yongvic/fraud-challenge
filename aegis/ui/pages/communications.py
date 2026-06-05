"""
Communications & droit de réponse.

Quatre temps :
1. PDF d'audit — explicabilité réglementaire téléchargeable.
2. Notification client — message de vigilance (sans accusation), avec lien de
   contestation à usage unique.
3. Portail de contestation — simulation de l'expérience client (droit de réponse)
   qui réinjecte un dossier dans le circuit d'investigation.
4. Journal — communications émises et réclamations reçues (traçabilité).
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from aegis.comms import audit_artifact, build_client_email, decode_token
from aegis.ui.components import (
    alert_card,
    empty_state,
    kpi_strip,
    page_header,
    section_title,
)


def _alert_options(decisions):
    return [d for d in decisions if d["is_suspicious"]]


def render(ctx) -> None:
    decisions = ctx["decisions"]
    store = ctx["store"]
    store.sync_alerts(decisions, actor="system")

    page_header(
        "Responsabilité",
        "Communications & droit de réponse",
        "Une détection responsable ne se contente pas de bloquer : elle explique, "
        "informe le client et lui ouvre un canal de contestation. Tout est tracé.",
    )

    comms = store.list_communications()
    contests = store.list_contestations()
    kpi_strip([
        ("Notifications", str(sum(1 for c in comms if c["channel"] == "Email client")),
         "clients informés"),
        ("PDF d'audit", str(sum(1 for c in comms if c["channel"] == "PDF audit")),
         "générés"),
        ("Contestations", str(len(contests)), "droit de réponse exercé"),
        ("À réexaminer", str(sum(1 for c in contests
                                 if "prioritaire" in (c["outcome"] or ""))),
         "priorité haute"),
    ])
    st.write("")

    alerts = _alert_options(decisions)
    if not alerts:
        empty_state("Aucune alerte", "Aucune transaction signalée à traiter ici.")
        return

    by_id = {d["transaction_id"]: d for d in alerts}
    pick = st.selectbox(
        "Dossier concerné",
        list(by_id.keys()),
        format_func=lambda t: f"{t} · {by_id[t]['level']} · {by_id[t]['reason']}",
    )
    decision = by_id[pick]
    case = store.get_case(pick)

    tab_pdf, tab_mail, tab_portal, tab_log = st.tabs(
        ["Rapport d'audit", "Notification client", "Portail de contestation",
         "Journal"])

    # ── Rapport d'audit ────────────────────────────────────────────────
    with tab_pdf:
        col_a, col_b = st.columns([1.5, 1])
        with col_a:
            section_title("Explicabilité", "Document d'audit de la décision")
            st.markdown(
                "<div class='summary'>Document lisible reprenant le motif en clair, "
                "la décomposition des trois couches de détection, les reason codes "
                "traduits et la traçabilité de la décision humaine. Conforme au "
                "<b>droit à l'explication</b> (RGPD art. 22) et aux obligations de "
                "diligence (LCB-FT).</div>",
                unsafe_allow_html=True,
            )
            artifact = audit_artifact(decision, case)
            if st.download_button(
                f"Générer et télécharger ({artifact['kind']})",
                data=artifact["data"], file_name=artifact["filename"],
                mime=artifact["mime"], type="primary",
                use_container_width=True, key=f"dl_{pick}",
            ):
                store.log_communication(pick, "PDF audit",
                                        decision["user_masked"],
                                        f"Rapport d'audit {pick}",
                                        actor=st.session_state.get("current_user", "Analyste"))
            st.caption(f"Format servi : {artifact['kind']} "
                       f"({len(artifact['data'])//1024 or 1} Ko)")
        with col_b:
            alert_card(decision)

    # ── Notification client ────────────────────────────────────────────
    with tab_mail:
        email = build_client_email(decision)
        section_title("Transparence", "Aperçu de la notification client")
        st.markdown(
            "<div class='summary'>Tant que la fraude n'est pas confirmée par un "
            "humain, le message reste une <b>alerte de vigilance</b>, jamais une "
            "accusation. Aucun détail technique (score, autres clients) n'est "
            "exposé. Le client garde un montant reconnaissable et un lien de "
            "contestation à usage unique.</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            f"<div class='mail'>"
            f"<div class='mail-bar'>"
            f"<span class='mail-dot' style='background:#fb7185'></span>"
            f"<span class='mail-dot' style='background:#fbbf24'></span>"
            f"<span class='mail-dot' style='background:#34d399'></span></div>"
            f"<div class='mail-head'><div class='mail-subj'>{email['subject']}</div>"
            f"<div class='mail-from'>Sécurité Aegis · à : client {email['recipient']}</div></div>"
            f"<div class='mail-body'>{email['body_html']}</div></div>",
            unsafe_allow_html=True,
        )
        c1, c2 = st.columns([1, 2])
        if c1.button("Envoyer la notification", type="primary",
                     use_container_width=True, key=f"send_{pick}"):
            store.log_communication(pick, "Email client", email["recipient"],
                                    email["subject"], token=email["token"],
                                    actor=st.session_state.get("current_user", "Analyste"))
            st.success("Notification consignée et envoyée (simulation).")
        c2.caption(f"Jeton de contestation : {email['token'][:22]}…  ·  expire en 72 h")

    # ── Portail de contestation (vue client) ───────────────────────────
    with tab_portal:
        section_title("Droit de réponse", "Portail de contestation (vue client)")
        st.markdown(
            "<div class='summary'>Simulation de ce que voit le client en cliquant "
            "le lien sécurisé. Sa réponse ne supprime pas l'alerte : elle crée un "
            "<b>dossier de contestation lié</b>, réinjecté vers un analyste, et "
            "alimente la boucle de feedback (qualité de détection).</div>",
            unsafe_allow_html=True,
        )
        token = build_client_email(decision)["token"]
        payload = decode_token(token)
        if not payload:
            st.error("Lien invalide.")
        elif payload.get("expired"):
            st.warning("Ce lien de contestation a expiré.")
        else:
            st.caption(f"Opération concernée : {decision['transaction_id']} · "
                       f"{decision.get('merchant') or '—'}")
            recognized = st.radio(
                "Reconnaissez-vous cette opération ?",
                ["Oui, c'est bien moi", "Non, je ne reconnais pas"],
                key=f"rec_{pick}",
            )
            message = st.text_area(
                "Précisez le contexte (voyage, achat, carte prêtée…)",
                placeholder="Votre explication…", key=f"msg_{pick}",
            )
            evidence = st.text_input(
                "Justificatif (référence ou nom de fichier, optionnel)",
                placeholder="ex. billet_avion.pdf", key=f"ev_{pick}",
            )
            if st.button("Envoyer ma réponse", type="primary",
                         use_container_width=True, key=f"contest_{pick}"):
                outcome = store.add_contestation(
                    pick, token, recognized.startswith("Oui"), message, evidence)
                st.success(f"Réclamation enregistrée. Suite : {outcome}.")
                st.caption("Un accusé de réception a été envoyé au client (simulation).")

    # ── Journal ────────────────────────────────────────────────────────
    with tab_log:
        section_title("Traçabilité", "Communications émises")
        all_comms = store.list_communications()
        if all_comms:
            df = pd.DataFrame(all_comms)[["ts", "transaction_id", "channel",
                                          "recipient", "subject", "status"]]
            df.columns = ["Horodatage", "Dossier", "Canal", "Destinataire",
                          "Objet", "Statut"]
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            empty_state("Aucune communication", "Générez un PDF ou envoyez une notification.")

        section_title("Droit de réponse", "Contestations reçues")
        all_contests = store.list_contestations()
        if all_contests:
            df = pd.DataFrame(all_contests)[["ts", "transaction_id", "recognized",
                                             "message", "outcome"]]
            df.columns = ["Horodatage", "Dossier", "Reconnu", "Message", "Suite"]
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            empty_state("Aucune contestation", "Le portail de contestation alimentera ce journal.")
