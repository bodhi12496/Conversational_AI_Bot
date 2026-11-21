import difflib
import json

from app.domain.errors import DomainError
from app.domain.models import ChangeSet
from app.repository import Repository, now, uid
from app.services.validation import validate_model


def apply_operations(model, changes: ChangeSet):
    candidate = model.model_copy(deep=True)
    views = {v.id: v for v in candidate.views}
    if changes.clarification or not changes.operations:
        raise DomainError(changes.clarification or "No change was proposed.")
    for op in changes.operations:
        if hasattr(op, "view_id") and op.view_id not in views:
            raise DomainError(f"Unknown view {op.view_id}.")
        if op.op == "describe_column":
            col = next((c for c in views[op.view_id].columns if c.name == op.column), None)
            if col is None:
                raise DomainError(f"Unknown column {op.column}.")
            col.description = op.description
        elif op.op == "set_grain":
            views[op.view_id].grain = op.grain
        elif op.op == "upsert_metric":
            view = views[op.view_id]
            view.metrics = [m for m in view.metrics if m.name != op.metric.name] + [op.metric]
            if len(view.metrics) > 100:
                raise DomainError("At most 100 metrics per view are supported.")
        elif op.op == "set_view_filters":
            views[op.view_id].filters = op.filters
        elif op.op == "set_relationship":
            relationship = op.relationship
            pair = {relationship.left_view, relationship.right_view}
            candidate.relationships = [
                r for r in candidate.relationships if {r.left_view, r.right_view} != pair
            ] + [relationship]
        elif op.op == "select_views":
            candidate.selected_views = op.view_ids
        elif op.op == "set_fiscal_year":
            candidate.fiscal_year_start_month = op.month
    # Revalidate lengths and field constraints after mutating nested objects.
    return type(candidate).model_validate(candidate.model_dump())


def propose(repo: Repository, project_id: str, base: int, changes: ChangeSet):
    with repo.connection(write=True) as conn:
        repo.check_base(conn, project_id, base)
        model = repo.version(conn, project_id, base)
        candidate = apply_operations(model, changes)
        report = validate_model(conn, project_id, candidate)
        diff = "\n".join(
            difflib.unified_diff(
                json.dumps(model.model_dump(), indent=2).splitlines(),
                json.dumps(candidate.model_dump(), indent=2).splitlines(),
                fromfile=f"version_{base}",
                tofile="proposed_draft",
                lineterm="",
            )
        )
        proposal_id = uid()
        conn.execute(
            "INSERT INTO proposals VALUES(?,?,?,?,?,?,?,?,?)",
            (
                proposal_id,
                project_id,
                base,
                changes.model_dump_json(),
                candidate.model_dump_json(),
                diff,
                json.dumps(report),
                "pending",
                now(),
            ),
        )
        return {
            "id": proposal_id,
            "base_version": base,
            "changes": changes.model_dump(),
            "diff": diff,
            "validation": report,
        }


def commit_proposal(repo: Repository, project_id: str, proposal_id: str):
    with repo.connection(write=True) as conn:
        row = conn.execute(
            "SELECT * FROM proposals WHERE id=? AND project_id=?", (proposal_id, project_id)
        ).fetchone()
        if not row:
            raise DomainError("Proposal not found.", 404)
        if row["status"] != "pending":
            raise DomainError("This proposal has already been applied.", 409)
        repo.check_base(conn, project_id, row["base"])
        from app.domain.models import SemanticModel

        candidate = SemanticModel.model_validate_json(row["candidate"])
        report = validate_model(conn, project_id, candidate)
        if not report["valid"]:
            raise DomainError("Validation failed: " + "; ".join(report["errors"]))
        changes = ChangeSet.model_validate_json(row["changes"])
        number = repo.add_version(conn, project_id, candidate, changes.summary, row["base"])
        conn.execute("UPDATE proposals SET status='applied' WHERE id=?", (proposal_id,))
        return {"version": number, "validation": report, "status": "draft"}
