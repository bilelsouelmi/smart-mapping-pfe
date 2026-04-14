# Types de Structure - StandardElements

## Types Supportés

### 1. simple
Champ scalaire avec une seule valeur.

**Exemples :**
- FirstName: "Jean"
- Amount: 1500.50
- Date: "2026-01-27"

**Utilisation :**
- Champs de base
- Pas de sous-structure

---

### 2. map
Structure fixe avec des champs prédéfinis (clés connues à l'avance).

**Exemple - Address :**
```json
{
  "street": "123 Avenue Bourguiba",
  "city": "Tunis",
  "postalCode": "1000",
  "country": "TN"
}
```

**Caractéristiques :**
- Clés fixes et connues
- Validation stricte possible
- Structure immuable

---

### 3. hmap (HashMap)
Structure dynamique avec des clés variables (non connues à l'avance).

**Exemple - CustomFields :**
```json
{
  "field_1": "value_1",
  "field_2": "value_2",
  "custom_attribute": "some_value"
}
```

**Caractéristiques :**
- Clés dynamiques
- Flexibilité maximale
- Validation générique seulement

---

### 4. array
Liste ordonnée d'éléments (tous du même type ou types mixtes).

**Exemple - Transactions :**
```json
[
  {"id": 1, "amount": 100},
  {"id": 2, "amount": 200}
]
```

---

### 5. object
Objet complexe avec structure mixte.

**Exemple - ComplexData :**
```json
{
  "header": {...},
  "items": [...],
  "metadata": {...}
}