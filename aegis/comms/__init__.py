"""
Communications & droit de réponse.

Transforme une décision en artefacts responsables :
- PDF d'audit (explicabilité réglementaire, droit à l'explication RGPD) ;
- notification client (transparence, sans accusation tant que non confirmé) ;
- jeton de contestation pour le portail de réclamation (droit de réponse).
"""

from aegis.comms.notify import (
    build_client_email,
    contestation_token,
    decode_token,
)
from aegis.comms.report import (
    build_audit_html,
    build_audit_pdf,
    audit_artifact,
)

__all__ = [
    "build_client_email",
    "contestation_token",
    "decode_token",
    "build_audit_html",
    "build_audit_pdf",
    "audit_artifact",
]
