# Smart Mapping Platform

**Plateforme intelligente de transformation et mapping de données bancaires avec IA**

🎓 **Projet de Fin d'Études (PFE) - 2026**  
📍 **Vermeg - Tunis, Tunisie**  
👨‍💻 **Développé par : Bilel Souelmi**

---

## 🎯 Objectif

Automatiser la transformation de messages financiers entre différents formats (ISO 20022, formats propriétaires) en utilisant l'intelligence artificielle pour suggérer des mappings intelligents basés sur des catalogues de données standardisés.

---

## ✨ Fonctionnalités Principales

### 🤖 Intelligence Artificielle
- **Analyse automatique** des fichiers uploadés (CSV, XML, JSON, Excel)
- **Détection de structure hiérarchique** à 3 niveaux maximum
- **Suggestions de mappings** basées sur RAG (Retrieval-Augmented Generation)
- **Ollama** pour l'analyse sémantique

### 📊 Gestion des Données
- **Catalogue de 28+ éléments standards** basés sur ISO 20022 pain.001.001.12
- **Support de structures MAP/HMAP** (structures fixes et dynamiques)
- **5 types de formules** : arithmetic, conditional, transformation, lookup, validation
- **Hiérarchie à 3 niveaux** pour structures complexes

### 🔄 Transformation
- **Mappings configurables** source → target
- **Moteur de formules** (FormulaEngine) avec support de règles métier
- **Génération d'outputs** JSON structurés
- **Téléchargement** des fichiers transformés

### 🔐 Sécurité
- **Authentification JWT** avec tokens sécurisés
- **Gestion des utilisateurs** et sessions
- **Hash Argon2** pour les mots de passe

---

## 🏗️ Architecture

### Stack Technique

**Backend :**
- 🐍 FastAPI (Python 3.11)
- 🗄️ PostgreSQL 16
- 🧠 Ollama (qwen2.5:3b)
- 🔍 ChromaDB (RAG)
- 🐳 Docker + Docker Compose

**Frontend :**
- ⚛️ React 18
- 🎨 Framer Motion (animations)
- 📊 Recharts (graphiques)
- 🎯 React Router v6

### Architecture 3 Niveaux
```
┌─────────────────────────────────────────┐
│  Niveau 1 : MessageDescription          │
│  (Fichier source + métadonnées)         │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│  Niveau 2 : StandardElements            │
│  (Catalogue de 28+ éléments ISO 20022)  │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│  Niveau 3 : MappingFormulas             │
│  (Règles de transformation)             │
└─────────────────────────────────────────┘
```

---

## 🚀 Installation & Lancement

### Prérequis
- Docker Desktop
- Git
- 8GB RAM minimum
- Port 8000, 5173, 5432, 11434 disponibles

### Installation
```bash
# Cloner le repository
git clone https://github.com/bilelsouelmi/smart-mapping-pfe.git
cd smart-mapping-pfe

# Lancer avec Docker Compose
docker-compose up --build

# Le système démarre sur :
# - Backend API : http://localhost:8000
# - Frontend : http://localhost:5173
# - Swagger Docs : http://localhost:8000/docs
# - PostgreSQL : localhost:5432
# - Ollama : http://localhost:11434
```

### Premier Lancement
```bash
# Importer le dataset ISO 20022
docker-compose exec backend python scripts/import_dataset.py

# Créer un compte utilisateur
# Via l'interface : http://localhost:5173/register
```

---

## 📖 Documentation

- 📘 [Types de Structure](backend/docs/structure_types.md) - MAP, HMAP, simple, array, object
- 📗 [Types de Données](backend/docs/data_types.md) - string, integer, decimal, date, etc.
- 📙 [Catégories](backend/docs/categories.md) - Header, Debtor, Creditor, etc.
- 📕 [ISO 20022 pain.001](backend/docs/iso20022_pain001.md) - Standard utilisé
- 📔 [Système Hiérarchique](backend/docs/hierarchy_system.md) - 3 niveaux
- 📓 [Formula Engine](backend/docs/formula_engine.md) - Moteur de formules

---

## 🗄️ Base de Données

### Tables Principales
```
users                  → Utilisateurs authentifiés
message_descriptions   → Fichiers uploadés + métadonnées
standard_elements      → Catalogue ISO 20022 (28+ éléments)
mapping_formulas       → Règles de transformation
transformation_jobs    → Historique des transformations
validation_reports     → Rapports de validation
knowledge_base_entries → Base de connaissances RAG
```

---

## 🔌 API Endpoints

### Authentication
```
POST   /api/auth/register      Créer un compte
POST   /api/auth/login         Se connecter
POST   /api/auth/refresh       Rafraîchir le token
```

### Files
```
POST   /api/files/analyze      Analyser un fichier
GET    /api/files/             Lister les fichiers
```

### StandardElements
```
GET    /api/standard-elements/                Liste tous les éléments
GET    /api/standard-elements/search?q=...   Recherche
GET    /api/standard-elements/categories     Liste des catégories
GET    /api/standard-elements/{id}           Détail d'un élément
POST   /api/standard-elements/               Créer un élément
PUT    /api/standard-elements/{id}           Modifier
DELETE /api/standard-elements/{id}           Supprimer
```

### MappingFormulas
```
GET    /api/mapping-formulas/      Liste des mappings
POST   /api/mapping-formulas/      Créer un mapping
PUT    /api/mapping-formulas/{id}  Modifier
DELETE /api/mapping-formulas/{id}  Supprimer
```

### Transformation
```
POST   /api/transform/apply-mapping/{id}     Appliquer un mapping
GET    /api/transform/outputs                Liste des outputs
GET    /api/transform/download/{filename}    Télécharger
```

**Documentation complète :** http://localhost:8000/docs

---

## 📊 Dataset

### StandardElements (28 éléments)

Basé sur **ISO 20022 pain.001.001.12** (Customer Credit Transfer Initiation)

**Catégories :**
- Header (4) : Message ID, Date, Transaction Count
- Payment (3) : Payment Info, Method, Date
- Debtor (7) : Nom, Adresse, IBAN, BIC
- Creditor (6) : Nom, Adresse, IBAN, BIC
- Transaction (5) : Montant, Devise, IDs
- Remittance (1) : Information de remise

**Format :** CSV dans `backend/dataset/standard_elements_pain001.csv`

---

## 🧪 Tests
```bash
# Tests backend
docker-compose exec backend pytest

# Tests API via Swagger
http://localhost:8000/docs

# Tests manuels
1. Register/Login
2. Upload fichier CSV
3. Créer mapping
4. Transformer
5. Télécharger output
```

---

## 🛠️ Développement

### Structure du Projet
```
smart-mapping/
├── backend/
│   ├── app/
│   │   ├── models/          # Modèles SQLAlchemy
│   │   ├── schemas/         # Schemas Pydantic
│   │   ├── api/routes/      # Endpoints API
│   │   ├── services/        # Services métier
│   │   └── core/            # Config, deps
│   ├── dataset/             # Données CSV
│   ├── scripts/             # Scripts utilitaires
│   └── docs/                # Documentation
├── frontend/
│   └── src/
│       ├── pages/           # Pages React
│       ├── components/      # Composants
│       └── contexts/        # Context API
└── docker-compose.yml
```

### Commandes Utiles
```bash
# Backend
docker-compose exec backend bash           # Shell backend
docker-compose exec backend alembic upgrade head  # Migrations

# Database
docker-compose exec backend psql -h postgres -U smart_mapping_user -d smart_mapping

# Logs
docker-compose logs -f backend
docker-compose logs -f frontend
```

---

## 🎓 Contexte PFE

**Entreprise :** Vermeg (Leader solutions bancaires et assurance)  
**Période :** Janvier - Juin 2026  
**Encadrant :** [Nom Superviseur]  
**Jury :** [À définir]

### Problématique

Les institutions financières doivent constamment transformer des données entre différents formats (ISO 20022, SWIFT, formats propriétaires). Ce processus est :
- ⏰ **Chronophage** : Mapping manuel pour chaque nouveau format
- 🐛 **Source d'erreurs** : Risques de mauvaise transformation
- 📈 **Non scalable** : Difficulté à gérer des centaines de mappings

### Solution

Plateforme intelligente qui :
1. **Analyse automatiquement** la structure des fichiers
2. **Suggère des mappings** basés sur l'IA et un catalogue standard
3. **Applique des règles de transformation** configurables
4. **Génère des outputs** validés et téléchargeables

### Valeur Ajoutée

- ⚡ **Réduction 80%** du temps de configuration
- ✅ **Qualité accrue** grâce à la validation automatique
- 🔄 **Réutilisation** des mappings via catalogue
- 🤖 **Amélioration continue** via apprentissage IA

---

## 📈 Roadmap

### ✅ Phase 1 : Infrastructure (Complété)
- Docker + FastAPI + React
- Auth JWT
- Upload multi-format
- Base PostgreSQL

### ✅ Phase 2 : StandardElements (Complété)
- Catalogue ISO 20022
- API CRUD
- Structure MAP/HMAP
- FormulaEngine

### 🔄 Phase 3 : Intelligence (En cours)
- RAG avec ChromaDB
- Suggestions automatiques
- Confidence scoring

### 📅 Phase 4 : Frontend Avancé (À venir)
- Tree view hiérarchique
- Drag & drop mappings
- Dashboard analytics

### 📅 Phase 5 : Production (À venir)
- Tests complets
- Documentation utilisateur
- Déploiement
- Présentation jury

---

## 📞 Contact

**Bilel Souelmi**  
📧 Email : bilelswelmi@gmail.com  
🔗 GitHub : [bilelsouelmi](https://github.com/bilelsouelmi)  
💼 LinkedIn : [Bilel Souelmi](https://linkedin.com/in/bilel-souelmi)

---

## 📄 Licence

**Projet Académique - PFE 2026**  
Propriété de Vermeg et l'auteur.

---

## 🙏 Remerciements

- **Vermeg** pour l'opportunité de stage
- **[Nom Superviseur]** pour l'encadrement
- **Anthropic (Claude)** pour l'assistance technique
- **Communauté Open Source** pour les outils utilisés

---

**⭐ Si ce projet vous intéresse, n'hésitez pas à le star sur GitHub !**