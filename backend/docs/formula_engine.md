# Formula Engine - Moteur de Formules

Documentation du moteur d'exécution de formules de transformation dans Smart Mapping Platform.

---

## 🎯 Vue d'Ensemble

Le **FormulaEngine** est le composant responsable de l'exécution des règles de transformation de données. Il supporte 5 types de formules différents et permet d'appliquer des transformations complexes sur les données mappées.

**Localisation :** `backend/app/services/formula_engine.py`

---

## 🔧 Types de Formules

### 1. arithmetic - Calculs Arithmétiques

**Description :** Effectue des opérations mathématiques.

**Opérations supportées :**
- Addition : `+`
- Soustraction : `-`
- Multiplication : `*`
- Division : `/`
- Parenthèses : `()`

**Exemples :**
```python
# Exemple 1 : Conversion de devise
formula = "amount * 0.304"
input_data = {"amount": 1500.50}
result = engine.execute("arithmetic", formula, input_data)
# Résultat : 456.152

# Exemple 2 : Calcul TVA
formula = "amount * 0.19"
input_data = {"amount": 1000}
result = engine.execute("arithmetic", formula, input_data)
# Résultat : 190.0

# Exemple 3 : Total TTC
formula = "amount * 1.19"
input_data = {"amount": 1000}
result = engine.execute("arithmetic", formula, input_data)
# Résultat : 1190.0

# Exemple 4 : Calculs complexes
formula = "(montant + frais) * taux"
input_data = {"montant": 1000, "frais": 50, "taux": 1.05}
result = engine.execute("arithmetic", formula, input_data)
# Résultat : 1102.5
```

**Sécurité :** Seuls les caractères mathématiques sont autorisés (`0-9 + - * / . ( )`).

---

### 2. conditional - Conditions

**Description :** Exécute des conditions IF-THEN-ELSE et CASE WHEN.

**Syntaxe IF simple :**
```
IF condition THEN valeur_si_vrai ELSE valeur_si_faux
```

**Syntaxe CASE WHEN :**
```
CASE WHEN condition1 THEN valeur1 WHEN condition2 THEN valeur2 ELSE valeur_par_defaut
```

**Exemples :**
```python
# Exemple 1 : Classification simple
formula = "IF country='TN' THEN 'DOMESTIC' ELSE 'INTERNATIONAL'"
input_data = {"country": "TN"}
result = engine.execute("conditional", formula, input_data)
# Résultat : "DOMESTIC"

# Exemple 2 : Classification par montant
formula = "CASE WHEN amount < 1000 THEN 'LOW' WHEN amount < 10000 THEN 'MEDIUM' ELSE 'HIGH'"
input_data = {"amount": 1500.50}
result = engine.execute("conditional", formula, input_data)
# Résultat : "MEDIUM"

# Exemple 3 : Validation
formula = "IF amount > 0 AND amount < 1000000 THEN 'VALID' ELSE 'INVALID'"
input_data = {"amount": 1500}
result = engine.execute("conditional", formula, input_data)
# Résultat : "VALID"

# Exemple 4 : Type de transaction
formula = "IF type='VIREMENT' THEN 'TRF' ELSE IF type='CHEQUE' THEN 'CHK' ELSE 'OTHER'"
input_data = {"type": "VIREMENT"}
result = engine.execute("conditional", formula, input_data)
# Résultat : "TRF"
```

**Opérateurs supportés :**
- Égalité : `=` ou `==`
- Différent : `!=`
- Plus grand : `>`
- Plus petit : `<`
- Plus grand ou égal : `>=`
- Plus petit ou égal : `<=`
- ET logique : `AND`
- OU logique : `OR`

---

### 3. transformation - Transformations de Texte

**Description :** Manipule et transforme des chaînes de caractères.

**Fonctions disponibles :**

#### uppercase()
Convertit en MAJUSCULES.
```python
formula = "uppercase(name)"
input_data = {"name": "Jean Dupont"}
result = engine.execute("transformation", formula, input_data)
# Résultat : "JEAN DUPONT"
```

#### lowercase()
Convertit en minuscules.
```python
formula = "lowercase(name)"
input_data = {"name": "JEAN DUPONT"}
result = engine.execute("transformation", formula, input_data)
# Résultat : "jean dupont"
```

#### concat()
Concatène plusieurs chaînes.
```python
formula = "concat(first_name, ' ', last_name)"
input_data = {"first_name": "Jean", "last_name": "Dupont"}
result = engine.execute("transformation", formula, input_data)
# Résultat : "Jean Dupont"
```

#### trim()
Supprime les espaces au début et à la fin.
```python
formula = "trim(text)"
input_data = {"text": "  Jean Dupont  "}
result = engine.execute("transformation", formula, input_data)
# Résultat : "Jean Dupont"
```

#### remove_spaces()
Supprime tous les espaces.
```python
formula = "remove_spaces(text)"
input_data = {"text": "CTR 2026 001"}
result = engine.execute("transformation", formula, input_data)
# Résultat : "CTR2026001"
```

#### date_format()
Convertit le format de date.
```python
formula = "date_format(date, 'DD/MM/YYYY', 'YYYY-MM-DD')"
input_data = {"date": "27/01/2026"}
result = engine.execute("transformation", formula, input_data)
# Résultat : "2026-01-27"
```

#### round()
Arrondit un nombre.
```python
formula = "round(amount 2)"
input_data = {"amount": 1500.5567}
result = engine.execute("transformation", formula, input_data)
# Résultat : 1500.56
```

---

### 4. lookup - Tables de Correspondance

**Description :** Recherche dans des tables de référence (lookup tables).

**Syntaxe :**
```
table_name[key_field]
```

**Exemples :**
```python
# Préparer les lookup tables
engine.register_lookup_table("country_code_map", {
    "TN": "TUN",
    "FR": "FRA",
    "US": "USA"
})

engine.register_lookup_table("currency_symbol", {
    "TND": "د.ت",
    "EUR": "€",
    "USD": "$"
})

# Exemple 1 : Code pays
formula = "country_code_map[country]"
input_data = {"country": "TN"}
result = engine.execute("lookup", formula, input_data)
# Résultat : "TUN"

# Exemple 2 : Symbole devise
formula = "currency_symbol[currency]"
input_data = {"currency": "TND"}
result = engine.execute("lookup", formula, input_data)
# Résultat : "د.ت"

# Exemple 3 : Taux de change
engine.register_lookup_table("exchange_rate", {
    "TND": 0.304,
    "USD": 1.000,
    "EUR": 1.050
})

formula = "exchange_rate[currency]"
input_data = {"currency": "TND"}
result = engine.execute("lookup", formula, input_data)
# Résultat : 0.304
```

**Lookup Tables disponibles :**
- `country_code_map` - Codes pays (ISO2 → ISO3)
- `currency_symbol` - Symboles de devises
- `exchange_rate` - Taux de change
- Autres tables personnalisées...

---

### 5. validation - Validations

**Description :** Valide la conformité des données.

**Fonctions disponibles :**

#### iban_validate()
Valide un IBAN pour un pays donné.
```python
formula = "iban_validate(iban, 'TN')"
input_data = {"iban": "TN5914207490000021879544"}
result = engine.execute("validation", formula, input_data)
# Résultat : True

input_data = {"iban": "INVALID"}
result = engine.execute("validation", formula, input_data)
# Résultat : False
```

#### email_validate()
Valide un format email.
```python
formula = "email_validate(email)"
input_data = {"email": "jean@example.com"}
result = engine.execute("validation", formula, input_data)
# Résultat : True

input_data = {"email": "invalid-email"}
result = engine.execute("validation", formula, input_data)
# Résultat : False
```

---

## 🔄 Utilisation dans le Système

### 1. Avec MappingFormulas
```python
# Créer un mapping avec formule
mapping = MappingFormula(
    name="Convert Amount to EUR",
    source_path="Transaction.Amount",
    target_path="Payment.AmountEUR",
    transformation_type="arithmetic",
    transformation_rule="amount * 0.304"
)
```

### 2. Application lors de la Transformation
```python
from app.services.formula_engine import FormulaEngine

engine = FormulaEngine()

# Extraire valeur source
source_value = get_value_by_path(source_data, mapping.source_path)
# source_value = 1500.50

# Préparer input pour la formule
formula_input = {"amount": source_value}

# Exécuter la formule
result = engine.execute(
    formula_type=mapping.transformation_type,
    formula_expression=mapping.transformation_rule,
    input_data=formula_input
)
# result = 456.152

# Injecter dans la cible
set_value_by_path(target_data, mapping.target_path, result)
```

---

## 📊 MappingRules - Catalogue de Règles

### Structure d'une Règle
```python
{
  "rule_id": "RULE_001",
  "rule_name": "Convert TND to EUR",
  "formula_type": "arithmetic",
  "formula_expression": "amount * 0.304",
  "input_fields": ["amount"],
  "output_field": "amount_eur",
  "output_type": "decimal",
  "description": "Convertit TND vers EUR au taux 0.304",
  "example_input": {"amount": 1500.50},
  "example_output": 456.152
}
```

### Règles Prédéfinies (Dataset)

Le système est livré avec **20 règles prédéfinies** dans `backend/dataset/mapping_rules_pain001.csv` :

1. **RULE_001** - Convert TND to EUR
2. **RULE_002** - Date Format ISO
3. **RULE_003** - Concatenate Full Name
4. **RULE_004** - Uppercase Text
5. **RULE_005** - IBAN Validation
6. **RULE_006** - Transaction Classification
7. **RULE_007** - Amount Classification
8. **RULE_008** - Phone Format Tunisia
9. **RULE_009** - Email Validation
10. **RULE_010** - Country Code Lookup
...

---

## ⚠️ Gestion des Erreurs

### Erreurs Courantes

**1. Variable non trouvée**
```python
formula = "amount * 0.304"
input_data = {"montant": 1500}  # Mauvais nom !
# Erreur : KeyError 'amount'
```

**2. Division par zéro**
```python
formula = "amount / divisor"
input_data = {"amount": 1000, "divisor": 0}
# Erreur : ZeroDivisionError
```

**3. Type incompatible**
```python
formula = "amount * rate"
input_data = {"amount": "abc", "rate": 0.304}
# Erreur : TypeError
```

### Try-Catch Recommandé
```python
try:
    result = engine.execute(formula_type, formula, input_data)
except ValueError as e:
    logger.error(f"Invalid formula: {e}")
except KeyError as e:
    logger.error(f"Missing field: {e}")
except Exception as e:
    logger.error(f"Formula execution failed: {e}")
```

---

## 🧪 Tests

### Test Unitaire Arithmetic
```python
def test_arithmetic():
    engine = FormulaEngine()
    
    # Simple multiplication
    result = engine.execute(
        "arithmetic",
        "amount * 0.304",
        {"amount": 1500.50}
    )
    assert result == 456.152
    
    # Complex expression
    result = engine.execute(
        "arithmetic",
        "(amount + fees) * rate",
        {"amount": 1000, "fees": 50, "rate": 1.05}
    )
    assert result == 1102.5
```

### Test Unitaire Conditional
```python
def test_conditional():
    engine = FormulaEngine()
    
    # IF simple
    result = engine.execute(
        "conditional",
        "IF country='TN' THEN 'DOMESTIC' ELSE 'INTERNATIONAL'",
        {"country": "TN"}
    )
    assert result == "DOMESTIC"
    
    # CASE WHEN
    result = engine.execute(
        "conditional",
        "CASE WHEN amount < 1000 THEN 'LOW' ELSE 'HIGH'",
        {"amount": 1500}
    )
    assert result == "HIGH"
```

---

## 💡 Bonnes Pratiques

### 1. Nommer les Champs Clairement
✅ **Bon :**
```python
formula = "amount * exchange_rate"
input_data = {"amount": 1500, "exchange_rate": 0.304}
```

❌ **Mauvais :**
```python
formula = "a * er"
input_data = {"a": 1500, "er": 0.304}
```

### 2. Documenter les Règles
Toujours fournir `description` et exemples.

### 3. Valider les Inputs
Vérifier que toutes les variables nécessaires sont présentes.

### 4. Utiliser les Lookup Tables
Pour les correspondances répétitives (codes pays, devises, etc.).

---

## 🔮 Évolutions Futures

### Fonctions Additionnelles
- `substring()` - Extraction de sous-chaînes
- `replace()` - Remplacement de texte
- `split()` - Découpage de chaînes
- `regex_match()` - Expressions régulières

### Support d'Expressions Complexes
- Fonctions imbriquées
- Variables temporaires
- Boucles (pour arrays)

### Performance
- Cache des résultats
- Compilation des formules
- Exécution parallèle

---

## 🔗 Voir Aussi

- [Data Types](data_types.md) - Types de données
- [Hierarchy System](hierarchy_system.md) - Chemins hiérarchiques
- [MappingFormulas API](../api/mapping_formulas.md) - Utilisation via API
```

**Sauvegardez : `backend/docs/formula_engine.md`**

---

## 📄 7. structure_types.md (Déjà Créé)

**Vous l'avez déjà créé plus tôt ! ✅**

---

## 🎉 TERMINÉ ! 7 Fichiers de Documentation Complets !
```
✅ README.md (racine)
✅ backend/docs/structure_types.md
✅ backend/docs/data_types.md
✅ backend/docs/categories.md
✅ backend/docs/iso20022_pain001.md
✅ backend/docs/hierarchy_system.md
✅ backend/docs/formula_engine.md