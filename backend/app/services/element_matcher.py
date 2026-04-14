from typing import List, Dict, Any
import logging
from sqlalchemy.orm import Session
from app.models.standard_element import StandardElement

logger = logging.getLogger(__name__)


class ElementMatcher:
    """
    Service pour matcher des colonnes avec des StandardElements
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.standard_elements = self._load_elements()
    
    def _load_elements(self) -> List[StandardElement]:
        """Charge tous les StandardElements actifs"""
        return self.db.query(StandardElement).filter(
            StandardElement.is_active == True
        ).all()
    
    def match_columns(
        self, 
        columns: List[str], 
        sample_data: List[Dict[str, Any]] = None
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Trouve les meilleurs StandardElements pour chaque colonne
        
        Args:
            columns: Liste des noms de colonnes
            sample_data: Données d'exemple (optionnel)
            
        Returns:
            Dict avec suggestions par colonne
            {
                "column_name": [
                    {
                        "element": StandardElement,
                        "confidence": 95,
                        "reason": "Exact name match"
                    },
                    ...
                ]
            }
        """
        suggestions = {}
        
        for column in columns:
            column_suggestions = self._find_matches(column, sample_data)
            suggestions[column] = column_suggestions[:3]  # Top 3
        
        return suggestions
    
    def _find_matches(
        self, 
        column_name: str, 
        sample_data: List[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Trouve les StandardElements correspondants pour une colonne
        
        Returns:
            Liste de suggestions triées par confidence (desc)
        """
        matches = []
        column_lower = column_name.lower().strip()
        
        for element in self.standard_elements:
            confidence, reason = self._calculate_confidence(
                column_name,
                column_lower,
                element,
                sample_data
            )
            
            if confidence > 0:
                matches.append({
                    "element_id": element.element_id,
                    "element_name": element.element_name,
                    "category": element.category,
                    "source_path": element.source_path,
                    "target_path": element.target_path,
                    "data_type": element.data_type,
                    "structure_type": element.structure_type,
                    "confidence": confidence,
                    "reason": reason
                })
        
        # Trier par confidence décroissant
        matches.sort(key=lambda x: x["confidence"], reverse=True)
        
        return matches
    
    def _calculate_confidence(
        self,
        column_name: str,
        column_lower: str,
        element: StandardElement,
        sample_data: List[Dict[str, Any]] = None
    ) -> tuple[int, str]:
        """
        Calcule le score de confiance (0-100) et la raison
        
        Returns:
            (confidence_score, reason)
        """
        confidence = 0
        reasons = []
        
        # 1. Match exact du nom (100%)
        if column_lower == element.element_id.lower():
            return 100, "Exact ID match"
        
        element_name_lower = element.element_name.lower()
        
        if column_lower == element_name_lower:
            return 95, "Exact name match"
        
        # 2. Match partiel du nom (50-80%)
        if column_lower in element_name_lower:
            confidence += 70
            reasons.append("Name contains column")
        elif element_name_lower in column_lower:
            confidence += 60
            reasons.append("Column contains element name")
        
        # 3. Match des mots-clés (20-40%)
        column_words = set(column_lower.replace('_', ' ').replace('.', ' ').split())
        element_words = set(element_name_lower.replace('_', ' ').split())
        
        common_words = column_words & element_words
        if common_words:
            word_score = min(len(common_words) * 15, 40)
            confidence += word_score
            reasons.append(f"Common words: {', '.join(common_words)}")
        
        # 4. Match des patterns courants (10-30%)
        patterns = {
            'name': ['name', 'nom', 'fullname', 'full_name'],
            'first': ['first', 'prenom', 'firstname', 'first_name', 'given'],
            'last': ['last', 'nom', 'lastname', 'last_name', 'family'],
            'email': ['email', 'mail', 'e-mail', 'courriel'],
            'phone': ['phone', 'tel', 'telephone', 'mobile', 'cell'],
            'address': ['address', 'adresse', 'street', 'rue'],
            'city': ['city', 'ville', 'town'],
            'country': ['country', 'pays', 'nation'],
            'date': ['date', 'time', 'datetime', 'timestamp'],
            'amount': ['amount', 'montant', 'price', 'prix', 'value'],
            'currency': ['currency', 'devise', 'ccy'],
            'iban': ['iban', 'account', 'compte'],
            'id': ['id', 'identifier', 'reference', 'ref']
        }
        
        for pattern_name, pattern_keywords in patterns.items():
            if any(keyword in column_lower for keyword in pattern_keywords):
                if any(keyword in element_name_lower for keyword in pattern_keywords):
                    confidence += 25
                    reasons.append(f"Pattern match: {pattern_name}")
                    break
        
        # 5. Match du type de données (10%)
        if sample_data and len(sample_data) > 0:
            sample_value = sample_data[0].get(column_name)
            if sample_value is not None:
                inferred_type = self._infer_type(sample_value)
                if inferred_type == element.data_type:
                    confidence += 10
                    reasons.append(f"Type match: {inferred_type}")
        
        # 6. Bonus pour les chemins hiérarchiques
        if element.source_path and '.' in column_name:
            # Si la colonne a une notation hiérarchique
            if column_name.lower() in element.source_path.lower():
                confidence += 15
                reasons.append("Hierarchical path match")
        
        # Limiter à 100
        confidence = min(confidence, 100)
        
        reason = "; ".join(reasons) if reasons else "No strong match"
        
        return confidence, reason
    
    def _infer_type(self, value: Any) -> str:
        """Infère le type de données à partir d'un échantillon"""
        if isinstance(value, bool):
            return "boolean"
        elif isinstance(value, int):
            return "integer"
        elif isinstance(value, float):
            return "decimal"
        elif isinstance(value, str):
            # Tenter de détecter des patterns
            value_lower = value.lower().strip()
            
            # Email
            if '@' in value and '.' in value:
                return "string"  # email type
            
            # Date patterns
            if any(sep in value for sep in ['/', '-']) and len(value) >= 8:
                try:
                    # Simple check for date-like format
                    parts = value.replace('/', '-').split('-')
                    if len(parts) == 3 and all(p.isdigit() for p in parts):
                        return "date"
                except:
                    pass
            
            return "string"
        else:
            return "string"
    
    def create_suggested_mappings(
        self,
        suggestions: Dict[str, List[Dict[str, Any]]],
        message_description_id: int,
        confidence_threshold: int = 70
    ) -> List[Dict[str, Any]]:
        """
        Crée des mappings suggérés basés sur les suggestions
        avec un seuil de confiance minimum
        
        Args:
            suggestions: Résultat de match_columns
            message_description_id: ID du MessageDescription
            confidence_threshold: Seuil minimum de confiance (défaut: 70%)
            
        Returns:
            Liste de mappings à créer
        """
        mappings = []
        
        for column_name, column_suggestions in suggestions.items():
            if not column_suggestions:
                continue
            
            # Prendre la meilleure suggestion si confiance >= seuil
            best_suggestion = column_suggestions[0]
            
            if best_suggestion["confidence"] >= confidence_threshold:
                mapping = {
                    "message_description_id": message_description_id,
                    "name": f"Auto: {column_name} → {best_suggestion['element_name']}",
                    "source_path": column_name,
                    "target_path": best_suggestion["target_path"] or best_suggestion["element_name"],
                    "transformation_type": "direct",
                    "transformation_rule": "Direct copy with auto-suggestion",
                    "example_input": None,
                    "example_output": None
                }
                mappings.append(mapping)
        
        return mappings