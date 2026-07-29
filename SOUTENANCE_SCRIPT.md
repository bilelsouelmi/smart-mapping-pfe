# Script de démonstration — Soutenance technique
### Smart Mapping Platform — Durée cible : ~18 minutes

---

## ⚙️ PRÉPARATION (à faire AVANT d'enregistrer, pas filmé)

### 1. Comptes à utiliser

> ⚠️ **La connexion se fait avec l'email**, pas le username — le username reste juste un identifiant affiché dans l'interface (audit log, "submitted by", etc.). Partout ci-dessous où c'est écrit "Connexion `X`", saisir l'email correspondant dans le champ Email du formulaire de connexion.

| Rôle | Username (affiché dans l'UI) | Email (à saisir pour se connecter) | Mot de passe |
|---|---|---|---|
| Utilisateur (soumission) | `testuser1` | `testuser1@vermeg.com` | `TestPass123!` |
| Officier conformité #1 (propose) | `officer1` | `officer1@vermeg.com` | `TestPass123!` |
| Officier conformité #2 (confirme/approuve) | `officer2` | `officer2@vermeg.com` | `TestPass123!` |
| Administrateur (approuve montant élevé) | `temp_approver` | `admin@vermeg.com` | `TestPass123!` |

### 2. Fichiers de test (déjà créés dans le dossier du projet)
- `demo_1_success.txt` — transaction normale (3 000 €)
- `demo_2_sanctions.txt` — ordonnateur "NORTHSTAR SHELL HOLDINGS" (2 500 €)
- `demo_3_pep.txt` — ordonnateur "ALICE JONES", déjà enregistrée comme PEP (2 800 €)
- `demo_4_large_amount.txt` — transaction de 75 000 € (au-dessus du seuil de 20 000 €)

### 3. Vérifications rapides avant de filmer
- Le mapping **"MT103 → pacs.008 mapping"** existe et est approuvé (déjà en place).
- La liste de surveillance ne contient **pas encore** "NORTHSTAR SHELL HOLDINGS" (on l'ajoute en direct pendant la démo).
- Navigateur ouvert sur la page de connexion, zoom à 100%, notifications du système désactivées.

---

## 🎬 SECTION 1 — Introduction (≈1 min)

**Action à l'écran** : Rester sur la page de connexion / dashboard vide.

**🎤 Speech :**
> Bonjour. Je vais vous présenter Smart Mapping Platform, une plateforme que j'ai développée pour automatiser la conversion entre les messages financiers SWIFT MT — le standard historique de la messagerie interbancaire — et le format ISO 20022, qui est le nouveau standard international vers lequel toutes les banques migrent actuellement.
>
> Mais au-delà de la simple conversion technique, la plateforme intègre l'ensemble des contrôles qu'une vraie banque doit appliquer : détection des doublons, filtrage sanctions et personnes politiquement exposées, seuils de validation par montant, et une piste d'audit complète. Je vais vous montrer un parcours complet, de bout en bout, avec de vraies données de test.

---

## 🎬 SECTION 2 — Description de message & Mapping assisté par IA (≈3 min)

**Action à l'écran** :
1. Se connecter en tant que `testuser1`.
2. Aller sur **Message Desc** → montrer la description MT103 déjà approuvée (badge vert "Approved").
3. Aller sur **Mapping** → ouvrir le mapping **"MT103 → pacs.008 mapping"** → montrer la liste des éléments mappés.
4. Cliquer sur un élément qui a une formule (ex. transformation de date ou de nom) → montrer le champ indiquant qu'elle a été suggérée par RAG (`suggestion_source`).

**🎤 Speech :**
> La première étape du workflow est la description de message : la plateforme analyse un fichier échantillon, détecte automatiquement le standard — ici MT103 — et génère la structure des champs. Cette génération passe par un contrôle à double validation : la personne qui génère la description n'est jamais celle qui peut l'approuver, exactement comme dans un vrai processus bancaire de contrôle interne.
>
> Une fois approuvée, cette description sert de base pour créer un mapping vers le format cible, ici pacs.008. Ce qui rend cette étape intelligente, c'est l'assistance par RAG — Retrieval-Augmented Generation : la plateforme interroge une base de connaissances vectorielle pour suggérer automatiquement les règles de transformation les plus probables, en s'appuyant sur des mappings similaires déjà validés. L'utilisateur garde toujours la main : il peut accepter, modifier, ou rejeter chaque suggestion.

---

## 🎬 SECTION 3 — Transformation réussie (≈2 min)

**Action à l'écran** :
1. Toujours connecté en `testuser1`, aller sur la page de transformation (mapping MT103 → pacs.008).
2. Uploader `demo_1_success.txt`.
3. Lancer la transformation → montrer le fichier XML pacs.008 généré et son contenu.

**🎤 Speech :**
> Voici un cas simple : un virement de 3000 euros, sans anomalie. Le fichier passe par plusieurs contrôles avant transformation — vérification qu'une description de message approuvée existe, vérification des règles de validation SWIFT, puis application du mapping. La transformation aboutit directement : le fichier XML ISO 20022 est généré et disponible immédiatement au téléchargement.
>
> C'est le chemin nominal. Maintenant, je vais vous montrer ce qui se passe quand une transaction déclenche un contrôle de conformité — c'est vraiment le cœur de ce qui différencie cette plateforme d'un simple outil de conversion.

---

## 🎬 SECTION 4 — Gouvernance de la liste de surveillance + Blocage sanctions (≈3 min)

**Action à l'écran** :
1. Se déconnecter, se connecter en tant que `officer1`.
2. Aller sur **Watchlist** → "Add Entity" → Nom : `NORTHSTAR SHELL HOLDINGS`, Liste : `SANCTIONS` → soumettre. Montrer le statut `pending_add`.
3. Se déconnecter, se connecter en tant que `officer2`.
4. Aller sur **Watchlist** → trouver l'entrée en attente → confirmer. Montrer qu'elle passe à `active`.
5. Se déconnecter, se connecter en tant que `testuser1`.
6. Uploader `demo_2_sanctions.txt` → lancer la transformation.
7. Montrer le blocage immédiat (message d'erreur clair, HTTP 403).
8. Aller sur **Audit Log** (si connecté en admin) ou mentionner l'entrée `sanctions_block` — sinon se reconnecter rapidement en admin pour montrer le journal.

**🎤 Speech :**
> Avant de déclencher le contrôle, je vous montre comment une entité est ajoutée à la liste de surveillance : ce n'est jamais une action unilatérale. Un premier officier de conformité propose l'ajout, et un second officier — obligatoirement différent — doit confirmer avant que l'entrée devienne active. C'est le principe du contrôle à quatre yeux, "maker-checker", pour éviter qu'une seule personne puisse manipuler seule la liste des entités sanctionnées.
>
> Maintenant que "Northstar Shell Holdings" est active sur la liste sanctions, je soumets un virement dont le donneur d'ordre porte exactement ce nom. Le résultat est immédiat : la transformation est bloquée avant même d'être exécutée, avec un message explicite. C'est un contrôle bloquant, pas une simple alerte — comparable à ce qu'impose la réglementation anti-blanchiment. Et cette action est tracée dans le journal d'audit, horodatée et non modifiable, pour la conformité réglementaire.

---

## 🎬 SECTION 5 — PEP : mise en attente pour révision de conformité (≈3 min)

**Action à l'écran** :
1. Toujours en `testuser1`, uploader `demo_3_pep.txt` → lancer la transformation.
2. Montrer la réponse "held for approval" (statut 202, pas un blocage).
3. Aller sur **Pending Transactions** → montrer l'entrée avec la raison "PEP match".
4. Se déconnecter, se connecter en `temp_approver` (administrateur).
5. Aller sur **Pending Transactions** → essayer d'approuver → montrer le refus / l'absence du bouton d'action.
6. Se déconnecter, se connecter en `officer1`.
7. Approuver la transaction → montrer le statut passé à "Approved" → télécharger le fichier.

**🎤 Speech :**
> Ce deuxième scénario illustre une nuance importante : une personne politiquement exposée n'est pas automatiquement bloquée comme pour les sanctions — la réglementation demande une revue renforcée, pas un rejet automatique. Le fichier est donc transformé et mis en attente, pas bloqué.
>
> Vous voyez que la transaction apparaît maintenant dans la file d'attente, avec la raison précise : correspondance PEP sur le donneur d'ordre. Je me connecte maintenant en tant qu'administrateur pour montrer un point clé de la conception : un administrateur classique ne peut PAS lever cette attente — seul un officier de conformité en a le droit, parce que la revue PEP est une responsabilité de conformité, pas une responsabilité d'administration système. C'est une séparation stricte des rôles, appliquée aussi bien côté interface que côté serveur.
>
> Je me reconnecte donc en tant qu'officier de conformité, qui peut approuver — et à ce moment seulement, le fichier devient téléchargeable.

---

## 🎬 SECTION 6 — Montant élevé : approbation multi-niveaux (≈2 min)

**Action à l'écran** :
1. En tant que `testuser1`, uploader `demo_4_large_amount.txt` → transformer.
2. Montrer la mise en attente (motif : dépassement de seuil).
3. Se connecter en `temp_approver` → approuver.
4. (Optionnel, si le temps le permet) Montrer la page **Business Variables** : le seuil `LARGE_AMOUNT_THRESHOLD` configurable à 20 000 €.

**🎤 Speech :**
> Troisième contrôle : un virement de 75 000 euros dépasse le seuil configuré — actuellement fixé à 20 000 euros, mais entièrement paramétrable par un administrateur sans toucher au code, via la page de configuration des variables métier. Au-delà d'un second seuil, critique, la plateforme peut même exiger deux approbations distinctes au lieu d'une, avec la même règle : la personne qui soumet la transaction ne peut jamais être elle-même l'approbateur, même si elle est administrateur.

---

## 🎬 SECTION 7 — Reporting réglementaire & tableau de bord SLA (≈3 min)

**Action à l'écran** :
1. Rester connecté en tant qu'officier ou admin.
2. Aller sur **Regulatory Reports** → montrer les catégories (Sanctions & PEP, Large-Amount Approval, etc.) → filtrer par catégorie "Sanctions & PEP Screening" → cliquer "Export CSV".
3. Aller sur **SLA Dashboard** → montrer les indicateurs (volume de transformations, temps moyen de traitement des mises en attente, graphique d'activité journalière).

**🎤 Speech :**
> Tout ce que nous venons de déclencher — le blocage sanctions, la mise en attente PEP, l'approbation du montant élevé — alimente automatiquement deux vues de pilotage. Le rapport réglementaire reprend l'ensemble du journal d'audit et le restructure par catégorie, exportable en CSV pour être transmis à un régulateur ou archivé. Le tableau de bord SLA, lui, mesure la performance opérationnelle : combien de temps une mise en attente met-elle à être résolue, par type de contrôle, quel est le taux de blocage, le volume quotidien. Aucune de ces deux vues ne crée de nouvelles données : elles ne font que réinterpréter la même piste d'audit déjà fiable, ce qui garantit qu'il n'y a qu'une seule source de vérité dans tout le système.

---

## 🎬 SECTION 8 — Conclusion (≈1 min)

**Action à l'écran** : Retour au dashboard général.

**🎤 Speech :**
> Pour résumer, cette plateforme couvre l'ensemble du cycle de vie d'une transformation SWIFT vers ISO 20022 : génération assistée par IA de la structure des messages, mapping intelligent avec suggestions RAG, et surtout un ensemble de contrôles de conformité bancaire réels — sanctions, PEP, seuils de montant — avec séparation stricte des rôles et double validation partout où c'est requis.
>
> Je n'ai pas eu le temps de montrer aujourd'hui deux autres fonctionnalités : le traitement par lot, qui permet de soumettre plusieurs fichiers en une seule fois avec un rapport par fichier, et la file de re-livraison automatique, qui garantit qu'une transformation réussie n'est jamais perdue même si le système de destination — Kafka, RabbitMQ, ou un service REST — est temporairement indisponible. Je reste bien sûr disponible pour les détailler si vous le souhaitez.
>
> Merci de votre attention, je suis à votre disposition pour vos questions.

---

## 📋 Checklist finale avant enregistrement
- [ ] Les 4 comptes se connectent bien
- [ ] Les 4 fichiers de test sont accessibles facilement (bureau ou dossier dédié)
- [ ] "NORTHSTAR SHELL HOLDINGS" n'est PAS déjà dans la watchlist (sinon la section 4 perd son intérêt pédagogique)
- [ ] Le mapping MT103 → pacs.008 est bien approuvé et actif
- [ ] Micro testé, silence ambiant, notifications désactivées
