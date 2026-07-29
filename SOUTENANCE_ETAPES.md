# Étapes du scénario — check-list rapide
### (sans le speech — voir SOUTENANCE_SCRIPT.md pour le texte à lire)

---

## Comptes
> ⚠️ Connexion avec l'**email**, pas le username.

| Rôle | Username (UI) | Email (login) | Mot de passe |
|---|---|---|---|
| Utilisateur | `testuser1` | `testuser1@vermeg.com` | `TestPass123!` |
| Officier conformité #1 | `officer1` | `officer1@vermeg.com` | `TestPass123!` |
| Officier conformité #2 | `officer2` | `officer2@vermeg.com` | `TestPass123!` |
| Administrateur | `temp_approver` | `admin@vermeg.com` | `TestPass123!` |

## Fichiers de test
`demo_1_success.txt` · `demo_2_sanctions.txt` · `demo_3_pep.txt` · `demo_4_large_amount.txt`

---

### 1. Introduction (~1 min)
- Rester sur la page de connexion / dashboard vide.

### 2. Message Description & Mapping (~3 min)
1. Connexion `testuser1`.
2. **Message Desc** → montrer la description MT103 approuvée (badge vert).
3. **Mapping** → ouvrir **"MT103 → pacs.008 mapping"** → montrer les éléments.
4. Cliquer un élément avec formule → montrer `suggestion_source` (RAG).

### 3. Transformation réussie (~2 min)
1. Page de transformation du mapping MT103 → pacs.008.
2. Uploader `demo_1_success.txt`.
3. Lancer → montrer le XML pacs.008 généré.

### 4. Watchlist + blocage sanctions (~3 min)
1. Déconnexion → connexion `officer1`.
2. **Watchlist** → "Add Entity" → Nom `NORTHSTAR SHELL HOLDINGS`, Liste `SANCTIONS` → soumettre.
3. Déconnexion → connexion `officer2`.
4. **Watchlist** → trouver l'entrée en attente → confirmer (statut → `active`).
5. Déconnexion → connexion `testuser1`.
6. Uploader `demo_2_sanctions.txt` → transformer → montrer le blocage (403).
7. (Optionnel) **Audit Log** → montrer l'entrée `sanctions_block`.

### 5. PEP — mise en attente (~3 min)
1. `testuser1` → uploader `demo_3_pep.txt` → transformer → montrer "held" (202).
2. **Pending Transactions** → montrer l'entrée "PEP match".
3. Déconnexion → connexion `temp_approver` (admin).
4. **Pending Transactions** → essayer d'approuver → montrer le refus.
5. Déconnexion → connexion `officer1`.
6. Approuver → statut "Approved" → télécharger.

### 6. Montant élevé (~2 min)
1. `testuser1` → uploader `demo_4_large_amount.txt` → transformer → "held".
2. Connexion `temp_approver` → approuver.
3. (Optionnel) **Business Variables** → montrer `LARGE_AMOUNT_THRESHOLD` = 20000.

### 7. Reporting & SLA (~3 min)
1. Rester connecté (officier ou admin).
2. **Regulatory Reports** → filtrer catégorie "Sanctions & PEP Screening" → "Export CSV".
3. **SLA Dashboard** → montrer volume, temps de traitement, graphique journalier.

### 8. Conclusion (~1 min)
- Retour au dashboard général.

---

## ✅ Checklist avant d'enregistrer
- [ ] Les 4 comptes se connectent
- [ ] Les 4 fichiers sont accessibles
- [ ] "NORTHSTAR SHELL HOLDINGS" **n'est pas déjà** dans la watchlist
- [ ] Mapping MT103 → pacs.008 approuvé et actif
- [ ] Micro testé, notifications désactivées
