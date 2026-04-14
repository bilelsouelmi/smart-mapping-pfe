# Système Hiérarchique à 3 Niveaux

Documentation du système de parsing et gestion des structures hiérarchiques dans Smart Mapping Platform.

---

## 🎯 Vue d'Ensemble

Le système Smart Mapping supporte des **structures de données hiérarchiques jusqu'à 3 niveaux de profondeur**. Cela permet de gérer des messages complexes comme ISO 20022, JSON imbriqués, ou XML hiérarchiques.

---

## 📊 Concept de Hiérarchie

### Qu'est-ce qu'un Niveau ?

**Un niveau = un niveau d'imbrication dans la structure**
```json
{
  "Body": {                    // Niveau 1
    "Client": {                // Niveau 2
      "FirstName": "Jean"      // Niveau 3
    }
  }
}
```

**Path hiérarchique :** `Body.Client.FirstName`  
**Profondeur :** 3 niveaux

---

## 🏗️ Les 3 Niveaux Expliqués

### Niveau 1 : Sections Principales
**Rôle :** Organisation de haut niveau du message

**Exemples :**
- `Header` - En-tête du message
- `Body` - Corps du message
- `Footer` - Pied de message
- `Metadata` - Métadonnées
```json
{
  "Header": {...},
  "Body": {...},
  "Footer": {...}
}
```

---

### Niveau 2 : Entités Métier
**Rôle :** Objets ou concepts métier

**Exemples :**
- `Client` - Information client
- `Transaction` - Détails transaction
- `Account` - Informations compte
- `Address` - Adresse
```json
{
  "Body": {
    "Client": {...},
    "Transaction": {...},
    "Account": {...}
  }
}
```

---

### Niveau 3 : Attributs Finaux
**Rôle :** Valeurs concrètes (champs terminaux)

**Exemples :**
- `FirstName` - Prénom
- `Amount` - Montant
- `IBAN` - Numéro de compte
- `Date` - Date
```json
{
  "Body": {
    "Client": {
      "FirstName": "Jean",
      "LastName": "Dupont",
      "BirthDate": "1985-03-15"
    }
  }
}
```

---

## 🔢 Comptage des Niveaux

### Méthode par Points
Le nombre de points (`.`) dans le path indique le nombre de séparations.

**Exemples :**

| Path | Points | Niveaux |
|------|--------|---------|
| `Name` | 0 | 1 |
| `Client.Name` | 1 | 2 |
| `Body.Client.Name` | 2 | 3 |
| `Header.Message.Type.Code` | 3 | 4 ❌ (trop profond) |

**Validation :**
```python
def count_levels(path: str) -> int:
    return len(path.split('.'))

# Exemples
count_levels("Body.Client.FirstName")  # 3 ✅
count_levels("A.B.C.D")                 # 4 ❌
```

---

## 📝 Représentation dans le Système

### Dans StandardElements
```python
{
  "element_id": "PERS_FNAME",
  "source_path": "Body.Client.FirstName",    # 3 niveaux
  "target_path": "Person.FirstName",          # 2 niveaux
  "iso20022_path": "pain.001/Dbtr/Nm"        # Référence ISO
}
```

### Dans MappingFormulas
```python
{
  "name": "Map First Name",
  "source_path": "Body.Client.Identity.FirstName",  # 4 parties
  "target_path": "Customer.Person.FirstName",       # 3 parties
  "source_level": 4,  # Calculé automatiquement
  "target_level": 3
}
```

---

## 🔧 HierarchyParser - Service de Parsing

### Fonctionnalités

**1. parse_structure()**
Parse une structure JSON/XML et extrait tous les chemins.
```python
from app.services.hierarchy_parser import HierarchyParser

parser = HierarchyParser()

data = {
  "Body": {
    "Client": {
      "FirstName": "Jean",
      "LastName": "Dupont"
    }
  }
}

paths = parser.parse_structure(data, max_level=3)

# Résultat :
# [
#   {"path": "Body", "level": 1, "is_leaf": False},
#   {"path": "Body.Client", "level": 2, "is_leaf": False},
#   {"path": "Body.Client.FirstName", "level": 3, "is_leaf": True, "sample_value": "Jean"},
#   {"path": "Body.Client.LastName", "level": 3, "is_leaf": True, "sample_value": "Dupont"}
# ]
```

**2. get_value_by_path()**
Récupère une valeur via son chemin.
```python
value = parser.get_value_by_path(data, "Body.Client.FirstName")
# Résultat : "Jean"
```

**3. set_value_by_path()**
Définit une valeur via son chemin.
```python
parser.set_value_by_path(data, "Body.Client.Age", 35)
# data["Body"]["Client"]["Age"] = 35
```

**4. build_tree()**
Construit un arbre hiérarchique pour affichage UI.
```python
tree = parser.build_tree(paths)
# Structure d'arbre pour visualisation
```

---

## 📋 Formats Supportés

### JSON Hiérarchique ✅
```json
{
  "Level1": {
    "Level2": {
      "Level3": "value"
    }
  }
}
```

### XML Hiérarchique ✅
```xml
<Level1>
  <Level2>
    <Level3>value</Level3>
  </Level2>
</Level1>
```

### CSV avec Notation ✅
Headers avec points pour indiquer la hiérarchie.
```csv
Body.Client.FirstName,Body.Client.LastName,Body.Account.IBAN
Jean,Dupont,TN59...
```

### Excel ✅
Même principe que CSV (notation avec points).

---

## 🎨 Visualisation UI

### Tree View (Frontend)
```
📄 Message
├─📁 Body (Niveau 1)
│  ├─📁 Client (Niveau 2)
│  │  ├─📄 FirstName: "Jean" (Niveau 3)
│  │  ├─📄 LastName: "Dupont" (Niveau 3)
│  │  └─📄 BirthDate: "1985-03-15" (Niveau 3)
│  └─📁 Account (Niveau 2)
│     ├─📄 IBAN: "TN59..." (Niveau 3)
│     └─📄 Currency: "TND" (Niveau 3)
└─📁 Header (Niveau 1)
   ├─📄 MessageId: "MSG-001" (Niveau 2)
   └─📄 Date: "2026-01-27" (Niveau 2)
```

---

## ⚠️ Contraintes et Limites

### Maximum 3 Niveaux

**Pourquoi cette limite ?**
1. **Simplicité** - Plus facile à comprendre et maintenir
2. **Performance** - Parsing plus rapide
3. **Standards** - ISO 20022 utilise généralement 2-3 niveaux
4. **UI/UX** - Plus de 3 niveaux devient difficile à visualiser

### Validation Automatique

**Le système rejette automatiquement :**
```python
# ❌ 4 niveaux - Rejeté
"Body.Client.Identity.FirstName"

# ✅ 3 niveaux - Accepté
"Body.Client.FirstName"
```

**Message d'erreur :**
```json
{
  "error": "Path cannot exceed 3 levels. Got 4 levels: Body.Client.Identity.FirstName"
}
```

---

## 🔄 Cas d'Usage Réels

### 1. Upload et Analyse
```python
# User uploade client_data.json
# Système parse automatiquement
paths = HierarchyParser.parse_structure(json_data, max_level=3)

# Détecte :
# - Body.Client.FirstName (3 niveaux) ✅
# - Body.Client.LastName (3 niveaux) ✅
# - Body.Account.IBAN (3 niveaux) ✅
```

### 2. Création de Mapping
```python
# User crée un mapping
{
  "source_path": "Body.Client.FirstName",     # 3 niveaux
  "target_path": "Customer.Person.FirstName", # 3 niveaux
  "transformation_type": "direct"
}
```

### 3. Transformation
```python
# Système applique le mapping
source_value = get_value_by_path(source_data, "Body.Client.FirstName")
# source_value = "Jean"

set_value_by_path(target_data, "Customer.Person.FirstName", source_value)
# target_data["Customer"]["Person"]["FirstName"] = "Jean"
```

---

## 💡 Bonnes Pratiques

### Nommage des Paths

✅ **Recommandé :**
```
Body.Client.FirstName
Header.Message.Id
Transaction.Amount.Value
```

❌ **À éviter :**
```
body.client.firstname         # Pas de capitalisation cohérente
Body_Client_FirstName         # Underscores au lieu de points
BodyClientFirstName           # Pas de séparation
```

### Organisation Logique

**Niveau 1 :** Sections techniques/structurelles
```
Header, Body, Footer, Metadata
```

**Niveau 2 :** Entités métier
```
Client, Transaction, Account, Address
```

**Niveau 3 :** Attributs concrets
```
FirstName, Amount, IBAN, Date
```

---

## 🔗 Intégration avec Autres Composants

### Avec StandardElements
```python
StandardElement(
  element_id="PERS_FNAME",
  source_path="Body.Client.FirstName",  # 3 niveaux
  structure_type="simple"
)
```

### Avec MappingFormulas
```python
MappingFormula(
  source_path="Body.Client.FirstName",      # Auto-validation 3 niveaux
  target_path="Customer.Person.FirstName",
  source_level=3,  # Calculé automatiquement
  target_level=3
)
```

### Avec FormulaEngine
```python
# Le FormulaEngine utilise les paths pour extraire/injecter des valeurs
value = get_value_by_path(data, mapping.source_path)
transformed_value = apply_formula(value, mapping.formula)
set_value_by_path(output, mapping.target_path, transformed_value)
```

---

## 📊 Exemples Complets

### Exemple 1 : Message ISO 20022

**Structure :**
```json
{
  "GrpHdr": {
    "MsgId": "MSG-001",
    "CreDtTm": "2026-01-27T10:00:00Z"
  },
  "PmtInf": {
    "Dbtr": {
      "Nm": "Jean Dupont"
    }
  }
}
```

**Paths détectés :**
- `GrpHdr.MsgId` (2 niveaux) ✅
- `GrpHdr.CreDtTm` (2 niveaux) ✅
- `PmtInf.Dbtr.Nm` (3 niveaux) ✅

### Exemple 2 : CSV avec Notation

**Fichier CSV :**
```csv
Client.Identity.FirstName,Client.Identity.LastName,Client.Contact.Email
Jean,Dupont,jean@email.com
Marie,Martin,marie@email.com
```

**Paths détectés :**
- `Client.Identity.FirstName` (3 niveaux) ✅
- `Client.Identity.LastName` (3 niveaux) ✅
- `Client.Contact.Email` (3 niveaux) ✅

---

## 🧪 Tests et Validation

### Test de Profondeur
```python
def test_max_depth():
    # Valid
    assert count_levels("A.B.C") == 3  # ✅
    
    # Invalid
    try:
        validate_path("A.B.C.D")
    except ValueError as e:
        assert "cannot exceed 3 levels" in str(e)  # ✅
```

### Test de Parsing
```python
def test_parse_structure():
    data = {"A": {"B": {"C": "value"}}}
    paths = parser.parse_structure(data, max_level=3)
    
    assert len(paths) == 4  # A, A.B, A.B.C, et les métadonnées
    assert paths[-1]["path"] == "A.B.C"
    assert paths[-1]["level"] == 3
    assert paths[-1]["is_leaf"] == True
```

---

## 🔮 Évolutions Futures

### Niveau 4+ (Si Nécessaire)
Si le besoin se présente, le système peut être étendu à 4+ niveaux en modifiant :
- `max_level` dans HierarchyParser
- Validation dans les schemas Pydantic
- UI pour supporter plus de profondeur

### Types de Structure
Combinaison avec `structure_type` :
- `simple` - Valeur scalaire
- `map` - Structure fixe
- `hmap` - Structure dynamique
- `array` - Tableau

---

## 🔗 Voir Aussi

- [Types de Structure](structure_types.md) - MAP, HMAP, simple
- [ISO 20022 pain.001](iso20022_pain001.md) - Exemple réel
- [Formula Engine](formula_engine.md) - Utilisation des paths