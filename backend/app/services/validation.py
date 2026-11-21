import json

from app.domain.errors import DomainError
from app.domain.models import QueryPlan, SemanticModel
from app.services.ingestion import quote
from app.services.query import column, execute_plan, filters_sql, metric_sql, rows_match, view_map


def validate_model(conn, project_id: str, model: SemanticModel):
    errors, warnings, checks = [], [], []
    views = view_map(model)
    if len(views) != len(model.views):
        errors.append("View IDs must be unique.")
    if len(set(model.selected_views)) != len(model.selected_views) or any(
        v not in views for v in model.selected_views
    ):
        errors.append("Selected views must exist and be unique.")
    for view in model.views:
        try:
            dataset = conn.execute(
                "SELECT * FROM datasets WHERE id=? AND project_id=?", (view.dataset_id, project_id)
            ).fetchone()
            if not dataset:
                raise DomainError("Referenced dataset does not belong to this project.")
            names = [c.name for c in view.columns]
            physical = [r["name"] for r in conn.execute(f"PRAGMA table_info({quote(view.dataset_id)})")]
            if names != physical:
                raise DomainError("Semantic columns must match the immutable dataset schema.")
            if len({m.name for m in view.metrics}) != len(view.metrics):
                raise DomainError("Metric names must be unique within a view.")
            filters_sql(view, view.filters)
            for metric in view.metrics:
                sql = metric_sql(view, metric)
                where, params = filters_sql(view, view.filters + metric.filters)
                conn.execute(f"SELECT {sql} FROM {quote(view.dataset_id)} WHERE {where}", params).fetchone()
            checks.append(f"{view.id}: schema, metric grammar, filters and aggregate execution passed.")
            if view.grain.startswith("Unconfirmed"):
                warnings.append(f"{view.id}: row grain still needs business confirmation.")
            for m in view.metrics:
                if not m.confirmed or m.unit == "unspecified":
                    warnings.append(f"{view.id}.{m.name}: confirm meaning, additivity and units.")
            if any(c.sensitive for c in view.columns):
                warnings.append(
                    f"{view.id}: suspected sensitive columns are blocked from analytics; name-based detection is incomplete."
                )
        except (DomainError, ArithmeticError) as exc:
            errors.append(f"{view.id}: {exc}")
    seen = set()
    for r in model.relationships:
        try:
            pair = tuple(sorted((r.left_view, r.right_view)))
            if pair in seen or r.left_view == r.right_view:
                raise DomainError("Use one relationship per distinct view pair in v0.1.")
            seen.add(pair)
            if r.left_view not in views or r.right_view not in views:
                raise DomainError("Relationship refers to an unknown view.")
            left, right = views[r.left_view], views[r.right_view]
            lc, rc = column(left, r.left_key), column(right, r.right_key)
            if lc.dtype != rc.dtype:
                raise DomainError("Join-key types differ. Normalize them before uploading.")
            stats = []
            for view, key in ((left, r.left_key), (right, r.right_key)):
                stats.append(
                    conn.execute(
                        f"SELECT COUNT(*) AS n, COUNT({quote(key)}) AS nonnull, COUNT(DISTINCT {quote(key)}) AS unique_n FROM {quote(view.dataset_id)}"
                    ).fetchone()
                )
            if any(s["n"] != s["nonnull"] for s in stats):
                raise DomainError("Confirmed relationship keys must not contain nulls.")
            if r.cardinality in ("one_to_one", "one_to_many") and stats[0]["n"] != stats[0]["unique_n"]:
                raise DomainError("The left key is not unique as declared.")
            if r.cardinality in ("one_to_one", "many_to_one") and stats[1]["n"] != stats[1]["unique_n"]:
                raise DomainError("The right key is not unique as declared.")
            if not r.confirmed:
                warnings.append("An unconfirmed relationship cannot be used for combined answers.")
            checks.append(
                f"{r.left_view} ↔ {r.right_view}: key types, nulls and declared cardinality passed."
            )
        except DomainError as exc:
            errors.append(str(exc))
    # Reference answers are authored independently by the project owner, never by the proposal model.
    if not errors:
        for row in conn.execute("SELECT * FROM regressions WHERE project_id=?", (project_id,)):
            try:
                result = execute_plan(conn, project_id, model, QueryPlan.model_validate_json(row["plan"]))
                if not rows_match(result["rows"], json.loads(row["expected_rows"])):
                    raise DomainError("Expected reference rows changed.")
                checks.append(f"Regression passed: {row['name']}")
            except DomainError as exc:
                errors.append(f"Regression {row['name']}: {exc}")
    if not conn.execute("SELECT 1 FROM regressions WHERE project_id=? LIMIT 1", (project_id,)).fetchone():
        warnings.append(
            "No independently authored reference tests are registered. Structural validation does not prove business correctness."
        )
    return {"valid": not errors, "errors": errors, "warnings": warnings, "checks": checks}
