import re
from typing import Any, Dict, List, Optional
from datetime import datetime, date
import logging

logger = logging.getLogger(__name__)


class FormulaEngine:
    """
    Moteur d'exécution des formules de transformation
    """
    
    def __init__(self):
        self.lookup_tables = {}
    
    def register_lookup_table(self, name: str, data: Dict[str, Any]):
        """Enregistre une table de lookup"""
        self.lookup_tables[name] = data
    
    def execute(
        self, 
        formula_type: str, 
        formula_expression: str, 
        input_data: Dict[str, Any],
        lookup_tables: Optional[Dict[str, Dict[str, Any]]] = None
    ) -> Any:
        """
        Exécute une formule et retourne le résultat
        
        Args:
            formula_type: Type de formule (arithmetic, conditional, transformation, lookup, validation)
            formula_expression: Expression de la formule
            input_data: Données d'entrée
            lookup_tables: Tables de référence optionnelles
            
        Returns:
            Résultat de la formule
        """
        if lookup_tables:
            self.lookup_tables.update(lookup_tables)
        
        try:
            if formula_type == "arithmetic":
                return self._execute_arithmetic(formula_expression, input_data)
            
            elif formula_type == "conditional":
                return self._execute_conditional(formula_expression, input_data)
            
            elif formula_type == "transformation":
                return self._execute_transformation(formula_expression, input_data)
            
            elif formula_type == "lookup":
                return self._execute_lookup(formula_expression, input_data)
            
            elif formula_type == "validation":
                return self._execute_validation(formula_expression, input_data)
            
            else:
                raise ValueError(f"Unknown formula type: {formula_type}")
        
        except Exception as e:
            logger.error(f"Formula execution error: {e}")
            logger.error(f"Formula: {formula_expression}")
            logger.error(f"Input: {input_data}")
            raise
    
    def _execute_arithmetic(self, expression: str, data: Dict[str, Any]) -> float:
        """Exécute une formule arithmétique"""
        # Remplacer les variables par leurs valeurs
        for key, value in data.items():
            if isinstance(value, (int, float)):
                expression = expression.replace(key, str(value))
        
        # Sécurité: autoriser seulement les opérations mathématiques
        allowed_chars = set('0123456789+-*/(). ')
        if not all(c in allowed_chars for c in expression.replace(' ', '')):
            raise ValueError("Invalid arithmetic expression")
        
        return eval(expression)
    
    def _execute_conditional(self, expression: str, data: Dict[str, Any]) -> Any:
        """Exécute une formule conditionnelle"""
        # Supporte IF...THEN...ELSE et CASE WHEN
        
        # IF simple
        if expression.startswith("IF"):
            match = re.match(
                r"IF\s+(.+?)\s+THEN\s+'?(.+?)'?\s+ELSE\s+'?(.+?)'?$",
                expression,
                re.IGNORECASE
            )
            if match:
                condition, then_value, else_value = match.groups()
                
                # Évaluer la condition
                condition_result = self._evaluate_condition(condition, data)
                return then_value if condition_result else else_value
        
        # CASE WHEN
        elif expression.startswith("CASE"):
            # Parse CASE WHEN ... THEN ... ELSE ... END
            when_pattern = r"WHEN\s+(.+?)\s+THEN\s+'?(.+?)'?"
            when_clauses = re.findall(when_pattern, expression, re.IGNORECASE)
            
            for condition, then_value in when_clauses:
                if self._evaluate_condition(condition, data):
                    return then_value
            
            # ELSE clause
            else_match = re.search(r"ELSE\s+'?(.+?)'?(?:\s+END)?$", expression, re.IGNORECASE)
            if else_match:
                return else_match.group(1)
        
        raise ValueError(f"Invalid conditional expression: {expression}")
    
    def _evaluate_condition(self, condition: str, data: Dict[str, Any]) -> bool:
        """Évalue une condition"""
        # Remplacer les variables
        for key, value in data.items():
            if isinstance(value, str):
                condition = condition.replace(key, f"'{value}'")
            else:
                condition = condition.replace(key, str(value))
        
        # Remplacer les opérateurs
        condition = condition.replace('=', '==')
        
        # Évaluer
        try:
            return eval(condition)
        except:
            return False
    
    def _execute_transformation(self, expression: str, data: Dict[str, Any]) -> str:
        """Exécute une formule de transformation"""
        
        # uppercase
        if expression.startswith("uppercase"):
            match = re.match(r"uppercase\((.+?)\)", expression)
            if match:
                field = match.group(1)
                value = data.get(field, "")
                return str(value).upper()
        
        # lowercase
        if expression.startswith("lowercase"):
            match = re.match(r"lowercase\((.+?)\)", expression)
            if match:
                field = match.group(1)
                value = data.get(field, "")
                return str(value).lower()
        
        # concat
        if expression.startswith("concat"):
            match = re.match(r"concat\((.+?)\)", expression)
            if match:
                args = match.group(1).split(',')
                result = ""
                for arg in args:
                    arg = arg.strip().strip("'\"")
                    if arg in data:
                        result += str(data[arg])
                    else:
                        result += arg
                return result
        
        # trim
        if expression.startswith("trim"):
            match = re.match(r"trim\((.+?)\)", expression)
            if match:
                field = match.group(1)
                value = data.get(field, "")
                return str(value).strip()
        
        # remove_spaces
        if expression.startswith("remove_spaces"):
            match = re.match(r"remove_spaces\((.+?)\)", expression)
            if match:
                field = match.group(1)
                value = data.get(field, "")
                return str(value).replace(" ", "")
        
        # date_format
        if expression.startswith("date_format"):
            match = re.match(r"date_format\((.+?),\s*'(.+?)',\s*'(.+?)'\)", expression)
            if match:
                field, from_format, to_format = match.groups()
                date_str = data.get(field, "")
                # Conversion simplifiée
                if from_format == "DD/MM/YYYY" and to_format == "YYYY-MM-DD":
                    parts = date_str.split("/")
                    if len(parts) == 3:
                        return f"{parts[2]}-{parts[1]}-{parts[0]}"
                return date_str
        
        # round
        if expression.startswith("round"):
            match = re.match(r"round\((.+?)\s+(\d+)\)", expression)
            if match:
                field, decimals = match.groups()
                value = data.get(field, 0)
                return round(float(value), int(decimals))
        
        raise ValueError(f"Unknown transformation: {expression}")
    
    def _execute_lookup(self, expression: str, data: Dict[str, Any]) -> Any:
        """Exécute un lookup dans une table de référence"""
        # Format: table_name[key_field]
        match = re.match(r"(\w+)\[(.+?)\]", expression)
        if not match:
            raise ValueError(f"Invalid lookup expression: {expression}")
        
        table_name, key_field = match.groups()
        
        if table_name not in self.lookup_tables:
            raise ValueError(f"Lookup table not found: {table_name}")
        
        key_value = data.get(key_field)
        if key_value is None:
            return None
        
        return self.lookup_tables[table_name].get(key_value)
    
    def _execute_validation(self, expression: str, data: Dict[str, Any]) -> bool:
        """Exécute une validation"""
        
        # iban_validate
        if expression.startswith("iban_validate"):
            match = re.match(r"iban_validate\((.+?),\s*'(.+?)'\)", expression)
            if match:
                field, country_code = match.groups()
                iban = data.get(field, "")
                # Validation simplifiée
                return str(iban).startswith(country_code) and len(str(iban)) >= 15
        
        # email_validate
        if expression.startswith("email_validate"):
            match = re.match(r"email_validate\((.+?)\)", expression)
            if match:
                field = match.group(1)
                email = data.get(field, "")
                return '@' in str(email) and '.' in str(email)
        
        return False