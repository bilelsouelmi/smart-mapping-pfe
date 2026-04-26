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
        """
        try:
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
            
            columns = df.columns.tolist()
            data = df.head(100).to_dict('records')
            data = [{k: (None if pd.isna(v) else v) for k, v in row.items()} for row in data]
            
            logger.info(f"Parsed CSV: {len(columns)} columns, {len(data)} rows (sample)")
            return columns, data
            
        except Exception as e:
            logger.error(f"Failed to parse CSV: {e}")
            raise ValueError(f"CSV parsing error: {str(e)}")
    
    @staticmethod
    def parse_xml(file_path: str) -> Tuple[List[str], List[Dict[str, Any]]]:
        """
        Parse un fichier XML générique
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                xml_content = f.read()
            
            data_dict = xmltodict.parse(xml_content)
            data_list = []
            
            if isinstance(data_dict, dict):
                root_key = list(data_dict.keys())[0]
                root_data = data_dict[root_key]
                
                for key, value in root_data.items():
                    if isinstance(value, list):
                        data_list = value
                        break
                    elif isinstance(value, dict):
                        data_list = [value]
                        break
            
            if not data_list:
                raise ValueError("Could not find data array in XML structure")
            
            if data_list:
                first_item = data_list[0]
                columns = list(first_item.keys()) if isinstance(first_item, dict) else []
            else:
                columns = []
            
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
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if isinstance(data, list):
                data_list = data
            elif isinstance(data, dict):
                for key, value in data.items():
                    if isinstance(value, list):
                        data_list = value
                        break
                else:
                    data_list = [data]
            else:
                raise ValueError("Unexpected JSON structure")
            
            if data_list:
                first_item = data_list[0]
                columns = list(first_item.keys()) if isinstance(first_item, dict) else []
            else:
                columns = []
            
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
        """
        try:
            if sheet_name:
                df = pd.read_excel(file_path, sheet_name=sheet_name)
            else:
                df = pd.read_excel(file_path)
            
            columns = df.columns.tolist()
            data = df.head(100).to_dict('records')
            data = [{k: (None if pd.isna(v) else v) for k, v in row.items()} for row in data]
            
            logger.info(f"Parsed Excel: {len(columns)} columns, {len(data)} rows (sample)")
            return columns, data
            
        except Exception as e:
            logger.error(f"Failed to parse Excel: {e}")
            raise ValueError(f"Excel parsing error: {str(e)}")

    # ── NOUVEAU : Parse XML MT SWIFT ──────────────────────────────────────────
    @staticmethod
    def parse_mt_xml(file_path: str) -> Tuple[List[str], List[Dict[str, Any]], Dict[str, Any]]:
        """
        Parse un fichier XML contenant des blocs SWIFT MT.
        Retourne columns, sample_data, et mt_info (mt_type, iso_target, mt_blocks).
        """
        from app.services.mt_parser import mt_parser
        result = mt_parser.parse(file_path)
        return result["columns"], result["sample_data"], {
            "mt_type": result["mt_type"],
            "iso_target": result["iso_target"],
            "mt_blocks": result["mt_blocks"]
        }
    # ── FIN NOUVEAU ────────────────────────────────────────────────────────────

    @classmethod
    def process_file(cls, file_path: str) -> Dict[str, Any]:
        """
        Traite un fichier et retourne sa structure.
        Détecte automatiquement si XML est un fichier MT SWIFT.
        """
        try:
            file_type = cls.detect_file_type(file_path)

            # ── NOUVEAU : détecter XML MT avant parse standard ─────────────────
            if file_type == "XML":
                try:
                    from app.services.mt_parser import mt_parser
                    if mt_parser.is_mt_xml(file_path):
                        logger.info(f"🏦 MT XML detected: {file_path}")
                        columns, data, mt_info = cls.parse_mt_xml(file_path)
                        return {
                            "file_type": "XML_MT",
                            "columns": columns,
                            "sample_data": data[:10],
                            "total_rows": len(data),
                            "mt_info": mt_info
                        }
                except Exception as e:
                    logger.warning(f"MT detection failed, falling back to generic XML: {e}")
            # ── FIN NOUVEAU ────────────────────────────────────────────────────

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
                "sample_data": data[:10],
                "total_rows": len(data),
                "mt_info": None
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
                    
                    source_value = row.get(source_col)
                    
                    if trans_type == 'direct':
                        new_row[target_col] = source_value
                    
                    elif trans_type == 'date_format':
                        new_row[target_col] = source_value  # TODO: Implement date parsing
                    
                    elif trans_type == 'name_split':
                        if source_value and isinstance(source_value, str):
                            parts = source_value.split()
                            if 'first' in target_col.lower():
                                new_row[target_col] = parts[0] if parts else None
                            elif 'last' in target_col.lower():
                                new_row[target_col] = ' '.join(parts[1:]) if len(parts) > 1 else None
                    
                    elif trans_type == 'concatenate':
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
                        new_row[target_col] = source_value
                
                transformed_data.append(new_row)
            
            logger.info(f"Transformed {len(transformed_data)} rows")
            return transformed_data
            
        except Exception as e:  
            logger.error(f"Transformation failed: {e}")
            raise