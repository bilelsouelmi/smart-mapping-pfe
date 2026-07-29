import re
import requests
import json
import logging
from typing import Dict, List, Optional, Any
from app.config import settings

logger = logging.getLogger(__name__)

# Ollama occasionally drops the comma between two adjacent quoted JSON
# tokens — most often when a string value (e.g. an "example_input" built
# from real sample data) itself contains a comma, which seems to confuse
# the model into thinking a separator was already emitted. A valid JSON
# document never has a bare `"..."` immediately followed by another
# `"..."` with only whitespace between them (no `:` or `,`), so this
# substitution is safe to apply generically before giving up on a parse.
_MISSING_COMMA_RE = re.compile(r'"\s*\n\s*"')


def _parse_llm_json(response: str):
    """json.loads with a fallback repair for the missing-comma glitch above."""
    try:
        return json.loads(response)
    except json.JSONDecodeError as e:
        repaired = _MISSING_COMMA_RE.sub('",\n"', response)
        if repaired != response:
            try:
                result = json.loads(repaired)
                logger.warning(f"Auto-repaired malformed JSON from LLM (missing comma): {e}")
                return result
            except json.JSONDecodeError:
                pass
        raise e


class LLMService:
    """
    Service pour interagir avec Ollama (LLM local)
    """

    def __init__(self, base_url: str = None, model: str = None):
        self.base_url = base_url or settings.OLLAMA_BASE_URL
        self.model = model or settings.OLLAMA_MODEL
        logger.info(f"LLM Service initialized - Model: {self.model}")

    def generate(self, prompt: str, max_tokens: int = 1000, temperature: float = 0.3) -> str:
        """
        Génère une réponse avec Ollama
        """
        url = f"{self.base_url}/api/generate"

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens
            }
        }

        try:
            logger.info(f"Sending request to Ollama: {url}")
            response = requests.post(url, json=payload, timeout=180)
            response.raise_for_status()

            result = response.json()
            generated_text = result.get("response", "")

            logger.info(f"Ollama response received: {len(generated_text)} chars")
            return generated_text

        except requests.exceptions.Timeout:
            logger.error("Ollama request timeout")
            raise Exception("LLM request timeout - model might be slow or unavailable")
        except requests.exceptions.RequestException as e:
            logger.error(f"Ollama API error: {e}")
            raise Exception(f"LLM API error: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise

    def analyze_file_structure(
        self,
        columns: List[str],
        sample_data: List[Dict[str, Any]],
        file_type: str = "CSV"
    ) -> Dict[str, Any]:
        """
        Analyse la structure d'un fichier et génère une MessageDescription
        """
        prompt = f"""You are a data analysis expert specialized in file structure analysis.

Analyze this {file_type} file structure:

COLUMNS: {', '.join(columns)}

SAMPLE DATA (first 3 rows):
{json.dumps(sample_data[:3], indent=2)}

Generate a structured analysis including:
1. Detected data types for each column (string, integer, float, date, boolean, etc.)
2. Date formats if any (e.g., "DD/MM/YYYY", "YYYY-MM-DD")
3. Potential data quality issues (null values, inconsistencies)
4. Business domain suggestion (Banking, Insurance, Healthcare, etc.)
5. Recommended target system format

IMPORTANT: Return ONLY valid JSON with this exact structure:
{{
  "file_type": "{file_type}",
  "columns_analysis": [
    {{
      "name": "column_name",
      "detected_type": "string|integer|float|date|boolean",
      "format": "format if date, null otherwise",
      "nullable": true/false,
      "sample_values": ["val1", "val2"]
    }}
  ],
  "business_domain": "detected domain",
  "data_quality_issues": ["issue1", "issue2"],
  "recommendations": ["recommendation1", "recommendation2"]
}}

Return ONLY the JSON, no markdown, no explanation.
"""

        response = self.generate(prompt, max_tokens=2000, temperature=0.2)

        response = response.strip()
        if "```json" in response:
            response = response.split("```json")[1].split("```")[0].strip()
        elif "```" in response:
            response = response.split("```")[1].split("```")[0].strip()

        try:
            return _parse_llm_json(response)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {e}")
            logger.error(f"Response was: {response[:500]}")
            raise ValueError(f"Invalid JSON response from LLM: {str(e)}")

    def suggest_mapping(
        self,
        source_columns: List[str],
        target_columns: List[str],
        sample_data: List[Dict[str, Any]],
        business_domain: Optional[str] = None,
        similar_mappings: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Suggère un mapping entre colonnes source et cible
        """
        context = ""
        if business_domain:
            context += f"\nBUSINESS DOMAIN: {business_domain}"

        if similar_mappings:
            context += "\n\nSIMILAR MAPPINGS FROM KNOWLEDGE BASE:"
            for mapping in similar_mappings[:3]:
                context += f"\n- {mapping.get('source_column')} → {mapping.get('target_column')}"
                context += f"  (Type: {mapping.get('transformation_type')}, Success: {mapping.get('success_rate', 0):.0%})"

        prompt = f"""You are a data mapping expert specialized in suggesting optimal field mappings.

SOURCE COLUMNS: {', '.join(source_columns)}
TARGET COLUMNS: {', '.join(target_columns)}

SAMPLE SOURCE DATA (first 3 rows):
{json.dumps(sample_data[:3], indent=2)}
{context}

Suggest optimal mappings between source and target columns.

For each target column, suggest:
1. Which source column(s) to use
2. Transformation type needed (direct, date_format, name_split, phone_format, concatenate, substring, case_conversion, custom)
3. Exact transformation rule/formula
4. Confidence score (0.0 to 1.0)
5. Reasoning

TRANSFORMATION TYPES:
- direct: Copy value as-is
- date_format: Convert date format (specify input/output format)
- name_split: Split full name into first/last name
- phone_format: Standardize phone number format
- concatenate: Combine multiple source columns
- substring: Extract part of a string
- case_conversion: Change case (upper/lower/title)
- custom: Complex transformation (provide Python-like logic)

IMPORTANT: Return ONLY valid JSON with this exact structure:
{{
  "mappings": [
    {{
      "target_column": "column_name",
      "source_column": "source_column_name or null",
      "transformation_type": "direct|date_format|name_split|etc",
      "transformation_rule": "detailed transformation logic",
      "confidence": 0.95,
      "reasoning": "why this mapping makes sense",
      "example_input": "example source value",
      "example_output": "expected result"
    }}
  ]
}}

Return ONLY the JSON, no markdown, no explanation.
"""

        # 2500 was too tight: each mapping entry includes reasoning +
        # example_input/output, so requests with >~6 target columns got
        # cut off mid-JSON (num_predict hit before the array closed),
        # producing an unparseable response and a 500. num_predict is a
        # cap, not a target, so raising it doesn't slow down shorter
        # responses.
        response = self.generate(prompt, max_tokens=6000, temperature=0.3)

        response = response.strip()
        if "```json" in response:
            response = response.split("```json")[1].split("```")[0].strip()
        elif "```" in response:
            response = response.split("```")[1].split("```")[0].strip()

        try:
            return _parse_llm_json(response)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {e}")
            logger.error(f"Response was: {response[:500]}")
            raise ValueError(f"Invalid JSON response from LLM: {str(e)}")

    def suggest_xml_mapping(
        self,
        mt_type: str,
        iso_target: str,
        source_fields: List[Dict[str, Any]],
        formulas: Optional[List[Dict[str, Any]]] = None,
        rag_context: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Suggère des mappings XPath ISO 20022 pour des champs SWIFT MT,
        en s'appuyant sur le contexte RAG (fragments XML similaires) et
        les formules de transformation déjà acceptées par l'utilisateur.

        Chaque champ est traité dans un appel LLM séparé (one-field-at-a-time)
        pour éliminer tout risque de troncature JSON. Le matching se fait par
        nom de champ (source_field_name) car field_tag est souvent vide en base.
        """
        all_elements: List[Dict[str, Any]] = []

        formulas_context = ""
        if formulas:
            formulas_context = "\n\nACCEPTED TRANSFORMATION FORMULAS (use these rules when applicable):\n"
            formulas_context += "\n".join(
                f"- {f.get('source_path')} → {f.get('target_path')} "
                f"[{f.get('transformation_type')}]: {f.get('transformation_rule')}"
                for f in formulas
            )

        rag_block = ""
        if rag_context:
            rag_block = "\n\nREFERENCE ISO 20022 XML STRUCTURE (from knowledge base):\n"
            rag_block += "\n---\n".join(rag_context[:3])

        for f in source_fields:
            field_name = f.get("name", "")
            field_tag = f.get("tag", "")
            field_desc = f.get("description", "")

            prompt = f"""You are a SWIFT-to-ISO20022 migration expert.

SOURCE MESSAGE TYPE: {mt_type}
TARGET ISO 20022 SCHEMA: {iso_target}

SOURCE FIELD TO MAP:
Name: {field_name}
Tag: {field_tag or "(unknown)"}
Description: {field_desc}
{formulas_context}
{rag_block}

Provide the correct ISO 20022 XPath target within the {iso_target} schema
for this field, and a SHORT transformation expression if needed (e.g. trim,
substring, date reformatting, BIC extraction). Keep the expression under
8 words.

Use standard ISO 20022 element names (e.g. GrpHdr/MsgId, Ntfctn/Ntry/Amt,
RltdAgts/DbtrAgt/FinInstnId/BICFI, NtryDtls/TxDtls/Refs/InstrId).

If you are NOT confident this field has a clean, direct equivalent in
{iso_target} — it's SWIFT envelope/technical metadata, a derived
classification code with no real 1:1 target, or you're genuinely unsure —
do NOT guess. Return "target_xpath": null and "confidence": 0.0 instead.
A field correctly left for human review is far better than a confidently
wrong mapping.

IMPORTANT: Return ONLY one compact, valid JSON object, nothing else:
{{
  "target_xpath": "NtryDtls/TxDtls/Refs/InstrId",
  "expression": "trim(value)",
  "confidence": 0.9,
  "is_mandatory": true
}}
If unsure, return exactly:
{{"target_xpath": null, "expression": null, "confidence": 0.0, "is_mandatory": false}}

Return ONLY the JSON object, no markdown, no explanation, no array brackets.
"""

            try:
                response = self.generate(prompt, max_tokens=300, temperature=0.1)
                response = response.strip()
                if "```json" in response:
                    response = response.split("```json")[1].split("```")[0].strip()
                elif "```" in response:
                    response = response.split("```")[1].split("```")[0].strip()

                item = _parse_llm_json(response)
                item["source_field_name"] = field_name
                all_elements.append(item)

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON for field '{field_name}': {e}")
                logger.error(f"Response was: {response[:300]}")
                continue
            except Exception as e:
                logger.error(f"LLM call failed for field '{field_name}': {e}")
                continue

        return {"elements": all_elements}

    def validate_transformation_result(
        self,
        expected_data: List[Dict[str, Any]],
        actual_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Valide le résultat d'une transformation en comparant avec les données attendues
        """
        prompt = f"""You are a data validation expert.

Compare these two datasets and provide a detailed validation report.

EXPECTED DATA (first 5 rows):
{json.dumps(expected_data[:5], indent=2)}

ACTUAL DATA (first 5 rows):
{json.dumps(actual_data[:5], indent=2)}

Analyze:
1. Row count match
2. Column count match
3. Data accuracy (cell by cell comparison)
4. Data type consistency
5. Format consistency
6. Overall quality assessment

Return ONLY valid JSON:
{{
  "overall_quality": "Excellent|Good|Fair|Poor",
  "accuracy_percentage": 95.5,
  "issues_found": ["issue1", "issue2"],
  "recommendations": ["recommendation1", "recommendation2"]
}}

Return ONLY the JSON, no markdown, no explanation.
"""

        response = self.generate(prompt, max_tokens=1500, temperature=0.2)

        response = response.strip()
        if "```json" in response:
            response = response.split("```json")[1].split("```")[0].strip()
        elif "```" in response:
            response = response.split("```")[1].split("```")[0].strip()

        try:
            return _parse_llm_json(response)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {e}")
            raise ValueError(f"Invalid JSON response from LLM: {str(e)}")