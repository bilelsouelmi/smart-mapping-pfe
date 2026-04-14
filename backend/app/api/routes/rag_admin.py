"""
RAG Admin API Routes
Endpoints for managing RAG system
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any
import logging

from app.services.rag_initializer import rag_initializer
from app.services.qdrant_manager import qdrant_manager as chromadb_manager


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rag-admin", tags=["RAG Administration"])


@router.post("/initialize")
async def initialize_rag(reset: bool = False) -> Dict[str, Any]:
    """
    Initialize RAG system by loading XML mappings into ChromaDB
    
    Args:
        reset: If True, reset ChromaDB collection before loading
    """
    try:
        logger.info(f"Initializing RAG system (reset={reset})...")
        results = rag_initializer.initialize(reset=reset)
        
        if not results["success"]:
            raise HTTPException(
                status_code=500,
                detail={
                    "message": "RAG initialization failed",
                    "errors": results["errors"]
                }
            )
        
        return {
            "success": True,
            "message": "RAG system initialized successfully",
            "details": results
        }
        
    except Exception as e:
        logger.error(f"RAG initialization error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_rag_status() -> Dict[str, Any]:
    """
    Get current status of RAG system
    """
    try:
        status = rag_initializer.get_status()
        return status
    except Exception as e:
        logger.error(f"Error getting RAG status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_chromadb_stats() -> Dict[str, Any]:
    """
    Get ChromaDB collection statistics
    """
    try:
        stats = chromadb_manager.get_collection_stats()
        return stats
    except Exception as e:
        logger.error(f"Error getting ChromaDB stats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reset")
async def reset_chromadb() -> Dict[str, Any]:
    """
    Reset ChromaDB collection (delete all data)
    """
    try:
        logger.warning("Resetting ChromaDB collection...")
        success = chromadb_manager.reset_collection()
        
        if success:
            return {
                "success": True,
                "message": "ChromaDB collection reset successfully"
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to reset collection")
            
    except Exception as e:
        logger.error(f"Error resetting ChromaDB: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/mapping/{mapping_id}")
async def delete_mapping_chunks(mapping_id: str) -> Dict[str, Any]:
    """
    Delete all chunks for a specific mapping
    """
    try:
        logger.info(f"Deleting chunks for mapping: {mapping_id}")
        success = chromadb_manager.delete_by_mapping_id(mapping_id)
        
        if success:
            return {
                "success": True,
                "message": f"Deleted chunks for mapping: {mapping_id}"
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to delete chunks")
            
    except Exception as e:
        logger.error(f"Error deleting chunks: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))