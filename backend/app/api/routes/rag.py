"""
RAG Query Endpoints
Provides semantic search and query capabilities
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from app.services.qdrant_manager import qdrant_manager as chromadb_manager
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/rag", tags=["RAG"])


class RAGQuery(BaseModel):
    """RAG query request"""
    query: str = Field(..., description="Search query in natural language")
    n_results: int = Field(default=5, ge=1, le=20, description="Number of results to return")
    filter_mapping_id: Optional[str] = Field(None, description="Filter by specific mapping ID")
    filter_chunk_type: Optional[str] = Field(None, description="Filter by chunk type")


class RAGResponse(BaseModel):
    """RAG query response"""
    success: bool
    query: str
    results: List[Dict[str, Any]]
    metadata: Dict[str, Any]


class SearchResult(BaseModel):
    """Single search result"""
    chunk_id: str
    content: str
    metadata: Dict[str, Any]
    similarity_score: float
    rank: int


@router.post("/query", response_model=RAGResponse)
async def query_rag(request: RAGQuery):
    """
    Query the RAG system with natural language
    
    Returns semantically similar chunks from the vector database
    
    **Example queries:**
    - "How to convert MT202 to MT500?"
    - "Field 20C mapping details"
    - "What are the validation rules for MT500?"
    - "Critical mappings for securities settlement"
    """
    try:
        logger.info(f"RAG Query: {request.query}")
        
        # Build metadata filter
        filter_metadata = {}
        if request.filter_mapping_id:
            filter_metadata["mapping_id"] = request.filter_mapping_id
        if request.filter_chunk_type:
            filter_metadata["chunk_type"] = request.filter_chunk_type
        
        # Query chromadb_manager /retrieval
        results = chromadb_manager.search(  # ← CHANGÉ
            query=request.query,
            n_results=request.n_results,
            filter_metadata=filter_metadata if filter_metadata else None
        )
        
        if not results or not results.get('ids', [[]])[0]:  # ← AJOUTÉ check
            return RAGResponse(
                success=False,
                query=request.query,
                results=[],
                metadata={
                    "message": "No results found",
                    "level": 1,
                    "fallback": "Try web search or broader query"
                }
            )
        
        # Format results
        formatted_results = []
        for i, (chunk_id, content, metadata, distance) in enumerate(zip(
            results.get('ids', [[]])[0],
            results.get('documents', [[]])[0],
            results.get('metadatas', [[]])[0],
            results.get('distances', [[]])[0]
        )):
            # Convert distance to similarity score (1 - distance for cosine)
            similarity_score = 1 - distance if distance is not None else 0
            
            formatted_results.append({
                "chunk_id": chunk_id,
                "content": content,
                "metadata": metadata,
                "similarity_score": round(similarity_score, 4),
                "rank": i + 1
            })
        
        return RAGResponse(
            success=True,
            query=request.query,
            results=formatted_results,
            metadata={
                "total_results": len(formatted_results),
                "level": 1,
                "source": "chromadb",
                "filters_applied": filter_metadata
            }
        )
        
    except Exception as e:
        logger.error(f"RAG query error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"RAG query failed: {str(e)}"
        )


@router.get("/search")
async def search_mappings(
    query: str = Query(..., description="Search query"),
    mapping_id: Optional[str] = Query(None, description="Filter by mapping ID"),
    chunk_type: Optional[str] = Query(None, description="Filter by chunk type"),
    limit: int = Query(5, ge=1, le=20, description="Number of results")
):
    """
    Search for mappings using semantic similarity
    
    **Query parameters:**
    - query: Natural language search query
    - mapping_id: Optional mapping ID filter
    - chunk_type: Optional chunk type filter (FIELD_MAPPING, SOURCE_FIELD, etc.)
    - limit: Number of results (1-20)
    
    **Example:**
    `/api/rag/search?query=settlement amount&chunk_type=FIELD_MAPPING&limit=3`
    """
    try:
        filter_metadata = {}
        if mapping_id:
            filter_metadata["mapping_id"] = mapping_id
        if chunk_type:
            filter_metadata["chunk_type"] = chunk_type
        
        results = chromadb_manager.search(  # ← CHANGÉ
            query=query,
            n_results=limit,
            filter_metadata=filter_metadata if filter_metadata else None
        )
        
        if not results or not results.get('ids', [[]])[0]:
            return {
                "success": True,
                "query": query,
                "results": [],
                "message": "No matching chunks found"
            }
        
        # Format response
        chunks = []
        for i, (chunk_id, content, metadata, distance) in enumerate(zip(
            results['ids'][0],
            results['documents'][0],
            results['metadatas'][0],
            results['distances'][0]
        )):
            chunks.append({
                "rank": i + 1,
                "chunk_id": chunk_id,
                "content": content,
                "mapping_id": metadata.get("mapping_id"),
                "chunk_type": metadata.get("chunk_type"),
                "similarity": round(1 - distance, 4)
            })
        
        return {
            "success": True,
            "query": query,
            "total_results": len(chunks),
            "results": chunks
        }
        
    except Exception as e:
        logger.error(f"Search error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/mappings/find")
async def find_mapping(
    source_field: str = Query(..., description="Source field name or tag"),
    target_field: Optional[str] = Query(None, description="Target field name or tag"),
    n_results: int = Query(3, ge=1, le=10)
):
    """
    Find field mappings by source/target fields
    
    **Example:**
    `/api/rag/mappings/find?source_field=Field20C&target_field=Field20C_SEME`
    """
    try:
        # Build query
        if target_field:
            query = f"mapping from {source_field} to {target_field}"
        else:
            query = f"mapping for {source_field}"
        
        # Search with FIELD_MAPPING filter
        results = chromadb_manager.search(  # ← CHANGÉ
            query=query,
            n_results=n_results,
            filter_metadata={"chunk_type": "FIELD_MAPPING"}
        )
        
        if not results or not results.get('ids', [[]])[0]:
            return {
                "success": False,
                "message": f"No mapping found for {source_field}",
                "suggestion": "Try broader search or check field name"
            }
        
        mappings = []
        for chunk_id, content, metadata, distance in zip(
            results['ids'][0],
            results['documents'][0],
            results['metadatas'][0],
            results['distances'][0]
        ):
            mappings.append({
                "source_field": metadata.get("source_field"),
                "target_field": metadata.get("target_field"),
                "mapping_id": metadata.get("mapping_id"),
                "formula_type": metadata.get("formula_type"),
                "criticality": metadata.get("criticality"),
                "content": content,
                "relevance": round(1 - distance, 4)
            })
        
        return {
            "success": True,
            "source_field": source_field,
            "target_field": target_field,
            "total_found": len(mappings),
            "mappings": mappings
        }
        
    except Exception as e:
        logger.error(f"Find mapping error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_rag_stats():
    """
    Get RAG system statistics
    
    Returns information about indexed chunks and system health
    """
    try:
        stats = chromadb_manager.get_collection_stats()  # ← CHANGÉ
        return {
            "success": True,
            "stats": stats
        }
    except Exception as e:
        logger.error(f"Stats error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))