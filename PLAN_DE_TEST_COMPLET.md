# Plan de test complet — Smart Mapping Platform

Document de test exhaustif couvrant l'ensemble des fonctionnalités de la plateforme.
Chaque cas de test précise : objectif, pré-requis, étapes, résultat attendu.

**Comptes de référence** — ⚠️ connexion avec l'**email**, pas le username (username = identifiant affiché dans l'UI uniquement) :

| Rôle | Username (UI) | Email (login) | Mot de passe |
|---|---|---|---|
| Utilisateur standard | `testuser1` | `testuser1@vermeg.com` | `TestPass123!` |
| Officier conformité #1 | `officer1` | `officer1@vermeg.com` | `TestPass123!` |
| Officier conformité #2 (double rôle admin+conformité) | `officer2` | `officer2@vermeg.com` | `TestPass123!` |
| Administrateur | `temp_approver` | `admin@vermeg.com` | `TestPass123!` |

---

## 1. Authentification & gestion des comptes

| # | Objectif | Étapes | Résultat attendu |
|---|---|---|---|
| 1.1 | Inscription d'un nouveau compte | Aller sur "Register", remplir email/username/mot de passe, soumettre | Compte créé avec `is_active = false` — message indiquant qu'une approbation admin est nécessaire |
| 1.2 | Connexion refusée avant approbation | Se connecter avec le compte créé en 1.1 | Connexion refusée ("Inactive user" ou équivalent) |
| 1.3 | Approbation d'inscription par un admin | Se connecter en admin → **User Management** → approuver le compte en attente | Le compte passe à `is_active = true` |
| 1.4 | Connexion réussie après approbation | Se connecter avec le compte nouvellement activé | Connexion réussie, redirection vers le dashboard |
| 1.5 | Connexion avec identifiants invalides | Login avec mauvais mot de passe | Erreur "Incorrect email or password", pas de token émis |
| 1.11 | Rejet d'un email hors domaine | Inscription avec un email non `@vermeg.com` (ex. `test@gmail.com`) | Rejeté (400) — "Only @vermeg.com email addresses are allowed" |
| 1.6 | Changement de mot de passe | Connecté, aller sur le profil → changer le mot de passe | Mot de passe mis à jour ; reconnexion avec le nouveau mot de passe fonctionne |
| 1.7 | Déconnexion | Cliquer "Logout" | Session terminée, redirection vers login |
| 1.8 | Un utilisateur ne peut pas modifier ses propres champs privilégiés | En tant que `testuser1`, tenter de modifier `is_admin` sur son propre profil via l'API | Requête rejetée (403) — seul un admin peut changer `is_active`/`is_admin`/`is_compliance_officer` |
| 1.9 | Un admin peut gérer les autres utilisateurs | Admin → **User Management** → éditer un utilisateur (rôle, statut) | Modification appliquée, visible immédiatement |
| 1.10 | Suppression d'un utilisateur | Admin → supprimer un compte de test | Compte supprimé, ne peut plus se connecter |

---

## 2. Description de message (Message Description)

| # | Objectif | Étapes | Résultat attendu |
|---|---|---|---|
| 2.1 | Upload d'un fichier source | **Message Desc** → uploader un fichier MT103 (.txt) exemple | Fichier accepté, aperçu affiché |
| 2.2 | Génération automatique de la structure | Cliquer "Generate MD" | Détection automatique du type MT103, structure des champs générée (blocs SWIFT) |
| 2.3 | Détection d'un mauvais format | Uploader un fichier corrompu / non SWIFT | Message d'erreur clair, pas de génération |
| 2.4 | Édition manuelle d'un élément | Ouvrir la MD générée → ajouter/éditer/supprimer un élément | Modification persistée |
| 2.5 | Import d'éléments depuis des colonnes (fichier CSV/Excel) | Uploader un fichier tabulaire → import des colonnes comme éléments | Éléments créés un par un, correctement typés |
| 2.6 | Import d'éléments depuis les blocs MT | Sur une MD de type SWIFT → "Import from MT blocks" | Éléments générés à partir de la structure de blocs détectée |
| 2.7 | Une MD ne peut pas être approuvée par son créateur | Connecté en tant que créateur de la MD, tenter d'approuver | Refusé — maker-checker : l'approbateur doit être différent du proposant |
| 2.8 | Approbation par un second utilisateur (admin) | Se connecter avec un autre compte admin → approuver la MD | Statut passe à `approved = true` |
| 2.9 | Rejet d'une MD | Admin → rejeter une MD en attente | Statut passe à `approved = false`, motif enregistré |
| 2.10 | Une MD non approuvée bloque le transform | Tenter un transform avec une MD non encore approuvée pour ce type | Transform refusé (400) — "No approved Message Description found" |
| 2.11 | Demande d'accès à une MD non possédée | `testuser1` (non propriétaire) → demander l'accès en modification à une MD | Requête créée avec statut `pending` |
| 2.12 | Octroi/refus d'une demande d'accès | Admin → **Access Requests** → accorder ou refuser | Statut mis à jour ; le demandeur reçoit une notification |
| 2.13 | Régénération du texte MT après édition des blocs | Éditer les blocs d'une MD → "Regenerate MT" | Nouveau texte MT généré cohérent avec les modifications |

---

## 3. Mapping & Formules

| # | Objectif | Étapes | Résultat attendu |
|---|---|---|---|
| 3.1 | Création d'un mapping | **Mapping** → "Create Mapping" → choisir source/cible (ex. MT103 → pacs.008) | Mapping créé avec statut `DRAFT` |
| 3.2 | Définition manuelle des éléments de mapping | Ouvrir le mapping → associer champ source à champ cible | Élément créé, statut `PENDING` puis `MAPPED` |
| 3.3 | Suggestion via RAG | Sur un élément non mappé → "Suggest via RAG" | Suggestion proposée avec un score de pertinence, source de la suggestion visible |
| 3.4 | Acceptation d'une suggestion RAG | Accepter la suggestion proposée | Élément mis à jour avec la formule suggérée |
| 3.5 | Rejet d'une suggestion RAG | Rejeter la suggestion | Élément reste non mappé, aucune formule appliquée |
| 3.6 | Génération automatique des éléments | "Generate Elements" sur un mapping | Tous les éléments mappables sont pré-remplis automatiquement via RAG |
| 3.7 | Création d'une formule de transformation | **Mapping Formulas** → créer une formule (ex. TRIM, SUBSTRING, CONCATENATION) | Formule enregistrée, testable sur un exemple |
| 3.8 | Édition / suppression d'une formule | Modifier ou supprimer une formule existante | Modification persistée ; formule supprimée n'est plus utilisable |
| 3.9 | Édition / suppression d'un mapping | Modifier le nom d'un mapping / le supprimer | Modification persistée ; suppression en cascade des éléments associés |
| 3.10 | Prévisualisation du transform | Sur un mapping → "Preview Transform" | Aperçu du résultat sans générer de fichier définitif |

---

## 4. Transformation (Transform)

| # | Objectif | Étapes | Résultat attendu |
|---|---|---|---|
| 4.1 | Transformation MT → ISO XML réussie | Uploader un MT103 valide, propre → transformer | Fichier XML pacs.008 généré, téléchargeable |
| 4.2 | Transformation ISO XML → MT réussie | Uploader un XML pacs.008 valide → transformer | Fichier MT103 texte généré |
| 4.3 | Fichier sans description de message approuvée | Transformer un type de message sans MD approuvée | Blocage (400) avant même la validation |
| 4.4 | Fichier sans règles de validation | Transformer un type sans règles importées | Blocage (404) — règles manquantes |
| 4.5 | Fichier échouant la validation | Transformer un fichier avec un champ obligatoire manquant ou mal formaté | Blocage (400), détail des champs en échec ; entrée créée dans la file de correction (voir 5.5) |
| 4.6 | Détection de doublon | Soumettre deux fois la même référence (`:20:`) dans la fenêtre de détection | Le second envoi est bloqué (409) — "Duplicate message ID detected" |
| 4.7 | Téléchargement direct d'un output non approuvé refusé | Tenter de télécharger via `/transform/download/{filename}` un fichier encore en attente d'approbation | Refusé (403) — protection contre le contournement de la mise en attente |
| 4.8 | Liste des outputs exclut les fichiers en attente | **Outputs** → vérifier qu'un fichier en attente n'apparaît pas dans la liste générale | Fichier absent tant qu'il n'est pas approuvé |

---

## 5. Validation

| # | Objectif | Étapes | Résultat attendu |
|---|---|---|---|
| 5.1 | Import des règles de validation | Depuis une MD approuvée → "Import rules from MD" | Règles créées (obligatoire, longueur, format FIN, pattern) |
| 5.2 | Validation d'un fichier conforme | **Validate** → uploader un fichier correct | `is_valid = true`, tous les champs "passed" |
| 5.3 | Validation d'un fichier non conforme | Uploader un fichier avec un champ hors format (ex. `:71A:` invalide) | Erreurs détaillées par champ, `is_valid = false` |
| 5.4 | Détection de type de message erroné | Valider un fichier MT202 contre des règles MT103 | Message d'erreur explicite de non-correspondance de type |
| 5.5 | Création automatique d'une correction en attente | Un transform échoue la validation | Entrée créée dans **Pending Transactions → Failed Validations**, visible avec détail des erreurs |
| 5.6 | Auto-résolution après correction | Soumettre à nouveau un fichier corrigé du même type | L'entrée précédente passe automatiquement à `resolved` |
| 5.7 | Rejet manuel d'une correction | Sur une entrée en attente → "Dismiss" | Statut passe à `dismissed`, sans nouvelle soumission requise |

---

## 6. Conformité — Filtrage sanctions & PEP

| # | Objectif | Étapes | Résultat attendu |
|---|---|---|---|
| 6.1 | Transaction propre (aucun contrôle déclenché) | Transformer un MT103 avec des noms neutres | Succès direct, aucun blocage ni mise en attente |
| 6.2 | Blocage sur correspondance sanctions | Transformer un MT103 dont le donneur d'ordre correspond à une entrée `SANCTIONS` active | Blocage immédiat (403), entrée `sanctions_block` au journal d'audit, notification aux admins |
| 6.3 | Mise en attente sur correspondance PEP | Transformer un MT103 dont le donneur d'ordre correspond à une entrée `PEP` active | Statut 202 "held_for_approval", `approver_role = compliance_officer` |
| 6.4 | Un admin seul ne peut pas approuver une mise en attente PEP | Connecté en admin (non conformité) → tenter d'approuver la mise en attente PEP | Refusé (403) — "Compliance officer access required" |
| 6.5 | Un officier de conformité approuve la mise en attente PEP | Connecté en officier conformité (≠ soumetteur) → approuver | Statut `approved`, fichier téléchargeable |
| 6.6 | Auto-approbation interdite | Le soumetteur de la transaction tente lui-même de l'approuver | Refusé — le soumetteur ne peut jamais être son propre approbateur |
| 6.7 | Toggle de désactivation du filtrage | Admin → **Business Variables** → mettre `SANCTIONS_SCREENING_ENABLED` ou `PEP_SCREENING_ENABLED` à `false` → retransformer un fichier normalement bloqué | Le filtrage correspondant est ignoré ; remettre à `true` après le test |

---

## 7. Conformité — Seuils de montant (approbation multi-niveaux)

| # | Objectif | Étapes | Résultat attendu |
|---|---|---|---|
| 7.1 | Montant sous le seuil | Transformer un MT103 avec montant < `LARGE_AMOUNT_THRESHOLD` (20 000 €) | Succès direct |
| 7.2 | Montant au-dessus du seuil simple | Transformer un montant entre le seuil simple et le seuil critique (ex. 75 000 €) | Mise en attente, 1 approbation admin requise |
| 7.3 | Montant au-dessus du seuil critique | Transformer un montant > `CRITICAL_AMOUNT_THRESHOLD` (100 000 €) | Mise en attente, **2** approbations admin distinctes requises |
| 7.4 | Vote unique par admin | Un même admin tente de voter deux fois sur la même transaction | Refusé — "You already approved this transaction" |
| 7.5 | Libération après quorum atteint | Faire approuver par le nombre d'admins requis | Statut `approved` seulement une fois le quorum atteint, pas avant |
| 7.6 | Rejet d'une mise en attente | Un admin (≠ soumetteur) rejette la transaction | Statut `rejected`, fichier de sortie supprimé du disque |
| 7.7 | Modification du seuil à chaud | Admin → **Business Variables** → modifier `LARGE_AMOUNT_THRESHOLD` → retester avec un montant entre l'ancien et le nouveau seuil | Le nouveau seuil est immédiatement pris en compte |

---

## 8. Gouvernance de la Watchlist (sanctions/PEP)

| # | Objectif | Étapes | Résultat attendu |
|---|---|---|---|
| 8.1 | Proposition d'ajout | Officier conformité → **Watchlist** → "Add Entity" | Entrée créée avec statut `pending_add` |
| 8.2 | Confirmation par un second officier | Un second officier (≠ proposant) confirme | Statut passe à `active` |
| 8.3 | Auto-confirmation interdite | Le proposant tente lui-même de confirmer | Refusé |
| 8.4 | Rejet d'une proposition d'ajout | Second officier rejette la proposition | Statut passe à `rejected`, entrée non appliquée |
| 8.5 | Demande de retrait | Officier → demander le retrait d'une entrée active | Statut passe à `pending_remove` — l'entrée reste **active** et continue d'être appliquée pendant l'attente |
| 8.6 | Confirmation du retrait | Second officier confirme le retrait | Statut passe à `active` retiré (l'entrée n'est plus appliquée) |
| 8.7 | Rejet du retrait | Second officier rejette le retrait | L'entrée reste `active`, continue d'être appliquée |

---

## 9. Journal d'audit

| # | Objectif | Étapes | Résultat attendu |
|---|---|---|---|
| 9.1 | Accès réservé aux admins | Se connecter en utilisateur standard → tenter d'accéder à **Audit Log** | Accès refusé |
| 9.2 | Consultation par un admin | Admin → **Audit Log** | Liste complète, horodatée, filtrable par action/entité/utilisateur |
| 9.3 | Persistance après suppression d'un compte | Supprimer un utilisateur ayant des entrées au journal → consulter le journal | Les entrées restent visibles avec le username dénormalisé, même si le compte n'existe plus |

---

## 10. Variables métier (Business Variables)

| # | Objectif | Étapes | Résultat attendu |
|---|---|---|---|
| 10.1 | Consultation | N'importe quel utilisateur connecté → **Business Variables** | Liste visible en lecture |
| 10.2 | Modification réservée aux admins | Utilisateur standard → tenter de modifier une variable | Refusé (403) |
| 10.3 | Modification par un admin | Admin → modifier une valeur (ex. seuil) | Modification appliquée, `updated_by`/`updated_at` mis à jour |

---

## 11. Traitement par lot (Batch Processing)

| # | Objectif | Étapes | Résultat attendu |
|---|---|---|---|
| 11.1 | Sélection multiple de fichiers | **Batch Processing** → sélectionner un mapping → glisser-déposer plusieurs fichiers | Tous les fichiers apparaissent dans la liste |
| 11.2 | Exécution du lot avec résultats mixtes | Inclure un fichier valide, un doublon, un fichier PEP, un fichier invalide → "Run Batch" | Résumé correct : succès / en attente / échecs, un résultat par fichier |
| 11.3 | Détection de doublon intra-lot | Inclure deux fichiers avec la même référence dans le même lot | Le second est bloqué comme doublon du premier |
| 11.4 | Téléchargement d'un résultat réussi | Cliquer le bouton de téléchargement sur une ligne "Success" | Fichier téléchargé correctement |
| 11.5 | Effacement des résultats | Bouton "Clear" après un lot | Liste de fichiers et résultats réinitialisés |

---

## 12. Pipeline & Transport

| # | Objectif | Étapes | Résultat attendu |
|---|---|---|---|
| 12.1 | Création d'un Config IN (FILE) | **Configuration** → nouveau config, direction IN, type FILE, chemin valide | Config créé |
| 12.2 | Création d'un Config OUT (REST) | Nouveau config, direction OUT, type REST, URL cible | Config créé |
| 12.3 | Test de connexion | Sur un config REST/RabbitMQ/Kafka → "Test connection" | Résultat de connectivité affiché |
| 12.4 | Création d'un pipeline | **Consommation** → lier Config IN + Mapping + Config OUT | Pipeline créé, actif par défaut |
| 12.5 | Exécution manuelle réussie | "Start" sur le pipeline avec un fichier présent et une destination valide | Statut "success", fichier consommé et déplacé vers `processed/` |
| 12.6 | Exécution manuelle avec échec de livraison | Config OUT pointant vers une destination injoignable → "Start" | Statut "error" sur l'étape Config OUT ; fichier source **non déplacé** (reste disponible pour réessai) |
| 12.7 | Exécution automatique planifiée | Laisser le pipeline actif, attendre le prochain cycle du planificateur | Le pipeline s'exécute automatiquement sans action manuelle |

---

## 13. File de re-livraison (Pending Delivery Retry)

| # | Objectif | Étapes | Résultat attendu |
|---|---|---|---|
| 13.1 | Création automatique après échec | Suite au cas 12.6 → **Consommation → Pending Delivery Retries** | Entrée créée avec message d'erreur et copie de la sortie transformée |
| 13.2 | Nouvelle tentative après correction | Corriger la destination du Config OUT → cliquer "Retry" | Statut passe à `delivered`, contenu **identique** à l'origine (pas de re-transformation) |
| 13.3 | Abandon d'une re-livraison | Sur une entrée en attente → "Abandon" | Statut `abandoned`, ne réapparaît plus dans le filtre "pending" |
| 13.4 | Blocage d'une nouvelle tentative sur entrée déjà résolue | Retenter "Retry" sur une entrée déjà `delivered` ou `abandoned` | Refusé — "Already delivered/abandoned" |

---

## 14. Demandes d'accès (Access Requests)

| # | Objectif | Étapes | Résultat attendu |
|---|---|---|---|
| 14.1 | Création d'une demande | Utilisateur non propriétaire → demander l'accès à une MD | Demande créée, statut `pending` |
| 14.2 | Octroi | Admin → accorder | Statut `granted`, l'utilisateur peut désormais modifier la MD |
| 14.3 | Refus | Admin → refuser | Statut `denied`, l'utilisateur reste bloqué |

---

## 15. Notifications

| # | Objectif | Étapes | Résultat attendu |
|---|---|---|---|
| 15.1 | Réception automatique | Déclencher un événement notifiant (ex. mise en attente PEP) | Le(s) destinataire(s) concerné(s) reçoivent une notification avec lien |
| 15.2 | Marquage comme lue | Cliquer sur une notification / "Mark as read" | Statut `is_read = true` |
| 15.3 | Suppression | Supprimer une notification individuelle ou toutes | Notification(s) supprimée(s) de la liste |

---

## 16. Reporting réglementaire

| # | Objectif | Étapes | Résultat attendu |
|---|---|---|---|
| 16.1 | Accès réservé | Utilisateur standard → tenter d'accéder à **Regulatory Reports** | Accès refusé |
| 16.2 | Vue d'ensemble | Admin ou officier → consulter le rapport sans filtre | Total et répartition par catégorie affichés |
| 16.3 | Filtre par période | Restreindre à une plage de dates/heures précise | Seuls les événements dans la plage apparaissent |
| 16.4 | Filtre par catégorie | Filtrer sur "Sanctions & PEP Screening" | Seule cette catégorie est affichée, les autres passent à 0 |
| 16.5 | Export CSV | "Export CSV" avec filtres actifs | Fichier téléchargé, contenu cohérent avec les filtres appliqués |
| 16.6 | Catégorisation correcte des approbations ambiguës | Vérifier qu'une approbation de mise en attente PEP est bien classée "Sanctions & PEP Screening" et non "Large-Amount Approval" | Catégorie correcte, résolue via le rôle réel de l'approbateur |

---

## 17. Dashboard SLA / Performance

| # | Objectif | Étapes | Résultat attendu |
|---|---|---|---|
| 17.1 | Accès réservé | Utilisateur standard → tenter d'accéder à **SLA Dashboard** | Accès refusé |
| 17.2 | Volume de transformations | Admin/officier → consulter le nombre de transformations sur la période | Chiffre cohérent avec les tests effectués |
| 17.3 | Temps de traitement moyen | Consulter le temps moyen de résolution des mises en attente, par rôle | Temps distincts pour admin vs conformité |
| 17.4 | Taux de blocage/flag | Consulter les compteurs sanctions/doublons/AML | Chiffres cohérents avec le journal d'audit |
| 17.5 | Graphique d'activité journalière | Consulter le graphique | Les jours sans activité apparaissent à zéro, pas absents |

---

## 18. Administration RAG

| # | Objectif | Étapes | Résultat attendu |
|---|---|---|---|
| 18.1 | Statut de la base vectorielle | Admin → consulter le statut RAG | Nombre de points/collections affiché (Qdrant) |
| 18.2 | Réinitialisation | Admin → "Reset RAG" | Base vectorielle réinitialisée |
| 18.3 | Suppression d'un mapping de l'index | Admin → supprimer un mapping spécifique de l'index RAG | Le mapping n'est plus proposé dans les futures suggestions |

---

## Résumé de couverture

| Domaine | Nb. de cas |
|---|---|
| Authentification & comptes | 10 |
| Description de message | 13 |
| Mapping & formules | 10 |
| Transformation | 8 |
| Validation | 7 |
| Conformité sanctions/PEP | 7 |
| Conformité montant | 7 |
| Watchlist | 7 |
| Audit | 3 |
| Variables métier | 3 |
| Batch | 5 |
| Pipeline & Transport | 7 |
| Retry de livraison | 4 |
| Demandes d'accès | 3 |
| Notifications | 3 |
| Reporting réglementaire | 6 |
| SLA | 5 |
| RAG Admin | 3 |
| **Total** | **112 cas de test** |
