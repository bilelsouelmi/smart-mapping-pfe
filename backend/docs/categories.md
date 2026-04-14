# Catégories - StandardElements

Documentation des catégories d'éléments de données dans le système Smart Mapping.

---

## 📊 Vue d'Ensemble

Les **catégories** permettent d'organiser les StandardElements par domaine fonctionnel. Chaque élément appartient à une seule catégorie.

**Nombre de catégories actuelles :** 6  
**Basé sur :** ISO 20022 pain.001.001.12

---

## 🏷️ Catégories Disponibles

### 1. Header
**Description :** Informations d'en-tête du message

**Rôle :**
- Identification du message
- Métadonnées de transmission
- Informations de contrôle

**Éléments (4) :**
- `MSG_ID` - Message Identification
- `MSG_CREDT` - Creation Date Time
- `MSG_NBTXS` - Number of Transactions
- `MSG_CTRLSUM` - Control Sum

**Exemple d'utilisation :**
```json
{
"Header": {
"MessageId": "MSG-2026-01-27-001",
"CreationDateTime": "2026-01-27T10:30:00Z",
"NumberOfTransactions": 5,
"ControlSum": 15000.00
}
}
**Obligatoire :** Oui (3/4 éléments mandatory)

---

### 2. Payment
**Description :** Informations générales sur le paiement

**Rôle :**
- Instructions de paiement
- Méthode et timing
- Identifiants de lot

**Éléments (3) :**
- `PMT_INFID` - Payment Information ID
- `PMT_MTD` - Payment Method
- `PMT_REQEXCDT` - Requested Execution Date

**Exemple d'utilisation :**
```json
{
"PaymentInfo": {
"PaymentInfoId": "PMT-INFO-001",
"Method": "TRF",
"RequestedDate": "2026-01-28"
}
}
# Catégories - StandardElements

Documentation des catégories d'éléments de données dans le système Smart Mapping.

---

## 📊 Vue d'Ensemble

Les **catégories** permettent d'organiser les StandardElements par domaine fonctionnel. Chaque élément appartient à une seule catégorie.

**Nombre de catégories actuelles :** 6  
**Basé sur :** ISO 20022 pain.001.001.12

---

## 🏷️ Catégories Disponibles

### 1. Header
**Description :** Informations d'en-tête du message

**Rôle :**
- Identification du message
- Métadonnées de transmission
- Informations de contrôle

**Éléments (4) :**
- `MSG_ID` - Message Identification
- `MSG_CREDT` - Creation Date Time
- `MSG_NBTXS` - Number of Transactions
- `MSG_CTRLSUM` - Control Sum

**Exemple d'utilisation :**
```json
{
  "Header": {
    "MessageId": "MSG-2026-01-27-001",
    "CreationDateTime": "2026-01-27T10:30:00Z",
    "NumberOfTransactions": 5,
    "ControlSum": 15000.00
  }
}
```

**Obligatoire :** Oui (3/4 éléments mandatory)

---

### 2. Payment
**Description :** Informations générales sur le paiement

**Rôle :**
- Instructions de paiement
- Méthode et timing
- Identifiants de lot

**Éléments (3) :**
- `PMT_INFID` - Payment Information ID
- `PMT_MTD` - Payment Method
- `PMT_REQEXCDT` - Requested Execution Date

**Exemple d'utilisation :**
```json
{
  "PaymentInfo": {
    "PaymentInfoId": "PMT-INFO-001",
    "Method": "TRF",
    "RequestedDate": "2026-01-28"
  }
}
```

**Obligatoire :** Oui (tous les éléments mandatory)

---

### 3. Debtor
**Description :** Informations sur l'émetteur/débiteur

**Rôle :**
- Identité de l'émetteur
- Coordonnées complètes
- Compte à débiter
- Banque émettrice

**Éléments (7) :**
- `DBTR_NM` - Debtor Name
- `DBTR_ADDR` - Debtor Address (MAP)
- `DBTR_STRTNM` - Debtor Street Name
- `DBTR_BLDGNB` - Debtor Building Number
- `DBTR_PSTCD` - Debtor Postal Code
- `DBTR_TWNNM` - Debtor Town Name
- `DBTR_CTRY` - Debtor Country
- `DBTR_IBAN` - Debtor IBAN
- `DBTR_CCY` - Debtor Account Currency
- `DBTRAGT_BIC` - Debtor Agent BIC

**Exemple d'utilisation :**
```json
{
  "Debtor": {
    "Name": "Jean Dupont",
    "Address": {
      "StreetName": "123 Avenue Habib Bourguiba",
      "TownName": "Tunis",
      "PostalCode": "1000",
      "Country": "TN"
    },
    "Account": {
      "IBAN": "TN5914207490000021879544",
      "Currency": "TND"
    },
    "Agent": {
      "BIC": "BTKETN"
    }
  }
}
```

**Obligatoire :** Partiellement (Name, Town, Country, IBAN mandatory)

---

### 4. Creditor
**Description :** Informations sur le bénéficiaire/créditeur

**Rôle :**
- Identité du bénéficiaire
- Coordonnées complètes
- Compte à créditer
- Banque bénéficiaire

**Éléments (6) :**
- `CDTR_NM` - Creditor Name
- `CDTR_ADDR` - Creditor Address (MAP)
- `CDTR_STRTNM` - Creditor Street Name
- `CDTR_PSTCD` - Creditor Postal Code
- `CDTR_TWNNM` - Creditor Town Name
- `CDTR_CTRY` - Creditor Country
- `CDTR_IBAN` - Creditor IBAN
- `CDTRAGT_BIC` - Creditor Agent BIC

**Exemple d'utilisation :**
```json
{
  "Creditor": {
    "Name": "Marie Martin",
    "Address": {
      "StreetName": "456 Rue de la République",
      "TownName": "Sfax",
      "PostalCode": "2000",
      "Country": "TN"
    },
    "Account": {
      "IBAN": "TN5910006035183598478831"
    }
  }
}
```

**Obligatoire :** Partiellement (Name, Town, Country, IBAN mandatory)

---

### 5. Transaction
**Description :** Détails de la transaction individuelle

**Rôle :**
- Montant et devise
- Identifiants de transaction
- Instructions spécifiques

**Éléments (5) :**
- `TXN_INSTRID` - Instruction ID
- `TXN_ENDTOENDID` - End To End ID
- `TXN_AMT` - Transaction Amount
- `TXN_CCY` - Transaction Currency

**Exemple d'utilisation :**
```json
{
  "Transaction": {
    "InstructionId": "TXN-2026-001",
    "EndToEndId": "E2E-2026-001",
    "Amount": {
      "Value": 1500.50,
      "Currency": "TND"
    }
  }
}
```

**Obligatoire :** Oui (tous les éléments mandatory)

---

### 6. Remittance
**Description :** Informations de remise/justification

**Rôle :**
- Motif du paiement
- Références de factures
- Informations libres

**Éléments (1) :**
- `RMT_USTRD` - Remittance Unstructured

**Exemple d'utilisation :**
```json
{
  "Remittance": {
    "Unstructured": "Paiement facture 2026-001"
  }
}
```

**Obligatoire :** Non (optionnel)

---

## 📊 Statistiques par Catégorie

| Catégorie | Éléments | Mandatory | Optionnels | Structure MAP |
|-----------|----------|-----------|------------|---------------|
| Header | 4 | 3 | 1 | 0 |
| Payment | 3 | 3 | 0 | 0 |
| Debtor | 10 | 4 | 6 | 1 (Address) |
| Creditor | 8 | 4 | 4 | 1 (Address) |
| Transaction | 4 | 4 | 0 | 0 |
| Remittance | 1 | 0 | 1 | 0 |
| **Total** | **30** | **18** | **12** | **2** |

---

## 🔄 Hiérarchie dans un Message Complet
```
pain.001 Message
├── Header (Niveau 1)
│   ├── MessageId
│   ├── CreationDateTime
│   └── ...
│
├── PaymentInfo (Niveau 1)
│   ├── PaymentInfoId
│   ├── Method
│   │
│   ├── Debtor (Niveau 2)
│   │   ├── Name
│   │   ├── Address (Niveau 3 - MAP)
│   │   └── Account
│   │
│   └── Transaction (Niveau 2)
│       ├── Amount
│       ├── Creditor (Niveau 3)
│       │   ├── Name
│       │   └── Account
│       └── Remittance
```

---

## 🎯 Utilisation dans l'API

### Filtrer par Catégorie
```bash
GET /api/standard-elements/?category=Debtor
```

**Réponse :**
```json
[
  {
    "element_id": "DBTR_NM",
    "element_name": "Debtor Name",
    "category": "Debtor",
    "data_type": "string"
  },
  ...
]
```

### Lister les Catégories
```bash
GET /api/standard-elements/categories
```

**Réponse :**
```json
[
  {"category": "Header", "count": 4},
  {"category": "Payment", "count": 3},
  {"category": "Debtor", "count": 10},
  {"category": "Creditor", "count": 8},
  {"category": "Transaction", "count": 4},
  {"category": "Remittance", "count": 1}
]
```

---

## 🔮 Évolution Future

### Catégories Potentielles à Ajouter

**Pour pain.002 (Status Report) :**
- `StatusReport` - Rapports de statut
- `StatusReason` - Raisons de statut

**Pour pain.007 (Reversal) :**
- `ReversalInfo` - Informations d'annulation

**Pour pain.008 (Direct Debit) :**
- `MandateInfo` - Informations de mandat

**Pour formats Vermeg :**
- `CustomFields` - Champs personnalisés
- `Metadata` - Métadonnées additionnelles

---

## 💡 Bonnes Pratiques

### Choix de Catégorie

✅ **Une catégorie par élément**
- Chaque élément appartient à une seule catégorie

✅ **Cohérence fonctionnelle**
- Grouper les éléments par rôle métier

✅ **Hiérarchie logique**
- Respecter la structure du message

❌ **À éviter**
- Catégories trop granulaires
- Mélanger différents niveaux hiérarchiques
- Catégories "fourre-tout"

---

## 🔗 Voir Aussi

- [Types de Données](data_types.md)
- [Types de Structure](structure_types.md)
- [ISO 20022 pain.001](iso20022_pain001.md)
