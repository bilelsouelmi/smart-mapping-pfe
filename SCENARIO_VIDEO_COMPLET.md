# Scénario vidéo complet — Test de toutes les fonctionnalités
### Chaque champ à remplir est indiqué avec sa valeur exacte — il suffit de suivre dans l'ordre.
### 🖱️ = bouton sans texte, juste une icône (pas d'erreur de manip si tu ne vois pas de mot dessus — c'est normal, dis l'action à l'oral).

---

## ⚙️ Comptes existants (déjà créés, ne pas les recréer)

> ⚠️ La connexion se fait avec l'**email**, pas le username (le username reste juste un identifiant affiché dans l'interface — audit log, "submitted by", etc.)

| Rôle | Username (affiché dans l'UI) | Email (à utiliser pour se connecter) | Mot de passe |
|---|---|---|---|
| Utilisateur | `testuser1` | `testuser1@vermeg.com` | `TestPass123!` |
| Officier conformité #1 | `officer1` | `officer1@vermeg.com` | `TestPass123!` |
| Officier conformité #2 | `officer2` | `officer2@vermeg.com` | `TestPass123!` |
| Administrateur | `temp_approver` | `admin@vermeg.com` | `TestPass123!` |

## 📁 Fichiers de test
> 📍 Situés dans `C:\Users\pc\Desktop\test demo\` (pas dans le dossier du projet).

`fulltest_1_success.txt` · `fulltest_2_badvalidation.txt` · `fulltest_2_fixed.txt` · `fulltest_3_sanctions.txt` · `fulltest_4_pep.txt` · `fulltest_5_large_amount.txt` · `fulltest_6_critical_amount.txt` · `fulltest_batch_A.txt` · `fulltest_batch_B_duplicate.txt` · `fulltest_batch_C_pep.txt` · `fulltest_batch_D_invalid.txt` · `fulltest_rabbitmq_kafka.txt`

## 🔌 Services externes (déjà lancés via Docker)
| Service | URL | Identifiants |
|---|---|---|
| RabbitMQ Management UI | http://localhost:15672 | `admin` / `admin123` |
| Kafka UI | http://localhost:8090 | — |

## 🗺️ Sommaire

| # | Chapitre | Durée |
|---|---|---|
| 1 | [Authentification & comptes](#chapitre-1--authentification--comptes-4-min) | ~4 min |
| 2 | [Description de message](#chapitre-2--description-de-message-5-min) | ~5 min |
| 3 | [Mapping & Formules](#chapitre-3--mapping--formules-3-min) | ~3 min |
| 4 | [Transformation](#chapitre-4--transformation--cas-nominal-et-blocages-techniques-4-min) | ~4 min |
| 5 | [Validation & correction](#chapitre-5--validation--file-de-correction-4-min) | ~4 min |
| 6 | [Watchlist + sanctions](#chapitre-6--gouvernance-watchlist--blocage-sanctions-4-min) | ~4 min |
| 7 | [PEP & séparation des rôles](#chapitre-7--pep--mise-en-attente-et-séparation-des-rôles-4-min) | ~4 min |
| 8 | [Montant élevé](#chapitre-8--montant-élevé--approbation-simple-et-critique-4-min) | ~4 min |
| 9 | [Retrait Watchlist](#chapitre-9--retrait-dune-entrée-watchlist-2-min) | ~2 min |
| 10 | [Traitement par lot](#chapitre-10--traitement-par-lot-3-min) | ~3 min |
| 11 | [Pipeline, Transport & Retry](#chapitre-11--pipeline-transport--retry-de-livraison-8-min) | ~8 min |
| 12 | [Notifications](#chapitre-12--notifications-2-min) | ~2 min |
| 13 | [Reporting réglementaire](#chapitre-13--reporting-réglementaire-4-min) | ~4 min |
| 14 | [Dashboard SLA](#chapitre-14--dashboard-sla-3-min) | ~3 min |
| 15 | [Administration RAG](#chapitre-15--administration-rag-2-min) | ~2 min |
| 16 | [Variables métier](#chapitre-16--variables-métier-récapitulatif-1-min) | ~1 min |

---

## CHAPITRE 1 — Authentification & comptes *(≈4 min)*

**1.1 — Créer un compte (page "Register")**
| Champ | Valeur à saisir |
|---|---|
| Full Name | `Test Candidat` |
| Username | `demo.candidat` |
| Email | `demo.candidat@vermeg.com` |
| Password | `DemoTest123!` |

→ Cliquer **Register**. Le compte est créé mais inactif.

**1.2 — Contrôles de saisie sur l'inscription** *(à montrer avant de soumettre le vrai compte, ou sur un second essai)*

| Test | Action | Résultat attendu |
|---|---|---|
| Champ obligatoire vide | Laisser "Username" vide → cliquer Register | Bulle native du navigateur : "Please fill out this field" |
| Email mal formé | Taper `pasunemail` dans Email → soumettre | Bulle native : "Please include an '@' in the email address" |
| Mot de passe trop court | Taper `abc123` (6 caractères) dans Password → soumettre | Bulle native : "Please lengthen this text to 8 characters or more" |
| Compte déjà existant | Refaire "Register" avec Username `testuser1` (déjà pris) | Message serveur : **"Email or username already registered"** |

→ Une fois ces essais montrés, soumettre le vrai formulaire (valeurs de 1.1) pour continuer le scénario.

**1.3 — Connexion avec un compte en attente d'approbation** — essayer : Email `demo.candidat@vermeg.com` / Password `DemoTest123!`
→ Refusé, mais avec un encart dédié (pas juste une erreur générique) : icône horloge orange, titre **"Account pending approval"**, texte : *"Your account has been created successfully but requires administrator approval before you can log in. Please contact your administrator."*

**1.4 — Connexion admin**
| Champ | Valeur |
|---|---|
| Email | `admin@vermeg.com` |
| Password | `TestPass123!` |

→ **User Management** → onglet **"Pending Approval (N)"** → trouver `demo.candidat` → cliquer **Approve**.

**1.5** — Se déconnecter → se reconnecter avec Email `demo.candidat@vermeg.com` / Password `DemoTest123!` → succès cette fois.

**1.6 — Changer le mot de passe** (toujours sur `demo.candidat`)
| Champ | Valeur |
|---|---|
| Ancien mot de passe | `DemoTest123!` |
| Nouveau mot de passe | `DemoTest456!` |

→ Se déconnecter → se reconnecter avec `DemoTest456!` → succès.

**1.7 — Contrôles d'erreur sur la connexion**

| Test | Action | Résultat attendu |
|---|---|---|
| Mauvais mot de passe | Email `demo.candidat@vermeg.com` / Password `MauvaisMdp1!` | **"Incorrect email or password"** |
| Email inexistant | Email `nexistepas@vermeg.com` / Password `TestPass123!` | **Exactement le même message** : "Incorrect email or password" |

→ Point à souligner à l'oral : le message est **volontairement identique** dans les deux cas — ne jamais révéler si c'est l'email ou le mot de passe qui est faux, pour empêcher un attaquant de deviner quels comptes existent (protection contre l'énumération de comptes).

**1.8** — Reconnexion `temp_approver` → **User Management** → trouver `demo.candidat` → cliquer **Delete** → un second bouton **Confirm** apparaît à la place → cliquer **Confirm**.

---

## CHAPITRE 2 — Description de message *(≈5 min)*

**2.1 — Connexion**
| Champ | Valeur |
|---|---|
| Email | `testuser1@vermeg.com` |
| Password | `TestPass123!` |

**2.2** — **Message Desc** → bouton d'upload → sélectionner `fulltest_1_success.txt`.

**2.3** — Cliquer **Generate MD** → attendre la détection automatique (type MT103). Ce même clic importe aussi directement les éléments depuis la structure SWIFT (blocs MT) — il n'y a pas de bouton séparé pour ça, tout se fait en un seul clic.

**2.4 — Test d'un fichier invalide** : uploader n'importe quel fichier non-SWIFT (ex. une image ou un `.docx`) → montrer le message d'erreur.

**2.5 — Ajouter un élément manuellement** (bouton "Add Element" sur la MD générée)
| Champ | Valeur |
|---|---|
| Value Type | `STRING` |
| Name | `TestField` |
| Min Length | `1` |
| Max Length | `35` |
| Min Occurs | `1` |
| Field Tag | `:99:` |
| Example | `TESTVALUE` |

→ Enregistrer. Puis cliquer sur cet élément → modifier Max Length en `50` → enregistrer. Puis le supprimer (bouton "Delete").

**2.6** — Toujours connecté `testuser1` : sur la MD qu'il vient de créer, remarquer qu'**aucun bouton Approve n'apparaît** — seul **Reject** est visible. C'est la preuve visuelle du maker-checker : un non-admin ne peut même pas tenter d'approuver sa propre proposition, le bouton n'existe simplement pas pour lui.

**2.7** — Connexion `temp_approver` → ouvrir la même MD → cliquer **Approve**.

**2.8 — Demande d'accès** : reconnexion `testuser1` → rouvrir **la même MD** (désormais approuvée) → un bouton **Request Access** apparaît à la place d'Approve/Reject — même le propriétaire d'origine doit demander un accès admin pour la modifier une fois qu'elle est approuvée.
| Champ | Valeur |
|---|---|
| Reason | `Besoin de corriger un champ pour la démo` |

**2.9** — Connexion `temp_approver` → **Access Requests** → trouver la demande → cliquer **Grant** → une boîte de confirmation apparaît (résumé de la demande) → confirmer.

---

## CHAPITRE 3 — Mapping & Formules *(≈3 min)*

> ⚠️ Ce mapping n'existe pas encore à ce stade (base propre) — il faut le créer, contrairement à ce qu'un scénario plus court pourrait laisser croire.

**3.1 — Créer le mapping** — toujours `testuser1` → **Mapping** → bouton **New**
| Champ | Valeur |
|---|---|
| Name | `MT103 → pacs.008 mapping` |
| Message Description | (sélectionner `fulltest_1_success.txt`, approuvée au Chapitre 2) |

→ Source et Target se remplissent automatiquement (`MT103` → `pacs.008.001.08`). Le champ **Status** est grisé pour ce compte (non-admin) — le mapping est créé en `draft`, pas encore utilisable pour un Transform : c'est le même principe maker-checker que pour les Message Descriptions.

**3.2 — Activer le mapping** — connexion `temp_approver` → **Mapping** → ouvrir "MT103 → pacs.008 mapping" (badge de statut orange/gris "draft") → cliquer **Activate** → badge passe à "active" (vert).

**3.3** — Toujours sur ce mapping → montrer les éléments, plusieurs marqués "PENDING".

**3.4** — Bouton **Generate Elements** en haut de la page → montrer le remplissage automatique en masse par RAG : les éléments PENDING passent à "MAPPED".

---

## CHAPITRE 4 — Transformation : cas nominal et blocages techniques *(≈4 min)*

**4.1** — `testuser1` → page de transformation du mapping MT103 → pacs.008 → uploader `fulltest_1_success.txt` → **Transform** → succès, XML généré.

**4.2** — Re-uploader **le même fichier** `fulltest_1_success.txt` une seconde fois → **Transform** → blocage doublon (référence `FULLTEST001` déjà traitée).

**4.3** — **Outputs** → vérifier que les fichiers déjà téléchargés apparaissent bien dans la liste.

---

## CHAPITRE 5 — Validation & file de correction *(≈4 min)*

**5.1** — `testuser1` → **Validate** → uploader `fulltest_1_success.txt` → **Validate** → tous les champs "passed".

**5.2** — Sur le mapping MT103 → pacs.008 → uploader `fulltest_2_badvalidation.txt` → **Transform** (pas Validate) → échec : champ `:71A:` invalide, message d'erreur détaillé affiché.

**5.3** — **Pending Transactions** → section **Failed Validations** → montrer l'entrée créée automatiquement avec le détail des erreurs.

**5.4** — Uploader `fulltest_2_fixed.txt` (même type, référence différente `FULLTEST003`) → **Transform** → succès.

**5.5** — Retour sur **Failed Validations** → montrer l'entrée précédente passée automatiquement à `resolved`.

---

## CHAPITRE 6 — Gouvernance Watchlist + blocage sanctions *(≈4 min)*

**6.1 — Connexion**
| Champ | Valeur |
|---|---|
| Email | `officer1@vermeg.com` |
| Password | `TestPass123!` |

**6.2** — **Watchlist** → bouton **Propose Entry**
| Champ | Valeur |
|---|---|
| Name | `EASTBRIDGE TRADING SA` |
| List | `SANCTIONS` |
| Notes | `Entité de démonstration — sanctions` |

→ Soumettre. Statut affiché : `pending_add`.

**6.3** — Toujours connecté `officer1` : sur cette même entrée, aucun bouton d'action n'apparaît — juste le texte *"Awaiting another officer's review"*. C'est le contrôle dual : le proposant ne peut même pas tenter d'approuver sa propre proposition.

**6.4 — Connexion**
| Champ | Valeur |
|---|---|
| Email | `officer2@vermeg.com` |
| Password | `TestPass123!` |

→ **Watchlist** → trouver l'entrée `EASTBRIDGE TRADING SA` → cliquer 🖱️ l'icône ✅ (check, sans texte) → statut passe à `active`.

**6.5** — Connexion `testuser1` → transformer `fulltest_3_sanctions.txt` → blocage immédiat (403), message affiché à l'écran.

**6.6** — Connexion `temp_approver` → **Audit Log** → montrer l'entrée `sanctions_block` la plus récente (en haut de la liste, triée par date).

**6.7** — Reconnexion `testuser1` → tenter d'accéder directement à l'URL de **Audit Log** → redirection silencieuse vers le Dashboard, sans message d'erreur affiché (à mentionner à l'oral : la page est simplement inaccessible pour ce rôle).

---

## CHAPITRE 7 — PEP : mise en attente et séparation des rôles *(≈4 min)*

**7.1 — Connexion**
| Champ | Valeur |
|---|---|
| Email | `officer1@vermeg.com` |
| Password | `TestPass123!` |

→ **Watchlist** → **Propose Entry**
| Champ | Valeur |
|---|---|
| Name | `MARC LEFEVRE` |
| List | `PEP` |
| Notes | `Personne politiquement exposée — démonstration` |

**7.2** — Connexion `officer2` → **Watchlist** → cliquer 🖱️ l'icône ✅ sur `MARC LEFEVRE` pour confirmer.

**7.3** — Connexion `testuser1` → transformer `fulltest_4_pep.txt` → statut "held for approval".

**7.4** — **Pending Transactions** → montrer l'entrée, raison affichée : `PEP match: ... "MARC LEFEVRE"`.

**7.5** — Connexion `officer1` → **Pending Transactions** → cliquer 🖱️ l'icône ✅ pour approuver → succès → cliquer 🖱️ l'icône de téléchargement.

→ Point à souligner à l'oral (pas la peine de le montrer en cliquant) : un compte admin non-officier ne voit même pas ce hold PEP dans sa liste — il est filtré par rôle côté serveur —, et le soumetteur d'origine (`testuser1`) ne voit aucun bouton d'action sur ses propres demandes, juste le texte *"Awaiting compliance officer(s)"*.

---

## CHAPITRE 8 — Montant élevé : approbation simple et critique *(≈4 min)*

**8.1** — `testuser1` → transformer `fulltest_5_large_amount.txt` (60 000 €) → encart **"🔒 Held for approval"** avec le message *"This transaction (60,000.00 EUR) exceeds the approval threshold and requires 1 admin approval(s) before the file is released..."*.

**8.2** — Connexion `temp_approver` → **Pending Transactions** → cliquer 🖱️ l'icône ✅ → statut "approved" immédiatement (quorum de 1 atteint), les icônes d'action disparaissent de cette ligne.

**8.3** — Connexion `testuser1` → transformer `fulltest_6_critical_amount.txt` (150 000 €) → hold, message indiquant 2 approbations requises.

**8.4** — Connexion `temp_approver` → approuver (1/2) → statut reste "pending", raison affichée : *"awaiting 1 more approval"*.

**8.5** — Connexion `officer2` → **Pending Transactions** → approuver (2/2) → statut "approved".

**8.6** — Point à souligner à l'oral (rien à cliquer) : une fois "approved", les icônes d'action disparaissent de la ligne — impossible d'approuver deux fois la même transaction depuis l'interface.

**8.7 — Variables métier** : `temp_approver` → **Business Variables** → trouver `LARGE_AMOUNT_THRESHOLD` → montrer la valeur actuelle (`20000`) → optionnel : la modifier temporairement en `30000` puis la remettre à `20000`.

---

## CHAPITRE 9 — Retrait d'une entrée Watchlist *(≈2 min)*

**9.1** — Connexion `officer1` → **Watchlist** → trouver `EASTBRIDGE TRADING SA` → cliquer 🖱️ l'icône ⊖ (title "Request removal").

**9.2** — Montrer le statut `pending_remove` — l'entrée reste listée comme active pour l'instant.

**9.3** — Connexion `officer2` → **Watchlist** → cliquer 🖱️ l'icône ✅ pour confirmer le retrait → l'entrée n'est plus active.

**9.4** — Connexion `testuser1` → transformer à nouveau un fichier avec `EASTBRIDGE TRADING SA` comme donneur d'ordre (réutiliser une copie de `fulltest_3_sanctions.txt` avec une nouvelle référence, ex. `:20:FULLTEST008`) → succès cette fois, plus bloqué.

---

## CHAPITRE 10 — Traitement par lot *(≈3 min)*

**10.1** — `testuser1` → **Batch Processing** → menu déroulant **Mapping** → sélectionner `MT103 → pacs.008 mapping`.

**10.2** — Glisser-déposer ensemble : `fulltest_batch_A.txt`, `fulltest_batch_B_duplicate.txt`, `fulltest_batch_C_pep.txt`, `fulltest_batch_D_invalid.txt`.

**10.3** — Cliquer **Run Batch (4 file(s))** → montrer le résumé : Total, 1 Success, 1 Held (PEP), 2 Failed (doublon + validation).

**10.4** — Cliquer le bouton de téléchargement sur la ligne "Success".

**10.5** — Cliquer **Clear** → montrer la réinitialisation de la liste.

---

## CHAPITRE 11 — Pipeline, Transport & Retry de livraison *(≈8 min)*

**11.1 — Créer un Config IN** (**Configuration** → onglet **Config IN** → bouton **New Config**)
| Champ | Valeur |
|---|---|
| Name | `Demo FILE Input` |
| Transport Type | `FILE` |
| Input Folder Path | `/app/fulltest_pipeline_in` |
| File Pattern | `*.txt` |

→ Note : il n'y a pas de champ "Direction" à remplir — c'est l'onglet actif (Config IN / Config OUT) qui le détermine, avant même d'ouvrir "New Config".

**11.2 — Créer un Config OUT** (basculer sur l'onglet **Config OUT** → **New Config**)
| Champ | Valeur |
|---|---|
| Name | `Demo REST Output` |
| Transport Type | `REST` |
| URL | `http://localhost:1/receive` |
| Method | `POST` |
| Authentication | `None` |

**11.3** — Sur ce Config OUT → cliquer 🖱️ l'icône Wifi (title "Test") → montrer l'échec (port fermé).

**11.4 — Créer le pipeline** (**Consommation** → bouton **Nouveau Pipeline**)
| Champ | Valeur |
|---|---|
| Pipeline Name | `Demo Pipeline Complet` |
| ① Config IN | `Demo FILE Input` |
| ② Mapping | `MT103 → pacs.008 mapping` |
| ③ Config OUT | `Demo REST Output` |

**11.5** — Cliquer **Start** sur ce pipeline → montrer l'échec à l'étape "Config OUT" (le fichier source n'est pas déplacé).

**11.6** — **Pending Delivery Retries** → montrer l'entrée créée automatiquement, avec le message d'erreur.

**11.7 — Corriger le Config OUT** : rouvrir `Demo REST Output` → changer l'URL en `http://localhost:8000/api/ws-receiver/receive` → enregistrer.

**11.8** — Retour sur **Pending Delivery Retries** → cliquer **Retry** sur l'entrée → statut "delivered".

**11.9** — Relancer le pipeline une seconde fois pour créer une nouvelle entrée en échec (remettre temporairement une mauvaise URL, relancer, puis remettre la bonne), puis cliquer **Abandon** dessus → montrer qu'elle disparaît du filtre "pending".

---

### RabbitMQ & Kafka *(≈3 min — testé en direct, fonctionne de bout en bout)*

> Les deux services tournent déjà (RabbitMQ + Kafka + Zookeeper), pas besoin de les démarrer.

**11.10 — Créer un Config IN RabbitMQ** (**Configuration** → onglet **Config IN** → **New Config**)
| Champ | Valeur |
|---|---|
| Name | `RabbitMQ Input` |
| Transport Type | `RabbitMQ` |
| Host | `rabbitmq` |
| Port | `5672` |
| Username | `admin` |
| Password | `admin123` |
| Queue Name | `swift.messages.in` |
| Virtual Host | `/` |

**11.11 — Créer un Config OUT Kafka** (onglet **Config OUT** → **New Config**)
| Champ | Valeur |
|---|---|
| Name | `Kafka Output` |
| Transport Type | `Apache Kafka` |
| Bootstrap Servers | `kafka:9092` |
| Topic | `swift.messages.out` |
| Group ID | (laisser la valeur par défaut) |
| Security Protocol | `PLAINTEXT` |

**11.12 — Créer le pipeline** (**Consommation** → **Nouveau Pipeline**)
| Champ | Valeur |
|---|---|
| Pipeline Name | `Pipeline RabbitMQ vers Kafka` |
| ① Config IN | `RabbitMQ Input` |
| ② Mapping | `MT103 → pacs.008 mapping` |
| ③ Config OUT | `Kafka Output` |

**11.13 — Publier un message de test dans RabbitMQ** — ouvrir un nouvel onglet → `http://localhost:15672` → login `admin` / `admin123` :
1. Onglet **Queues and Streams** → **Add a new queue** → Name `swift.messages.in`, Durability `Durable` → **Add queue** *(si elle n'existe pas déjà).*
2. Cliquer sur la queue `swift.messages.in` → section **Publish message** → coller le contenu de `fulltest_rabbitmq_kafka.txt` dans **Payload** → **Publish message**.

**11.14** — Retour sur la plateforme → **Consommation** → cliquer **Start** sur "Pipeline RabbitMQ vers Kafka" → montrer les 3 étapes réussies : Config IN (message consommé), Mapping (transformé → pacs.008.001.08), Config OUT (publié sur Kafka).

**11.15 — Vérifier la réception côté Kafka** — nouvel onglet → `http://localhost:8090` (Kafka UI) → **Topics** → `swift.messages.out` → **Messages** → montrer le XML pacs.008 reçu, avec `MsgId = RMQTEST001`.

---

## CHAPITRE 12 — Notifications *(≈2 min)*

**12.1** — `testuser1` → cliquer l'icône 🔔 de notifications → montrer les notifications reçues (approbations/rejets des chapitres précédents).

**12.2** — Cliquer une notification → montrer qu'elle passe à "lue".

**12.3** — Cliquer 🖱️ l'icône ✕ sur une notification pour la supprimer individuellement, puis cliquer **Clear all**.

---

## CHAPITRE 13 — Reporting réglementaire *(≈4 min)*

**13.1** — Connexion `officer1` ou `temp_approver` → **Regulatory Reports**.

**13.2** — Laisser les filtres par défaut (fenêtre glissante de 30 jours, pas seulement "aujourd'hui") → montrer le total et la répartition par catégorie.

**13.3 — Filtrer par date**
| Champ | Valeur |
|---|---|
| Start date & time | (aujourd'hui, 00:00) |
| End date & time | (maintenant) |

**13.4** — Cliquer sur la carte catégorie **"Sanctions & PEP Screening"** → montrer que les autres catégories passent à 0.

**13.5** — Cliquer **Export CSV** → ouvrir le fichier téléchargé, montrer le contenu.

**13.6** — Reconnexion `testuser1` → tenter d'accéder à **Regulatory Reports** → redirection silencieuse vers le Dashboard, sans message d'erreur (même comportement qu'au 6.7).

---

## CHAPITRE 14 — Dashboard SLA *(≈3 min)*

**14.1** — Rester connecté (`officer1` ou `temp_approver`) → **SLA Dashboard**.

**14.2** — Montrer "Transforms Completed" et "Holds Created".

**14.3** — Montrer "Avg Turnaround — Admin Holds" vs "Avg Turnaround — PEP Holds" (comparer les deux valeurs, issues des chapitres 7 et 8).

**14.4** — Montrer "Outright Blocks/Flags" (sanctions, doublons).

**14.5** — Montrer le graphique "Daily Activity".

---

## CHAPITRE 15 — Administration RAG *(≈2 min)*

> ⚠️ **Important** : ces routes existent côté serveur (`/api/rag-admin/...`) mais n'ont **aucune page dans l'interface** — il n'y a rien à cliquer. Deux options :
> - **Option A (recommandée pour la vidéo)** : sauter ce chapitre entièrement et le mentionner uniquement à l'oral ("le module RAG dispose aussi d'endpoints d'administration — statut, réinitialisation — exposés en API, sans interface dédiée pour l'instant").
> - **Option B** : montrer l'appel via le navigateur (onglet Réseau des outils développeur) ou un outil comme Postman, en appelant `GET /api/rag-admin/status` avec le token admin, pour prouver que la fonctionnalité existe même sans UI.

**15.1 (Option B uniquement)** — Ouvrir un nouvel onglet → utiliser Postman ou la console du navigateur pour appeler `GET http://localhost:8000/api/rag-admin/status` avec l'en-tête `Authorization: Bearer <token admin>` → montrer la réponse JSON (nombre de points indexés, statut Qdrant).

---

## CHAPITRE 16 — Variables métier (récapitulatif) *(≈1 min)*

**16.1** — `testuser1` → **Business Variables** → montrer la liste en lecture seule.

**16.2** — Aucun bouton d'édition n'apparaît pour ce rôle — la colonne d'actions est simplement absente, pas un bouton qui refuserait au clic.

**16.3** — Connexion `temp_approver` → modifier une valeur (ex. `PEP_SCREENING_ENABLED`) → montrer que le changement est pris en compte.

---

## Durée totale estimée : ~58 minutes

Si trop long pour une seule vidéo : découpe en 2-3 vidéos par blocs (Chapitres 1-5 / 6-11 / 12-16) — chaque chapitre est autonome.

## 🧹 Après l'enregistrement
Préviens-moi une fois terminé — je nettoierai les comptes de test, les entrées watchlist, les pipelines et fichiers créés pendant le tournage.
