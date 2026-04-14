# Types de Données - StandardElements

Documentation complète des types de données supportés dans le système Smart Mapping.

---

## 📊 Types Supportés

### 1. string
**Type texte** - Chaîne de caractères de longueur variable

**Utilisation :**
- Noms, prénoms, adresses
- Codes (IBAN, BIC, pays)
- Identifiants alphanumériques
- Descriptions textuelles

**Exemples :**
```json
{
  "element_id": "DBTR_NM",
  "data_type": "string",
  "example_value": "Jean Dupont"
}

{
  "element_id": "DBTR_IBAN",
  "data_type": "string",
  "example_value": "TN5914207490000021879544"
}
```

**Contraintes :**
- Longueur max : définie par `max_length` (optionnel)
- Pattern : défini par `validation_regex` (optionnel)
- Exemple : IBAN TN doit commencer par "TN" et avoir 24 caractères

---

### 2. integer
**Type entier** - Nombre entier sans décimales

**Utilisation :**
- Compteurs (nombre de transactions)
- IDs numériques
- Codes numériques
- Quantités entières

**Exemples :**
```json
{
  "element_id": "MSG_NBTXS",
  "data_type": "integer",
  "example_value": 5
}

{
  "element_id": "ACCT_BALANCE_COUNT",
  "data_type": "integer",
  "example_value": 1250
}
```

**Contraintes :**
- Valeur minimale : `min_value` (optionnel)
- Valeur maximale : `max_value` (optionnel)
- Toujours sans virgule

---

### 3. decimal
**Type décimal** - Nombre avec décimales (précision importante)

**Utilisation :**
- Montants financiers
- Taux de change
- Pourcentages
- Valeurs monétaires

**Exemples :**
```json
{
  "element_id": "TXN_AMT",
  "data_type": "decimal",
  "example_value": 1500.50
}

{
  "element_id": "EXCHANGE_RATE",
  "data_type": "decimal",
  "example_value": 0.304
}
```

**Contraintes :**
- Précision : généralement 2 décimales pour les montants
- Précision : jusqu'à 6 décimales pour les taux de change
- Toujours positif ou négatif selon le contexte

**⚠️ Important :** Utilisez `decimal` (pas `float`) pour les calculs financiers pour éviter les erreurs d'arrondi.

---

### 4. date
**Type date** - Date sans heure

**Utilisation :**
- Dates de naissance
- Dates d'échéance
- Dates d'exécution
- Dates de validité

**Formats supportés :**
- ISO 8601 : `YYYY-MM-DD` (recommandé)
- Français : `DD/MM/YYYY`
- US : `MM/DD/YYYY`

**Exemples :**
```json
{
  "element_id": "PMT_REQEXCDT",
  "data_type": "date",
  "example_value": "2026-01-28",
  "format_pattern": "YYYY-MM-DD"
}

{
  "element_id": "PERS_DOB",
  "data_type": "date",
  "example_value": "1985-03-15"
}
```

**Contraintes :**
- Format défini par `format_pattern`
- Validation de date valide (ex: pas de 31 février)

---

### 5. datetime
**Type date-heure** - Date avec heure précise

**Utilisation :**
- Timestamps de messages
- Dates de création
- Horodatage d'événements
- Logs

**Format :**
- ISO 8601 avec timezone : `YYYY-MM-DDTHH:MM:SS+TZ`
- Exemple : `2026-01-27T10:30:00+01:00`

**Exemples :**
```json
{
  "element_id": "MSG_CREDT",
  "data_type": "datetime",
  "example_value": "2026-01-27T10:30:00Z"
}
```

**Contraintes :**
- Inclut toujours la timezone (UTC recommandé)
- Précision à la seconde ou milliseconde

---

### 6. boolean
**Type booléen** - Vrai ou Faux

**Utilisation :**
- Flags (actif/inactif)
- Validations (valide/invalide)
- Options (oui/non)
- Status binaires

**Valeurs :**
- `true` / `false`
- `1` / `0` (converti en boolean)
- `"yes"` / `"no"` (converti en boolean)

**Exemples :**
```json
{
  "element_id": "IS_URGENT",
  "data_type": "boolean",
  "example_value": true
}

{
  "element_id": "IS_VALID_IBAN",
  "data_type": "boolean",
  "example_value": false
}
```

---

### 7. object
**Type objet** - Structure complexe (JSON)

**Utilisation :**
- Structures imbriquées
- Adresses complètes
- Objets composés
- Données hiérarchiques

**Note :** Souvent combiné avec `structure_type = "map"` ou `"hmap"`

**Exemples :**
```json
{
  "element_id": "DBTR_ADDR",
  "data_type": "object",
  "structure_type": "map",
  "example_value": {
    "street": "123 Avenue Bourguiba",
    "city": "Tunis",
    "postalCode": "1000",
    "country": "TN"
  }
}
```

---

### 8. array
**Type tableau** - Liste d'éléments

**Utilisation :**
- Listes de transactions
- Multiples bénéficiaires
- Collections d'objets
- Séries de données

**Exemples :**
```json
{
  "element_id": "TRANSACTIONS_LIST",
  "data_type": "array",
  "structure_type": "array",
  "example_value": [
    {"id": 1, "amount": 100},
    {"id": 2, "amount": 200}
  ]
}
```

---

## 🔄 Conversions de Types

### FormulaEngine - Conversions Automatiques

**string → integer**
```javascript
parseInt("123") // 123
```

**string → decimal**
```javascript
parseFloat("1500.50") // 1500.50
```

**string → date**
```javascript
date_format("27/01/2026", "DD/MM/YYYY", "YYYY-MM-DD") // "2026-01-27"
```

**integer → string**
```javascript
toString(123) // "123"
```

---

## ✅ Validation par Type

### string
- Longueur min/max
- Pattern regex
- Valeurs autorisées (enum)

### integer
- Min/max
- Positive uniquement

### decimal
- Min/max
- Nombre de décimales
- Positive uniquement

### date/datetime
- Format
- Date dans le futur/passé
- Plage de dates

### boolean
- true/false uniquement

---

## 📋 Recommandations

### Montants Financiers
✅ Utilisez `decimal` (pas `float`)  
✅ Précision 2 décimales pour les montants  
✅ Précision 4-6 décimales pour les taux

### Dates
✅ Format ISO 8601 (`YYYY-MM-DD`)  
✅ Toujours avec timezone pour datetime  
✅ UTC recommandé

### Identifiants
✅ `string` pour IDs alphanumériques (IBAN, BIC)  
✅ `integer` pour IDs numériques auto-incrémentés

### Structures
✅ `object` + `structure_type="map"` pour structures fixes  
✅ `object` + `structure_type="hmap"` pour structures dynamiques

---

## 🔗 Voir Aussi

- [Types de Structure](structure_types.md)
- [Catégories](categories.md)
- [Formula Engine](formula_engine.md)