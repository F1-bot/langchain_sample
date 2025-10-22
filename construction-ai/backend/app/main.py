from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.config import settings
from app.routes import health, analysis, research

app = FastAPI(
    title="Construction AI Backend",
    description="Construction AI Assistant API - Powered by LangChain",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(analysis.router)
app.include_router(research.router)

app.mount("/static", StaticFiles(directory="frontend"), name="static")

@app.get("/")
async def read_index():
    return FileResponse('frontend/index.html')