from __future__ import annotations

import ipaddress
from contextlib import asynccontextmanager
from uuid import UUID

import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, PlainTextResponse

from .config import Settings
from .control_plane import AuthorizationError, ConflictError, ControlPlane, NotFoundError
from .database import Database, connect
from .input_vault import DpapiTaskInputVault, InMemoryTaskInputVault, TaskInputStore
from .schemas import (
    ApprovalAuthorize,
    ApprovalCreate,
    ApprovalResolve,
    ApprovalView,
    ArtifactCreate,
    ArtifactView,
    HealthCheckCreate,
    StateTransitionRequest,
    TaskCreate,
    TaskView,
    ValidationRequest,
)
from .security import token_matches
from .state_machine import InvalidTransition


def create_app(
    settings: Settings | None = None,
    database: Database | None = None,
    input_vault: TaskInputStore | None = None,
) -> FastAPI:
    configured = settings or Settings.from_env()
    configured.validate()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        db = database or connect(configured)
        app.state.database = db
        app.state.control = ControlPlane(db, configured)
        app.state.input_vault = input_vault or (
            InMemoryTaskInputVault() if configured.environment == "test" else DpapiTaskInputVault()
        )
        try:
            yield
        finally:
            if database is None:
                db.close()

    app = FastAPI(title="PAIOS Single-Host Control Plane", version="2.0.0", lifespan=lifespan)
    app.state.settings = configured

    @app.middleware("http")
    async def loopback_only(request: Request, call_next):
        client = request.client.host if request.client else ""
        if configured.test_auth_bypass and client == "testclient":
            return await call_next(request)
        try:
            if not ipaddress.ip_address(client).is_loopback:
                return PlainTextResponse("loopback only", status_code=status.HTTP_403_FORBIDDEN)
        except ValueError:
            return PlainTextResponse("loopback only", status_code=status.HTTP_403_FORBIDDEN)
        return await call_next(request)

    def control(request: Request) -> ControlPlane:
        return request.app.state.control

    def owner(
        request: Request,
        authorization: str | None = Header(default=None),
        x_paios_owner_token: str | None = Header(default=None),
    ) -> str:
        if configured.test_auth_bypass:
            return configured.owner_id
        candidate = x_paios_owner_token
        if authorization and authorization.lower().startswith("bearer "):
            candidate = authorization[7:]
        if not token_matches(candidate, configured.owner_token):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="owner authentication required")
        return configured.owner_id

    @app.exception_handler(NotFoundError)
    async def not_found(_: Request, exc: NotFoundError):
        return PlainTextResponse(str(exc), status_code=404)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError):
        safe_errors = [
            {key: value for key, value in item.items() if key not in {"input", "ctx"}}
            for item in exc.errors()
        ]
        return JSONResponse({"detail": safe_errors}, status_code=422)

    @app.exception_handler(ConflictError)
    async def conflict(_: Request, exc: ConflictError):
        return PlainTextResponse(str(exc), status_code=409)

    @app.exception_handler(InvalidTransition)
    async def invalid_transition(_: Request, exc: InvalidTransition):
        return PlainTextResponse(str(exc), status_code=409)

    @app.exception_handler(AuthorizationError)
    async def forbidden(_: Request, exc: AuthorizationError):
        return PlainTextResponse(str(exc), status_code=403)

    @app.get("/health")
    def health(cp: ControlPlane = Depends(control)) -> dict[str, object]:
        vault_ok = bool(app.state.input_vault.health())
        return {"status": "PASS" if cp.database.ping() and vault_ok else "FAIL", "component": "paios-api", "database": cp.database.dialect, "input_vault": vault_ok}

    @app.get("/live")
    def live() -> dict[str, str]:
        return {"status": "PASS", "component": "paios-api"}

    @app.get("/metrics", response_class=PlainTextResponse)
    def metrics(cp: ControlPlane = Depends(control)) -> str:
        states = cp.database.execute("SELECT current_state, COUNT(*) AS count FROM tasks GROUP BY current_state").fetchall()
        lines = ["# HELP paios_tasks_total Tasks by state", "# TYPE paios_tasks_total gauge"]
        lines.extend(f'paios_tasks_total{{state="{row["current_state"]}"}} {row["count"]}' for row in states)
        return "\n".join(lines) + "\n"

    @app.post("/v1/tasks", response_model=TaskView, status_code=201)
    def create_task(payload: TaskCreate, request: Request, actor: str = Depends(owner), cp: ControlPlane = Depends(control)) -> TaskView:
        task = cp.create_task(payload, actor)
        try:
            request.app.state.input_vault.put(str(task.task_id), payload.objective, payload.metadata)
        except Exception:
            cp.transition(task.task_id, StateTransitionRequest(to_state="FAILED", reason_code="INPUT_VAULT_FAILURE"))
            raise HTTPException(status_code=503, detail="secure task input unavailable")
        return task

    @app.get("/v1/tasks", response_model=list[TaskView])
    def list_tasks(limit: int = Query(default=100, ge=1, le=1000), _: str = Depends(owner), cp: ControlPlane = Depends(control)) -> list[TaskView]:
        return cp.list_tasks(limit)

    @app.get("/v1/tasks/{task_id}", response_model=TaskView)
    def get_task(task_id: UUID, _: str = Depends(owner), cp: ControlPlane = Depends(control)) -> TaskView:
        return cp.get_task(task_id)

    @app.post("/v1/tasks/{task_id}/transition", response_model=TaskView)
    def transition(task_id: UUID, payload: StateTransitionRequest, _: str = Depends(owner), cp: ControlPlane = Depends(control)) -> TaskView:
        return cp.transition(task_id, payload)

    @app.post("/v1/approvals", response_model=ApprovalView, status_code=201)
    def create_approval(payload: ApprovalCreate, actor: str = Depends(owner), cp: ControlPlane = Depends(control)) -> ApprovalView:
        return cp.create_approval(payload, actor)

    @app.post("/v1/approvals/{approval_id}/resolve", response_model=ApprovalView)
    def resolve_approval(approval_id: UUID, payload: ApprovalResolve, actor: str = Depends(owner), cp: ControlPlane = Depends(control)) -> ApprovalView:
        return cp.resolve_approval(approval_id, payload, actor)

    @app.post("/v1/approvals/{approval_id}/authorize", response_model=ApprovalView)
    def authorize_approval(approval_id: UUID, payload: ApprovalAuthorize, _: str = Depends(owner), cp: ControlPlane = Depends(control)) -> ApprovalView:
        return cp.authorize_approval(approval_id, payload)

    @app.post("/v1/artifacts", response_model=ArtifactView, status_code=201)
    def add_artifact(payload: ArtifactCreate, _: str = Depends(owner), cp: ControlPlane = Depends(control)) -> ArtifactView:
        return cp.add_artifact(payload)

    @app.post("/v1/validate", response_model=TaskView)
    def validate(payload: ValidationRequest, _: str = Depends(owner), cp: ControlPlane = Depends(control)) -> TaskView:
        return cp.validate_result(payload)

    @app.post("/v1/health-checks", status_code=201)
    def health_check(payload: HealthCheckCreate, _: str = Depends(owner), cp: ControlPlane = Depends(control)) -> dict[str, str]:
        return {"check_id": str(cp.record_health(payload))}

    return app


def main() -> None:
    settings = Settings.from_env()
    uvicorn.run(create_app(settings), host=settings.bind_host, port=settings.bind_port, log_config=None)


if __name__ == "__main__":
    main()
