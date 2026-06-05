# 🛡️ Guide complet du projet — Détection de fraude financière par l'IA

> Document pédagogique : comprendre **ce que fait** ce projet, **comment il marche**,
> **quelle solution** on a implémentée, et **comment aller beaucoup plus loin**.

---

## 1. De quoi parle ce projet ?

### Le problème du monde réel
Chaque jour, des millions de paiements par carte transitent dans le système
bancaire. Une infime partie est **frauduleuse** : carte volée, montant gonflé,
achats dans deux pays à la fois, comptes piratés…

La banque a deux ennemis opposés :
- **Laisser passer une fraude** → elle perd de l'argent et la confiance du client.
- **Bloquer une transaction honnête** (faux positif) → le client est humilié à
  la caisse, appelle le service client, et déteste sa banque.

> 🎯 **Le vrai défi n'est PAS de détecter les fraudes évidentes.**
> C'est de trouver le bon équilibre : attraper les fraudes **sans accabler les
> clients honnêtes.** C'est exactement ce que demande le hackathon (niveau 3).

### Notre mission concrète
Compléter une fonction Python, `detect_fraud(transactions)`, qui :
- reçoit **toutes** les transactions d'un coup (donc on peut comparer chaque
  opération à l'historique du client) ;
- renvoie, pour chacune : un **score de risque** (0 à 1), un **verdict**
  (suspecte ou non) et une **justification lisible**.

---

## 2. Architecture du projet (les 3 fichiers clés)

```
fraud-challenge/
├── fraud_detection.py   ← LE CERVEAU (noté automatiquement par les tests)
│   ├── load_transactions()   → lit le CSV (FOURNI, on n'y touche pas)
│   └── detect_fraud()        → notre logique de détection ⭐
├── app.py               ← L'INTERFACE (jugée par le jury humain)
│   └── render_interface()    → tableau de bord de supervision
└── data/
    ├── sample_transactions.csv  → exemples d'entrée
    └── sample_expected.json     → résultats attendus (notre "corrigé")
```

**Le flux complet :**

```
CSV brut → load_transactions() → liste de transactions "propres"
        → detect_fraud()       → liste de verdicts (score + raison)
        → render_interface()   → écran visuel pour l'humain
```

---

## 3. Comment marche notre moteur de détection ?

`detect_fraud` travaille en **deux temps** :

### Étape A — Construire le profil de chaque client (pré-calcul)
Avant de juger quoi que ce soit, on parcourt toutes les transactions pour bâtir,
**par client** :
- la **liste de ses montants habituels** (pour savoir ce qui est "normal" pour lui) ;
- la **chronologie de ses déplacements** (date + pays de chaque opération) ;
- le **rythme de ses transactions** (pour repérer les rafales).

> 💡 C'est ça la force du sujet : on reçoit **tout le lot d'un coup**, donc on peut
> comparer chaque transaction à l'**historique personnel** du client, pas à une
> règle universelle bête.

### Étape B — Juger chaque transaction (la règle la plus forte gagne)
Pour chaque transaction, on applique nos règles **par ordre de priorité** et on
garde la première qui se déclenche :

| Priorité | Règle | Score | Justification renvoyée |
|---|---|---|---|
| 1 | Montant **nul ou négatif** | 0.90 | « Montant nul ou négatif » |
| 2 | Montant **très supérieur à l'habitude** | 0.90 | « Montant très supérieur à l'habitude du client » |
| 3 | **Voyage impossible** entre 2 pays | 0.88 | « Deux pays différents en trop peu de temps » |
| 4 | **Champ obligatoire manquant** | 0.85 | « Champs obligatoires manquants: … » |
| 5 | **Rafale** de transactions | 0.70 | « Fréquence de transactions anormale » |
| — | Rien d'anormal | 0.00 | « Transaction conforme au profil du client » |

Une transaction est **signalée** (`is_suspicious = True`) dès que son score
dépasse 0.5.

---

## 4. Les concepts techniques expliqués simplement

### 🧮 a) La "médiane robuste" (règle du montant anormal)
**Le problème :** comment savoir si 4800 € est anormal ? Ça dépend du client.
Pour un client qui dépense 50 €, c'est énorme. Pour un client qui dépense 5000 €,
c'est banal.

**La mauvaise solution :** utiliser la **moyenne**. Problème : si le client a déjà
eu UNE grosse dépense, la moyenne explose et on rate les fraudes suivantes.

**Notre solution :** la **médiane** (la valeur "du milieu"). Elle est *robuste* :
une valeur aberrante ne la déforme pas.
→ On signale si le montant est **≥ 5 × la médiane** du client (avec au moins
3 opérations d'historique pour être fiable).

> Exemple : client habitué à ~48 €. Transaction à 4800 € = 100× la médiane → 🚨

### ✈️ b) Le "voyage impossible" par la PHYSIQUE (notre innovation phare)
**Le problème :** un client paie à Paris à 10h00, puis à Tokyo à 10h40. Fraude
évidente (on ne téléporte pas). Mais comment le détecter automatiquement ?

**La solution naïve (que tout le monde code) :** « deux pays différents en moins
de X heures = suspect ». Problème : combien d'heures ? Paris→Bruxelles en 2h
c'est normal, Paris→Tokyo en 2h c'est impossible. Un seuil fixe se trompe.

**Notre solution :** on calcule la **vraie distance** entre les deux pays
(formule de *Haversine* = distance à vol d'oiseau sur la sphère terrestre), puis
on la divise par la **vitesse maximale d'un avion** (~1000 km/h). Ça donne le
temps **minimum physiquement nécessaire** pour faire le trajet.
→ Si le temps réel écoulé est **inférieur** à ce minimum → voyage impossible → 🚨

> - Paris→Tokyo = 9700 km → minimum ~10h. Écoulé : 40 min → **impossible** 🚨
> - Paris→New York = 7700 km → minimum ~8h. Écoulé : 3 jours → **normal** ✅
>
> **Zéro faux positif géographique, et ça marche pour N'IMPORTE quel couple de pays.**

### ⚡ c) La détection de "rafale" (vélocité)
Un fraudeur qui teste une carte volée enchaîne plein de petites transactions en
quelques secondes. On compte les opérations d'un client dans une **fenêtre de
temps glissante** : 4 transactions ou plus en 2 minutes → comportement de test
de carte → 🚨

### 🛡️ d) La robustesse (ne JAMAIS planter)
Le sujet est clair : *« les données réelles sont imparfaites… votre programme ne
doit jamais planter »*. On gère : montants vides/textuels, dates invalides,
champs `None`, dictionnaires vides, etc. Chaque transaction est analysée dans un
filet de sécurité (`try/except`) : en cas de pépin, on renvoie un verdict neutre
plutôt que de faire crasher tout le lot.

### 💬 e) L'IA "explicable" (explainable AI)
Beaucoup de systèmes anti-fraude sont des "boîtes noires" : ils disent "fraude"
sans dire pourquoi. **Nous, chaque alerte est justifiée en français clair.**
C'est crucial : un agent bancaire doit pouvoir comprendre et défendre la décision.

---

## 5. L'interface (le "waouh" pour le jury)

`app.py` transforme les résultats bruts en **centre de supervision** :
- **4 indicateurs clés** : nb de transactions, nb d'alertes, taux d'alerte,
  montant total à risque ;
- une **carte mondiale** où chaque transaction est un point (rouge = suspecte) ;
- un **graphique** des motifs d'alerte (pourquoi ça alerte) ;
- une **file d'investigation** : chaque alerte sous forme de carte colorée,
  triée par risque, avec sa justification ;
- des **filtres** (par client, par score, alertes uniquement).

Le tout pensé pour un **public non technique** : on raconte une histoire, on ne
montre pas du code.

---

## 6. 🚀 Comment passer au NIVEAU SUPÉRIEUR (surprendre tout le monde)

Voici des pistes concrètes, classées par effort/impact, pour aller au-delà du
hackathon.

### Niveau "Bluffant en démo" (rapide, fort effet visuel)
1. **Mode "simulation temps réel"** — faire défiler les transactions une par une
   avec une animation, comme un vrai flux bancaire en direct. Effet garanti.
2. **Alerte sonore + notification** quand une fraude critique apparaît.
3. **Fiche client 360°** — cliquer sur un client affiche son profil : dépense
   moyenne, pays habituels, historique, niveau de confiance.
4. **Export PDF** d'un rapport d'incident par alerte (pour un usage "métier").

### Niveau "Crédibilité technique" (vrai sérieux d'ingénieur)
5. **Score continu plutôt que par paliers** — combiner plusieurs signaux faibles
   en une probabilité unique (ex. régression logistique), au lieu de règles "tout
   ou rien". Permet de nuancer.
6. **Apprentissage automatique non supervisé** — un *Isolation Forest* ou un
   *autoencoder* qui apprend tout seul ce qu'est une transaction "normale" et
   détecte les anomalies, **sans qu'on lui dise les règles**. C'est le vrai
   "AI" du thème.
7. **Détection par graphe** — modéliser clients/commerçants/cartes comme un
   réseau et repérer les **anneaux de fraude** (plusieurs comptes liés à une même
   carte volée). Très impressionnant.
8. **Horaires inhabituels** — un achat à 3h du matin pour un client qui ne paie
   jamais la nuit est un signal (déjà présent dans les données : T-004 à 03h22 !).
9. **Carte absente + gros montant** (`card_present = false`) — combinaison
   classique de fraude en ligne, à pondérer dans le score.

### Niveau "Produit réel" (vision long terme)
10. **Boucle de feedback** — quand un agent confirme/infirme une alerte, le
    système apprend et ajuste ses seuils. Le modèle s'améliore avec le temps.
11. **API temps réel** (FastAPI) — exposer `detect_fraud` comme un service que
    n'importe quelle app de paiement peut appeler en < 50 ms.
12. **Streaming** (Kafka) — analyser les transactions au fil de l'eau plutôt
    qu'en lot, pour bloquer une fraude **avant** qu'elle ne soit validée.
13. **Conformité & RGPD** — journaliser chaque décision (qui, quoi, pourquoi)
    pour l'audit réglementaire bancaire.
14. **A/B testing des seuils** — mesurer en continu le compromis
    fraudes attrapées vs faux positifs, et optimiser automatiquement.

### La phrase à dire au jury
> « Notre détecteur ne se contente pas de règles : il **personnalise** l'analyse
> par client, **raisonne avec la physique** pour le voyage impossible, **explique**
> chaque décision, et **ne plante jamais**. Et voici comment on le ferait passer
> de prototype à produit bancaire réel… » → puis enchaîner sur les idées 6, 7, 10.

---

## 7. Résumé : pourquoi notre solution est forte

| Critère du sujet | Notre réponse |
|---|---|
| Format de sortie respecté | ✅ 11/11 tests publics |
| Anomalies évidentes | ✅ montant nul/négatif, champs manquants |
| Logique métier | ✅ montant vs historique, fréquence, géographie |
| Éviter les faux positifs | ✅ médiane robuste + voyage impossible physique |
| Ne jamais planter | ✅ testé sur données volontairement cassées |
| Justifications lisibles | ✅ chaque verdict est expliqué en français |
| Interface pour le jury | ✅ tableau de bord complet et visuel |

**En une phrase :** on a transformé un simple "filtre" en un **système de
supervision explicable, personnalisé et robuste** — exactement ce qu'une vraie
banque voudrait.
