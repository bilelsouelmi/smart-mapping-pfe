"""
API endpoints for XML Mappings
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Any, Optional
import logging

from app.services.xml_mapping_parser import xml_parser

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/xml-mappings", tags=["XML Mappings"])


@router.get("/", response_model=List[Dict[str, Any]])
async def get_all_mappings(
    status: Optional[str] = Query(None, description="Filter by status (ACTIVE, INACTIVE)")
):
    """
    Get list of all available XML mappings with summary information
    """
    try:
        summaries = xml_parser.get_all_mapping_summaries()
        
        # Filter by status if provided
        if status:
            summaries = [s for s in summaries if s.get('status') == status]
        
        logger.info(f"Returned {len(summaries)} mapping summaries")
        return summaries
    except Exception as e:
        logger.error(f"Error retrieving mappings: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving mappings: {str(e)}")


@router.get("/{mapping_id}", response_model=Dict[str, Any])
async def get_mapping_details(mapping_id: str):
    """
    Get detailed information about a specific mapping
    """
    try:
        mapping_data = xml_parser.get_mapping_by_id(mapping_id)
        
        if not mapping_data:
            raise HTTPException(status_code=404, detail=f"Mapping '{mapping_id}' not found")
        
        logger.info(f"Retrieved mapping details for: {mapping_id}")
        return mapping_data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving mapping {mapping_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving mapping: {str(e)}")


@router.get("/{mapping_id}/fields", response_model=Dict[str, Any])
async def get_mapping_fields(mapping_id: str):
    """
    Get source and target fields for a specific mapping
    """
    try:
        mapping_data = xml_parser.get_mapping_by_id(mapping_id)
        
        if not mapping_data:
            raise HTTPException(status_code=404, detail=f"Mapping '{mapping_id}' not found")
        
        fields_data = {
            'mapping_id': mapping_id,
            'mapping_name': mapping_data.get('mapping_name'),
            'source_message': mapping_data.get('source_message', {}),
            'target_message': mapping_data.get('target_message', {}),
            'statistics': mapping_data.get('statistics', {})
        }
        
        logger.info(f"Retrieved fields for mapping: {mapping_id}")
        return fields_data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving fields for {mapping_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving fields: {str(e)}")


@router.get("/{mapping_id}/mappings", response_model=List[Dict[str, Any]])
async def get_field_mappings(
    mapping_id: str,
    criticality: Optional[str] = Query(None, description="Filter by criticality (CRITICAL, HIGH, MEDIUM, LOW)")
):
    """
    Get field mapping details for a specific mapping
    """
    try:
        mapping_data = xml_parser.get_mapping_by_id(mapping_id)
        
        if not mapping_data:
            raise HTTPException(status_code=404, detail=f"Mapping '{mapping_id}' not found")
        
        field_mappings = mapping_data.get('field_mappings', [])
        
        # Filter by criticality if provided
        if criticality:
            field_mappings = [m for m in field_mappings if m.get('criticality') == criticality]
        
        logger.info(f"Retrieved {len(field_mappings)} field mappings for: {mapping_id}")
        return field_mappings
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving mappings for {mapping_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving mappings: {str(e)}")


@router.get("/{mapping_id}/validation-rules", response_model=Dict[str, Any])
async def get_validation_rules(mapping_id: str):
    """
    Get validation rules for a specific mapping
    """
    try:
        mapping_data = xml_parser.get_mapping_by_id(mapping_id)
        
        if not mapping_data:
            raise HTTPException(status_code=404, detail=f"Mapping '{mapping_id}' not found")
        
        validation_rules = mapping_data.get('validation_rules', {})
        
        logger.info(f"Retrieved validation rules for: {mapping_id}")
        return validation_rules
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving validation rules for {mapping_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving validation rules: {str(e)}")


@router.get("/{mapping_id}/statistics", response_model=Dict[str, Any])
async def get_mapping_statistics(mapping_id: str):
    """
    Get statistics about a specific mapping
    """
    try:
        mapping_data = xml_parser.get_mapping_by_id(mapping_id)
        
        if not mapping_data:
            raise HTTPException(status_code=404, detail=f"Mapping '{mapping_id}' not found")
        
        statistics = {
            'mapping_id': mapping_id,
            'mapping_name': mapping_data.get('mapping_name'),
            'statistics': mapping_data.get('statistics', {}),
            'general_info': {
                'source_format': mapping_data.get('general_information', {}).get('source_format'),
                'target_format': mapping_data.get('general_information', {}).get('target_format'),
                'processing_mode': mapping_data.get('general_information', {}).get('processing_mode'),
                'use_cases': mapping_data.get('general_information', {}).get('use_cases', [])
            }
        }
        
        logger.info(f"Retrieved statistics for: {mapping_id}")
        return statistics
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving statistics for {mapping_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving statistics: {str(e)}")


@router.post("/reload")
async def reload_mappings():
    """
    Reload all XML mappings from disk (useful for updates)
    """
    try:
        xml_parser.mappings_cache.clear()
        mappings = xml_parser.load_all_mappings()
        
        return {
            "success": True,
            "message": f"Reloaded {len(mappings)} mappings",
            "mapping_ids": list(mappings.keys())
        }
    except Exception as e:
        logger.error(f"Error reloading mappings: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error reloading mappings: {str(e)}")