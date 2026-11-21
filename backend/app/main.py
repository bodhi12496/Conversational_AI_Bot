import hmac
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.routes import router
from app.config import Settings
from app.domain.errors import DomainError
from app.providers.demo import DemoInterpreter
from app.repository import Repository


def create_app(settings=None, interpreter=None):
    settings = settings or Settings.from_env()
    app = FastAPI(
        title="COE Conversational Data Platform",
        version="0.1.0",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        redoc_url=None,
    )
    app.state.settings = settings
    app.state.repo = Repository(settings.data_dir)
    if interpreter is None:
        if settings.provider == "bedrock":
            from app.providers.bedrock import BedrockInterpreter

            interpreter = BedrockInterpreter(settings.region, settings.model_id)
        elif settings.provider == "demo":
            interpreter = DemoInterpreter()
        else:
            raise RuntimeError("COE_PROVIDER must be demo or bedrock.")
    app.state.interpreter = interpreter
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "testserver", "[::1]"])

    @app.middleware("http")
    async def local_access(request: Request, call_next):
        if request.url.path.startswith("/api"):
            expected = settings.api_token
            supplied = request.headers.get("authorization", "")
            if expected and not hmac.compare_digest(supplied, "Bearer " + expected):
                return JSONResponse(status_code=401, content={"detail": "A valid API token is required."})
            origin = request.headers.get("origin")
            if (
                request.method not in ("GET", "HEAD", "OPTIONS")
                and origin
                and origin
                not in (
                    "http://" + request.headers.get("host", ""),
                    "https://" + request.headers.get("host", ""),
                )
            ):
                return JSONResponse(status_code=403, content={"detail": "Cross-origin writes are disabled."})
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'"
        )
        if request.url.path == "/api/docs":
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "img-src 'self' data: https://fastapi.tiangolo.com; frame-ancestors 'none'"
            )
        return response

    @app.exception_handler(DomainError)
    async def domain_error(request, exc):
        return JSONResponse(status_code=exc.status, content={"detail": exc.message})

    @app.get("/health")
    def health():
        return {"status": "ok", "version": "0.1.0"}

    app.include_router(router)
    static = Path(__file__).parent / "static"
    static.mkdir(exist_ok=True)
    if (static / "index.html").exists():
        app.mount("/", StaticFiles(directory=static, html=True), name="frontend")
    else:

        @app.get("/")
        def frontend_hint():
            return {
                "message": "Run npm ci and npm run build in frontend, then restart the API.",
                "api_docs": "/api/docs",
            }

    return app
