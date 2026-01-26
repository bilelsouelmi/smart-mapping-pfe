import pandas as pd
import json
import xml.etree.ElementTree as ET
import xmltodict
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import csv

logger = logging.getLogger(__name__)


class FileProcessor:
    """
    Service pour traiter différents types de fichiers (CSV, XML, JSON, Excel)
    """
    
    SUPPORTED_FORMATS = ["csv", "xml", "json", "xlsx", "xls"]
    
    @staticmethod
    def detect_file_type(file_path: str) -> str:
        """
        Détecte le type de fichier basé sur l'extension
        
        Args:
            file_path: Chemin du fichier
            
        Returns:
            Type de fichier (CSV, XML, JSON, Excel)
        """
        extension = Path(file_path).suffix.lower().replace('.', '')
        
        if extension == 'csv':
            return "CSV"
        elif extension == 'xml':
            return "XML"
        elif extension == 'json':
            return "JSON"
        elif extension in ['xlsx', 'xls']:
            return "Excel"
        else:
            raise ValueError(f"Unsupported file format: {extension}")
    
    @staticmethod
    def parse_csv(file_path: str, encoding: str = 'utf-8') -> Tuple[List[str], List[Dict[str, Any]]]:
        """
        Parse un fichier CSV
        
        Args:
            file_path: Chemin du fichier CSV
            encoding: Encodage du fichier
            
        Returns:
            Tuple (colonnes, données)
        """
        try:
            # Try different encodings if utf-8 fails
            encodings = [encoding, 'utf-8', 'latin-1', 'iso-8859-1', 'cp1252']
            
            df = None
            for enc in encodings:
                try:
                    df = pd.read_csv(file_path, encoding=enc)
                    logger.info(f"Successfully read CSV with encoding: {enc}")
                    break
                except UnicodeDecodeError:
                    continue
            
            if df is None:
                raise ValueError("Could not read CSV file with any supported encoding")
            
            # Get columns
            columns = df.columns.tolist()
            
            # Convert to list of dicts (limit to first 100 rows for sample)
            data = df.head(100).to_dict('records')
            
            # Clean NaN values
            data = [{k: (None if pd.isna(v) else v) for k, v in row.items()} for row in data]
            
            logger.info(f"Parsed CSV: {len(columns)} columns, {len(data)} rows (sample)")
            return columns, data
            
        except Exception as e:
            logger.error(f"Failed to parse CSV: {e}")
            raise ValueError(f"CSV parsing error: {str(e)}")
    
    @staticmethod
    def parse_xml(file_path: str) -> Tuple[List[str], List[Dict[str, Any]]]:
        """
        Parse un fichier XML
        
        Args:
            file_path: Chemin du fichier XML
            
        Returns:
            Tuple (colonnes, données)
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                xml_content = f.read()
            
            # Parse XML to dict
            data_dict = xmltodict.parse(xml_content)
            
            # Try to find the data array (common patterns)
            data_list = []
            
            # Pattern 1: Root > items > item
            if isinstance(data_dict, dict):
                root_key = list(data_dict.keys())[0]
                root_data = data_dict[root_key]
                
                # Look for array-like structures
                for key, value in root_data.items():
                    if isinstance(value, list):
                        data_list = value
                        break
                    elif isinstance(value, dict):
                        # Single item
                        data_list = [value]
                        break
            
            if not data_list:
                raise ValueError("Could not find data array in XML structure")
            
            # Extract columns from first item
            if data_list:
                first_item = data_list[0]
                columns = list(first_item.keys()) if isinstance(first_item, dict) else []
            else:
                columns = []
            
            # Limit to first 100 items
            data = data_list[:100]
            
            logger.info(f"Parsed XML: {len(columns)} columns, {len(data)} rows (sample)")
            return columns, data
            
        except Exception as e:
            logger.error(f"Failed to parse XML: {e}")
            raise ValueError(f"XML parsing error: {str(e)}")
    
    @staticmethod
    def parse_json(file_path: str) -> Tuple[List[str], List[Dict[str, Any]]]:
        """
        Parse un fichier JSON
        
        Args:
            file_path: Chemin du fichier JSON
            
        Returns:
            Tuple (colonnes, données)
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Handle different JSON structures
            if isinstance(data, list):
                data_list = data
            elif isinstance(data, dict):
                # Try to find the data array
                for key, value in data.items():
                    if isinstance(value, list):
                        data_list = value
                        break
                else:
                    # Single object
                    data_list = [data]
            else:
                raise ValueError("Unexpected JSON structure")
            
            # Extract columns from first item
            if data_list:
                first_item = data_list[0]
                columns = list(first_item.keys()) if isinstance(first_item, dict) else []
            else:
                columns = []
            
            # Limit to first 100 items
            data_list = data_list[:100]
            
            logger.info(f"Parsed JSON: {len(columns)} columns, {len(data_list)} rows (sample)")
            return columns, data_list
            
        except Exception as e:
            logger.error(f"Failed to parse JSON: {e}")
            raise ValueError(f"JSON parsing error: {str(e)}")
    
    @staticmethod
    def parse_excel(file_path: str, sheet_name: Optional[str] = None) -> Tuple[List[str], List[Dict[str, Any]]]:
        """
        Parse un fichier Excel
        
        Args:
            file_path: Chemin du fichier Excel
            sheet_name: Nom de la feuille (None = première feuille)
            
        Returns:
            Tuple (colonnes, données)
        """
        try:
            # Read Excel file
            if sheet_name:
                df = pd.read_excel(file_path, sheet_name=sheet_name)
            else:
                df = pd.read_excel(file_path)
            
            # Get columns
            columns = df.columns.tolist()
            
            # Convert to list of dicts (limit to first 100 rows)
            data = df.head(100).to_dict('records')
            
            # Clean NaN values
            data = [{k: (None if pd.isna(v) else v) for k, v in row.items()} for row in data]
            
            logger.info(f"Parsed Excel: {len(columns)} columns, {len(data)} rows (sample)")
            return columns, data
            
        except Exception as e:
            logger.error(f"Failed to parse Excel: {e}")
            raise ValueError(f"Excel parsing error: {str(e)}")
    
    @classmethod
    def process_file(cls, file_path: str) -> Dict[str, Any]:
        """
        Traite un fichier et retourne sa structure
        
        Args:
            file_path: Chemin du fichier
            
        Returns:
            Dictionnaire avec file_type, columns, sample_data
        """
        try:
            # Detect file type
            file_type = cls.detect_file_type(file_path)
            
            # Parse based on type
            if file_type == "CSV":
                columns, data = cls.parse_csv(file_path)
            elif file_type == "XML":
                columns, data = cls.parse_xml(file_path)
            elif file_type == "JSON":
                columns, data = cls.parse_json(file_path)
            elif file_type == "Excel":
                columns, data = cls.parse_excel(file_path)
            else:
                raise ValueError(f"Unsupported file type: {file_type}")
            
            return {
                "file_type": file_type,
                "columns": columns,
                "sample_data": data[:10],  # Return only first 10 rows as sample
                "total_rows": len(data)
            }
            
        except Exception as e:
            logger.error(f"Failed to process file: {e}")
            raise
    
    @staticmethod
    def apply_transformation(
        data: List[Dict[str, Any]],
        mapping_formulas: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Applique des transformations sur les données
        
        Args:
            data: Données source
            mapping_formulas: Liste des formules de transformation
            
        Returns:
            Données transformées
        """
        try:
            transformed_data = []
            
            for row in data:
                new_row = {}
                
                for formula in mapping_formulas:
                    target_col = formula.get('target_column')
                    source_col = formula.get('source_column')
                    trans_type = formula.get('transformation_type')
                    trans_rule = formula.get('transformation_rule')
                    
                    # Get source value
                    source_value = row.get(source_col)
                    
                    # Apply transformation based on type
                    if trans_type == 'direct':
                        new_row[target_col] = source_value
                    
                    elif trans_type == 'date_format':
                        # Date transformation (simplified)
                        new_row[target_col] = source_value  # TODO: Implement date parsing
                    
                    elif trans_type == 'name_split':
                        # Split full name (simplified)
                        if source_value and isinstance(source_value, str):
                            parts = source_value.split()
                            if 'first' in target_col.lower():
                                new_row[target_col] = parts[0] if parts else None
                            elif 'last' in target_col.lower():
                                new_row[target_col] = ' '.join(parts[1:]) if len(parts) > 1 else None
                    
                    elif trans_type == 'concatenate':
                        # Concatenate multiple columns (TODO: parse rule for multiple sources)
                        new_row[target_col] = source_value
                    
                    elif trans_type == 'case_conversion':
                        if source_value and isinstance(source_value, str):
                            if 'upper' in trans_rule.lower():
                                new_row[target_col] = source_value.upper()
                            elif 'lower' in trans_rule.lower():
                                new_row[target_col] = source_value.lower()
                            elif 'title' in trans_rule.lower():
                                new_row[target_col] = source_value.title()
                    
                    else:
                        # Default: direct copy
                        new_row[target_col] = source_value
                
                transformed_data.append(new_row)
            
            logger.info(f"Transformed {len(transformed_data)} rows")
            return transformed_data
            
        except Exception as e:  
            logger.error(f"Transformation failed: {e}")
            raise