from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api import api_router
from app.core.config import Settings, get_settings
from app.core.db import create_tables
from app.core.errors import ApiError, install_exception_handlers, success


STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings = get_settings()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    create_tables()
    yield


app = FastAPI(
    title="衣搭 API",
    version="0.1.0",
    lifespan=lifespan,
)
install_exception_handlers(app)
app.include_router(api_router)
if get_settings().is_development:
    app.mount("/debug-assets", StaticFiles(directory=STATIC_DIR / "debug"), name="debug-assets")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def attach_request_id(request: Request, call_next):
    request.state.request_id = f"req_{uuid4().hex[:12]}"
    response = await call_next(request)
    response.headers["X-Request-Id"] = request.state.request_id
    return response


@app.get("/health")
def health(request: Request):
    return success(request, {"status": "ok"})


@app.get("/debug/wardrobe", include_in_schema=False)
def wardrobe_debug_page(settings: Settings = Depends(get_settings)):
    if not settings.is_development:
        raise ApiError(40401, "页面不存在", 404)
    return FileResponse(STATIC_DIR / "debug" / "wardrobe.html")
