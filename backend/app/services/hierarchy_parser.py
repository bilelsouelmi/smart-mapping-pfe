import json
from typing import Dict, List, Any, Tuple


class HierarchyParser:
    """
    Service pour parser et analyser les structures hiérarchiques à 3 niveaux
    """
    
    @staticmethod
    def parse_structure(data: Any, parent_path: str = "", level: int = 0, max_level: int = 3) -> List[Dict[str, Any]]:
        """
        Parse une structure JSON/dict et retourne tous les chemins avec leurs niveaux
        
        Args:
            data: Structure à parser (dict ou list)
            parent_path: Chemin parent actuel
            level: Niveau actuel de profondeur
            max_level: Niveau maximum autorisé
            
        Returns:
            Liste de chemins avec leurs métadonnées
        """
        paths = []
        
        if level > max_level:
            return paths
        
        if isinstance(data, dict):
            for key, value in data.items():
                current_path = f"{parent_path}.{key}" if parent_path else key
                
                # Si c'est une valeur finale (pas dict/list)
                if not isinstance(value, (dict, list)):
                    paths.append({
                        "path": current_path,
                        "level": level + 1,
                        "type": type(value).__name__,
                        "sample_value": str(value)[:100],  # Limiter à 100 chars
                        "is_leaf": True
                    })
                # Si c'est un dict, continuer la récursion
                elif isinstance(value, dict):
                    paths.append({
                        "path": current_path,
                        "level": level + 1,
                        "type": "object",
                        "children_count": len(value),
                        "is_leaf": False
                    })
                    # Récursion
                    paths.extend(HierarchyParser.parse_structure(value, current_path, level + 1, max_level))
                # Si c'est une liste avec des dicts
                elif isinstance(value, list) and value and isinstance(value[0], dict):
                    paths.append({
                        "path": current_path,
                        "level": level + 1,
                        "type": "array",
                        "array_length": len(value),
                        "is_leaf": False
                    })
                    # Parser le premier élément du tableau
                    paths.extend(HierarchyParser.parse_structure(value[0], current_path, level + 1, max_level))
        
        return paths
    
    @staticmethod
    def get_value_by_path(data: Dict[str, Any], path: str) -> Any:
        """
        Récupère une valeur dans une structure hiérarchique via son chemin
        
        Args:
            data: Structure de données
            path: Chemin (ex: "Body.Client.Identity.FirstName")
            
        Returns:
            La valeur trouvée ou None
        """
        keys = path.split('.')
        current = data
        
        try:
            for key in keys:
                if isinstance(current, dict):
                    current = current[key]
                elif isinstance(current, list) and key.isdigit():
                    current = current[int(key)]
                else:
                    return None
            return current
        except (KeyError, IndexError, TypeError):
            return None
    
    @staticmethod
    def set_value_by_path(data: Dict[str, Any], path: str, value: Any) -> Dict[str, Any]:
        """
        Définit une valeur dans une structure hiérarchique via son chemin
        
        Args:
            data: Structure de données
            path: Chemin (ex: "Body.Client.Identity.FirstName")
            value: Valeur à définir
            
        Returns:
            Structure modifiée
        """
        keys = path.split('.')
        current = data
        
        # Créer la structure si elle n'existe pas
        for i, key in enumerate(keys[:-1]):
            if key not in current:
                # Déterminer si le prochain niveau est un objet ou un tableau
                next_key = keys[i + 1]
                current[key] = [] if next_key.isdigit() else {}
            current = current[key]
        
        # Définir la valeur finale
        current[keys[-1]] = value
        return data
    
    @staticmethod
    def build_tree(paths: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Construit un arbre hiérarchique à partir d'une liste de chemins
        
        Args:
            paths: Liste de chemins avec métadonnées
            
        Returns:
            Structure d'arbre pour affichage UI
        """
        tree = {}
        
        for item in paths:
            path_parts = item['path'].split('.')
            current = tree
            
            for i, part in enumerate(path_parts):
                if part not in current:
                    current[part] = {
                        "name": part,
                        "path": '.'.join(path_parts[:i+1]),
                        "level": i + 1,
                        "children": {} if i < len(path_parts) - 1 else None,
                        "is_leaf": item.get('is_leaf', False),
                        "type": item.get('type', 'unknown'),
                        "sample_value": item.get('sample_value')
                    }
                
                if i < len(path_parts) - 1:
                    current = current[part]["children"]
        
        return tree


# Fonction utilitaire pour compter les niveaux
def count_levels(path: str) -> int:
    """Compte le nombre de niveaux dans un chemin"""
    return len(path.split('.'))