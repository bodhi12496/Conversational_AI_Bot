import json

from fastapi import APIRouter, Request, UploadFile

from app.domain.errors import DomainError
from app.domain.models import (
    AskRequest,
    EditRequest,
    ProjectCreate,
    PublishRequest,
    QueryPlan,
    RegressionCreate,
    RollbackRequest,
    SemanticModel,
    StructuredEdit,
)
from app.repository import now, uid
from app.services.changes import commit_proposal, propose
from app.services.composition import compile_instructions
from app.services.demo_data import INVENTORY, SALES
from app.services.ingestion import ingest
from app.services.query import execute_plan
from app.services.validation import validate_model

router = APIRouter(prefix="/api")


def repo_for(request):
    return request.app.state.repo


def interpreter_for(request):
    return request.app.state.interpreter


@router.get("/config")
def config(request: Request):
    return {
        "provider": request.app.state.settings.provider,
        "version": "0.1.0",
        "scope": "single-owner local workspace",
    }


@router.get("/projects")
def projects(request: Request):
    with repo_for(request).connection() as conn:
        return [dict(row) for row in conn.execute("SELECT * FROM projects ORDER BY created_at DESC")]


@router.post("/projects", status_code=201)
def create_project(body: ProjectCreate, request: Request):
    repo = repo_for(request)
    project_id = uid()
    with repo.connection(write=True) as conn:
        if (
            conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
            >= request.app.state.settings.max_projects
        ):
            raise DomainError("Project limit reached.")
        conn.execute("INSERT INTO projects VALUES(?,?,?,?,?)", (project_id, body.name, 1, None, now()))
        conn.execute(
            "INSERT INTO versions VALUES(?,?,?,?,?)",
            (project_id, 1, SemanticModel().model_dump_json(), "Created project", now()),
        )
        repo.event(conn, project_id, "project_created", {})
        return repo.project(conn, project_id)


@router.get("/projects/{project_id}")
def project_detail(project_id: str, request: Request):
    repo = repo_for(request)
    with repo.connection() as conn:
        project = repo.project(conn, project_id)
        model = repo.version(conn, project_id)
        return {
            "project": project,
            "model": model.model_dump(),
            "instructions": compile_instructions(model),
            "validation": validate_model(conn, project_id, model),
            "versions": [
                dict(row)
                for row in conn.execute(
                    "SELECT number,reason,created_at FROM versions WHERE project_id=? ORDER BY number DESC",
                    (project_id,),
                )
            ],
            "datasets": [
                dict(row) for row in conn.execute("SELECT * FROM datasets WHERE project_id=?", (project_id,))
            ],
            "regressions": [
                dict(row)
                for row in conn.execute("SELECT id,name FROM regressions WHERE project_id=?", (project_id,))
            ],
            "recent_runs": [
                dict(row)
                for row in conn.execute(
                    "SELECT id,version,question,created_at FROM runs WHERE project_id=? ORDER BY created_at DESC LIMIT 20",
                    (project_id,),
                )
            ],
        }


@router.get("/projects/{project_id}/versions/{number}")
def get_version(project_id: str, number: int, request: Request):
    repo = repo_for(request)
    with repo.connection() as conn:
        return repo.version(conn, project_id, number).model_dump()


@router.post("/projects/{project_id}/datasets", status_code=201)
def upload(project_id: str, request: Request, file: UploadFile):
    content = file.file.read(request.app.state.settings.max_upload_bytes + 1)
    return ingest(
        repo_for(request), request.app.state.settings, project_id, content, file.filename or "upload.csv"
    )


@router.post("/projects/{project_id}/demo")
def load_demo(project_id: str, request: Request):
    repo = repo_for(request)
    with repo.connection() as conn:
        if repo.version(conn, project_id).views:
            raise DomainError("Load the sample into an empty project to preserve the example view names.")
    # Two ordinary imports; either can be retried separately through the upload API.
    for filename, content in (("sales.csv", SALES), ("inventory.csv", INVENTORY)):
        ingest(repo, request.app.state.settings, project_id, content, filename)
    return {"loaded": ["sales", "inventory"]}


@router.post("/projects/{project_id}/changes")
def chat_change(project_id: str, body: EditRequest, request: Request):
    repo = repo_for(request)
    with repo.connection() as conn:
        repo.check_base(conn, project_id, body.base_version)
        model = repo.version(conn, project_id, body.base_version)
    # Inference happens outside the database transaction. Commit rechecks the base version.
    try:
        changes = interpreter_for(request).propose(body.message, model)
    except ValueError as exc:
        raise DomainError(
            "The request does not map to a supported semantic change. Clarify the names and scope."
        ) from exc
    if changes.clarification:
        return {"clarification": changes.clarification}
    return propose(repo, project_id, body.base_version, changes)


@router.post("/projects/{project_id}/changes/structured")
def structured_change(project_id: str, body: StructuredEdit, request: Request):
    return propose(repo_for(request), project_id, body.base_version, body.changes)


@router.post("/projects/{project_id}/proposals/{proposal_id}/apply")
def apply_change(project_id: str, proposal_id: str, request: Request):
    return commit_proposal(repo_for(request), project_id, proposal_id)


@router.post("/projects/{project_id}/publish")
def publish(project_id: str, body: PublishRequest, request: Request):
    repo = repo_for(request)
    with repo.connection(write=True) as conn:
        repo.check_base(conn, project_id, body.version)
        model = repo.version(conn, project_id, body.version)
        if not model.selected_views:
            raise DomainError("Select at least one semantic view before publishing.")
        report = validate_model(conn, project_id, model)
        if not report["valid"]:
            raise DomainError("Validation failed: " + "; ".join(report["errors"]))
        if report["warnings"] and not body.acknowledge_inferred_definitions:
            raise DomainError("Review and acknowledge the validation warnings before publishing.")
        conn.execute("UPDATE projects SET active=? WHERE id=?", (body.version, project_id))
        repo.event(
            conn,
            project_id,
            "published",
            {"version": body.version, "acknowledged_warnings": report["warnings"]},
        )
        return {"active_version": body.version, "validation": report}


@router.post("/projects/{project_id}/rollback")
def rollback(project_id: str, body: RollbackRequest, request: Request):
    repo = repo_for(request)
    with repo.connection(write=True) as conn:
        repo.check_base(conn, project_id, body.base_version)
        model = repo.version(conn, project_id, body.target_version)
        report = validate_model(conn, project_id, model)
        if not report["valid"]:
            raise DomainError("Rollback fails current reference tests: " + "; ".join(report["errors"]))
        version = repo.add_version(
            conn,
            project_id,
            model,
            f"Restored version {body.target_version} as a new draft",
            body.base_version,
        )
        return {"version": version, "status": "draft", "validation": report}


def run_question(request: Request, project_id: str, question: str, plan=None):
    repo = repo_for(request)
    with repo.connection() as conn:
        project = repo.project(conn, project_id)
        version = project["active"]
        if version is None:
            raise DomainError("Publish a reviewed semantic model before asking questions.")
        model = repo.version(conn, project_id, version)
    if plan is None:
        plan = interpreter_for(request).plan(question, model)
    if plan.clarification:
        return {"clarification": plan.clarification, "version": version}
    with repo.connection() as conn:
        result = execute_plan(conn, project_id, model, plan)
    result.update({"id": uid(), "version": version, "question": question})
    with repo.connection(write=True) as conn:
        conn.execute(
            "INSERT INTO runs VALUES(?,?,?,?,?,?)",
            (
                result["id"],
                project_id,
                version,
                question,
                json.dumps(result, allow_nan=False),
                now(),
            ),
        )
    return result


@router.post("/projects/{project_id}/ask")
def ask(project_id: str, body: AskRequest, request: Request):
    return run_question(request, project_id, body.message)


@router.post("/projects/{project_id}/query")
def typed_query(project_id: str, body: QueryPlan, request: Request):
    return run_question(request, project_id, "[typed analytics plan]", body)


@router.get("/projects/{project_id}/runs/{run_id}")
def get_run(project_id: str, run_id: str, request: Request):
    repo = repo_for(request)
    with repo.connection() as conn:
        repo.project(conn, project_id)
        row = conn.execute(
            "SELECT result FROM runs WHERE id=? AND project_id=?", (run_id, project_id)
        ).fetchone()
        if not row:
            raise DomainError("Run not found.", 404)
        return json.loads(row["result"])


@router.post("/projects/{project_id}/regressions", status_code=201)
def add_regression(project_id: str, body: RegressionCreate, request: Request):
    repo = repo_for(request)
    with repo.connection(write=True) as conn:
        repo.project(conn, project_id)
        if (
            conn.execute("SELECT COUNT(*) FROM regressions WHERE project_id=?", (project_id,)).fetchone()[0]
            >= 50
        ):
            raise DomainError("At most 50 reference tests are supported per project.")
        if body.plan.clarification:
            raise DomainError("A reference test needs an executable query plan.")
        test_id = uid()
        conn.execute(
            "INSERT INTO regressions VALUES(?,?,?,?,?)",
            (
                test_id,
                project_id,
                body.name,
                body.plan.model_dump_json(),
                json.dumps(body.expected_rows, allow_nan=False),
            ),
        )
        repo.event(conn, project_id, "reference_test_added", {"id": test_id, "name": body.name})
        return {"id": test_id}


@router.delete("/projects/{project_id}/regressions/{test_id}")
def remove_regression(project_id: str, test_id: str, request: Request):
    repo = repo_for(request)
    with repo.connection(write=True) as conn:
        repo.project(conn, project_id)
        count = conn.execute(
            "DELETE FROM regressions WHERE project_id=? AND id=?", (project_id, test_id)
        ).rowcount
        if not count:
            raise DomainError("Reference test not found.", 404)
        repo.event(conn, project_id, "reference_test_removed", {"id": test_id})
        return {"deleted": True}


@router.get("/projects/{project_id}/audit")
def audit(project_id: str, request: Request):
    repo = repo_for(request)
    with repo.connection() as conn:
        repo.project(conn, project_id)
        return [
            dict(row)
            for row in conn.execute(
                "SELECT * FROM events WHERE project_id=? ORDER BY id DESC LIMIT 100", (project_id,)
            )
        ]
