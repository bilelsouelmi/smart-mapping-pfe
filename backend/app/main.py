from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import engine, Base
from app.api.routes import api_router
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    debug=settings.DEBUG
)

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
        "chromadb": f"{settings.CHROMADB_HOST}:{settings.CHROMADB_PORT}",
        "debug": settings.DEBUG
    }

@app.on_event("startup")
async def startup_event():
    logger.info(f"Starting {settings.PROJECT_NAME} v{settings.VERSION}")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    
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
    
# Test ChromaDB connection
logger.info("🔍 Starting ChromaDB connection test...")

try:
    import requests
    import time
    
    # Essayons d'abord la racine
    chromadb_url = f"http://{settings.CHROMADB_HOST}:{settings.CHROMADB_PORT}/"
    logger.info(f"   Testing URL: {chromadb_url}")
    
    max_retries = 3
    for i in range(max_retries):
        try:
            logger.info(f"   Attempt {i+1}/{max_retries}...")
            response = requests.get(chromadb_url, timeout=5)
            logger.info(f"   Response status: {response.status_code}")
            
            # ChromaDB peut répondre 200, 404, ou autre
            # Tant qu'il répond, c'est qu'il fonctionne
            if response.status_code in [200, 404]:
                logger.info("✅ ChromaDB connected and responding")
                break
            else:
                logger.warning(f"   Unexpected status code: {response.status_code}")
                
        except requests.exceptions.RequestException as req_err:
            logger.warning(f"   Request failed: {req_err}")
            if i < max_retries - 1:
                logger.info(f"⏳ Waiting for ChromaDB... (attempt {i+1}/{max_retries})")
                time.sleep(2)
            else:
                logger.warning("⚠️  ChromaDB not responding after retries")
                
except Exception as e:
    logger.error(f"⚠️  ChromaDB connection failed with error: {e}")