"""
Aegis — Plateforme de prévention du crime financier.

Couche « entreprise » construite au-dessus du moteur de détection deterministe
du hackathon (``fraud_detection.detect_fraud``). Le moteur noté reste la source
de vérité auditable ; Aegis l'augmente d'un orchestrateur de décision (règles +
ML + graphe), d'une gestion de dossiers avec piste d'audit, et d'une UX premium
multi-persona.

Importé uniquement par ``app.py`` : le contrat technique (``detect_fraud`` /
``load_transactions``) n'est jamais modifié.
"""

__version__ = "1.0.0"
__product__ = "Aegis"
__tagline__ = "Financial Crime Intelligence Platform"
