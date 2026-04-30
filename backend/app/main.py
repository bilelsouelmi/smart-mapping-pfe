from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import engine, Base
from app.api.routes import api_router
import logging
from app.api.routes import xml_mappings
from app.api.routes import rag_admin
from app.api.routes import rag
from app.api.routes import ai_learning
from app.api.routes import element_routes
from app.api.routes import element_routes  # ── NOUVEAU ──

# Force Qdrant Manager initialization at import
from app.services.qdrant_manager import qdrant_manager as chromadb_manager

# Import models for table creation
from app.models.ai_learning import AILearning

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    debug=settings.DEBUG
)

app.include_router(rag.router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Base.metadata.create_all(bind=engine)

# Include API routes
app.include_router(api_router, prefix="/api")
app.include_router(rag_admin.router, prefix="/api")
app.include_router(xml_mappings.router, prefix="/api")
app.include_router(ai_learning.router, prefix="/api")
app.include_router(element_routes.router, prefix="/api")
app.include_router(element_routes.router, prefix="/api")  # ── NOUVEAU ──

@app.get("/")
async def root():
    return {
        "message": f"Welcome to {settings.PROJECT_NAME}",
        "version": settings.VERSION,
        "status": "running"
    }

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "environment": settings.ENVIRONMENT,
        "database": "connected",
        "ollama": f"{settings.OLLAMA_BASE_URL} - {settings.OLLAMA_MODEL}",
        "qdrant": f"{settings.QDRANT_HOST}:{settings.QDRANT_PORT}",
        "debug": settings.DEBUG
    }

@app.on_event("startup")
async def startup_event():
    logger.info(f"Starting {settings.PROJECT_NAME} v{settings.VERSION}")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    
    # Force Qdrant Manager initialization
    logger.info("🔧 Initializing Qdrant Manager...")
    try:
        if chromadb_manager.collection:
            collection_info = chromadb_manager.client.get_collection(chromadb_manager.collection_name)
            count = collection_info.points_count
            logger.info(f"✅ Qdrant Manager ready - {count} points available")
        else:
            logger.warning("⚠️ Qdrant Manager collection is None - attempting to initialize...")
            chromadb_manager.initialize_collection()
            if chromadb_manager.collection:
                collection_info = chromadb_manager.client.get_collection(chromadb_manager.collection_name)
                count = collection_info.points_count
                logger.info(f"✅ Qdrant Manager initialized - {count} points")
            else:
                logger.error("❌ Failed to initialize Qdrant Manager")
    except Exception as e:
        logger.error(f"❌ Qdrant Manager error: {e}")
    
    # Test Ollama connection
    try:
        import requests
        response = requests.get(f"{settings.OLLAMA_BASE_URL}/api/tags", timeout=5)
        if response.status_code == 200:
            models = response.json().get('models', [])
            logger.info(f"✅ Ollama connected - Available models: {len(models)}")
            logger.info(f"   Using model: {settings.OLLAMA_MODEL}")
        else:
            logger.warning("⚠️  Ollama not responding")
    except Exception as e:
        logger.warning(f"⚠️  Ollama connection failed: {e}")
    
    # Test Qdrant connection
    logger.info("🔍 Starting Qdrant connection test...")
    
    try:
        import requests
        import time
        
        qdrant_url = f"http://{settings.QDRANT_HOST}:{settings.QDRANT_PORT}/"
        logger.info(f"   Testing URL: {qdrant_url}")
        
        max_retries = 3
        for i in range(max_retries):
            try:
                logger.info(f"   Attempt {i+1}/{max_retries}...")
                response = requests.get(qdrant_url, timeout=5)
                logger.info(f"   Response status: {response.status_code}")
                
                if response.status_code == 200:
                    logger.info("✅ Qdrant connected and responding")
                    break
                else:
                    logger.warning(f"   Unexpected status code: {response.status_code}")
                    
            except requests.exceptions.RequestException as req_err:
                logger.warning(f"   Request failed: {req_err}")
                if i < max_retries - 1:
                    logger.info(f"⏳ Waiting for Qdrant... (attempt {i+1}/{max_retries})")
                    time.sleep(2)
                else:
                    logger.warning("⚠️  Qdrant not responding after retries")
                    
    except Exception as e:
        logger.error(f"⚠️  Qdrant connection failed with error: {e}")