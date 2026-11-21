import ast
import json
import math
import sqlite3
import time

from app.domain.errors import DomainError
from app.domain.models import Filter, QueryPlan, SemanticModel, View
from app.services.ingestion import quote


def view_map(model: SemanticModel) -> dict[str, View]:
    return {v.id: v for v in model.views}


def column(view: View, name: str, numeric=False):
    result = next((c for c in view.columns if c.name == name), None)
    if result is None:
        raise DomainError(f"Unknown column: {view.id}.{name}.")
    if result.sensitive:
        raise DomainError(f"Column {view.id}.{name} is blocked by the local sensitivity policy.")
    if numeric and result.dtype not in ("integer", "number"):
        raise DomainError(f"Arithmetic requires a numeric column: {view.id}.{name}.")
    return result


def expression_sql(view: View, expression: str):
    """Compile a tiny expression grammar. Never execute a model-supplied SQL string."""
    try:
        root = ast.parse(expression, mode="eval")
    except (SyntaxError, ValueError) as exc:
        raise DomainError("Use column names, numeric constants, parentheses and +, - or *.") from exc
    if sum(1 for _ in ast.walk(root)) > 60:
        raise DomainError("Metric expression is too complex.")

    def compile_node(node):
        if isinstance(node, ast.Name):
            column(view, node.id, numeric=True)
            return quote(node.id)
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            if not math.isfinite(node.value) or abs(node.value) > 1e15:
                raise DomainError("Metric constant is out of range.")
            return repr(node.value)
        if isinstance(node, ast.BinOp) and type(node.op) in (ast.Add, ast.Sub, ast.Mult):
            op = {ast.Add: "+", ast.Sub: "-", ast.Mult: "*"}[type(node.op)]
            return f"({compile_node(node.left)} {op} {compile_node(node.right)})"
        if isinstance(node, ast.UnaryOp) and type(node.op) in (ast.UAdd, ast.USub):
            return f"({'-' if isinstance(node.op, ast.USub) else '+'}{compile_node(node.operand)})"
        raise DomainError("Unsupported metric syntax. SQL, functions and arbitrary Python are not accepted.")

    return compile_node(root.body)


def filters_sql(view: View, filters: list[Filter]):
    clauses, params = [], []
    for f in filters:
        c = column(view, f.column)
        name = quote(f.column)
        if f.op in ("is_null", "not_null"):
            if f.value is not None:
                raise DomainError("Null predicates do not accept a value.")
            clauses.append(f"{name} IS {'NOT ' if f.op == 'not_null' else ''}NULL")
            continue
        values = f.value if isinstance(f.value, list) else [f.value]
        if any(v is None for v in values):
            raise DomainError("Use is_null or not_null for null comparisons.")
        if c.dtype in ("integer", "number") and any(type(v) not in (int, float) for v in values):
            raise DomainError(f"Filter values for {view.id}.{c.name} must be numeric.")
        if c.dtype in ("text", "date") and any(not isinstance(v, str) for v in values):
            raise DomainError(f"Filter values for {view.id}.{c.name} must be strings.")
        if f.op in ("in", "not_in"):
            if not isinstance(f.value, list) or not 1 <= len(values) <= 100:
                raise DomainError("in/not_in requires a list of 1–100 values.")
            clauses.append(
                f"{name} {'NOT IN' if f.op == 'not_in' else 'IN'} ({','.join('?' for _ in values)})"
            )
            params.extend(values)
        else:
            if isinstance(f.value, list):
                raise DomainError("This filter accepts a single value.")
            op = {"eq": "=", "ne": "!=", "gt": ">", "gte": ">=", "lt": "<", "lte": "<="}[f.op]
            clauses.append(f"{name} {op} ?")
            params.append(f.value)
    return (" AND ".join(clauses) if clauses else "1=1"), params


def metric_sql(view, metric):
    if metric.expression == "*":
        if metric.aggregation != "count":
            raise DomainError("Only count supports '*'.")
        expression = "*"
    elif metric.aggregation in ("count", "count_distinct"):
        column(view, metric.expression)
        expression = quote(metric.expression)
    else:
        expression = expression_sql(view, metric.expression)
    aggregation = {
        "sum": "SUM",
        "avg": "AVG",
        "count": "COUNT",
        "count_distinct": "COUNT",
        "min": "MIN",
        "max": "MAX",
    }[metric.aggregation]
    return f"{aggregation}({'DISTINCT ' if metric.aggregation == 'count_distinct' else ''}{expression})"


def resolve_plan(model: SemanticModel, plan: QueryPlan):
    if plan.clarification:
        raise DomainError(plan.clarification)
    if not plan.metrics:
        raise DomainError("Choose at least one defined metric.")
    if len(set(plan.metrics)) != len(plan.metrics):
        raise DomainError("Duplicate metric references are not supported.")
    views = view_map(model)
    resolved = []
    for ref in plan.metrics:
        parts = ref.split(".")
        if len(parts) != 2 or parts[0] not in model.selected_views or parts[0] not in views:
            raise DomainError(f"Metric {ref} is not in the selected views.")
        view = views[parts[0]]
        metric = next((m for m in view.metrics if m.name == parts[1]), None)
        if metric is None:
            raise DomainError(f"Unknown metric {ref}. Define it through chat first.")
        resolved.append((ref, view, metric))
    involved = list(dict.fromkeys(v.id for _, v, _ in resolved))
    if any(v not in involved for v in plan.filters):
        raise DomainError(
            "Question filters must belong to queried views. Cross-view row filtering is unsupported."
        )
    if sum(len(f) for f in plan.filters.values()) > 40:
        raise DomainError("At most 40 question filters are allowed.")
    groups = {}
    if plan.group_by:
        parts = plan.group_by.split(".")
        if len(parts) != 2 or parts[0] not in involved:
            raise DomainError("Group by a column in a queried view.")
        column(views[parts[0]], parts[1])
        groups[parts[0]] = parts[1]
    if len(involved) > 2:
        raise DomainError("The standard version supports at most two queried views per question.")
    if len(involved) == 2:
        if not plan.group_by:
            raise DomainError("For a combined answer, specify the confirmed common key as the grouping.")
        relations = [
            r for r in model.relationships if r.confirmed and {r.left_view, r.right_view} == set(involved)
        ]
        if len(relations) != 1:
            raise DomainError(
                "Define one unambiguous confirmed relationship between these views through chat."
            )
        r = relations[0]
        if groups.get(r.left_view) == r.left_key:
            groups[r.right_view] = r.right_key
        elif groups.get(r.right_view) == r.right_key:
            groups[r.left_view] = r.left_key
        else:
            raise DomainError("Cross-view questions must group by the confirmed relationship key.")
    return resolved, groups


def execute_plan(conn: sqlite3.Connection, project_id: str, model: SemanticModel, plan: QueryPlan):
    resolved, groups = resolve_plan(model, plan)
    deadline = time.monotonic() + 3
    conn.set_progress_handler(lambda: int(time.monotonic() > deadline), 1000)
    result_map, queries, evidence, warnings = {}, [], [], []
    try:
        for ref, view, metric in resolved:
            source = conn.execute(
                "SELECT * FROM datasets WHERE id=? AND project_id=?", (view.dataset_id, project_id)
            ).fetchone()
            if not source:
                raise DomainError("A referenced dataset is unavailable in this project.")
            where, params = filters_sql(view, view.filters + metric.filters + plan.filters.get(view.id, []))
            group = quote(groups[view.id]) if view.id in groups else None
            select = (group + " AS group_key, " if group else "") + metric_sql(view, metric) + " AS value"
            sql = f"SELECT {select} FROM {quote(view.dataset_id)} WHERE {where}"
            if group:
                sql += f" GROUP BY {group} ORDER BY {group} LIMIT 501"
            values = conn.execute(sql, params).fetchall()
            if len(values) > 500:
                raise DomainError(
                    "This question has over 500 groups. Narrow the query before combining results."
                )
            for row in values:
                key = row["group_key"] if group else "__total__"
                if group and key is None:
                    raise DomainError(
                        "The grouping key contains nulls. Define a supported non-null grouping."
                    )
                value = row["value"]
                if isinstance(value, float) and not math.isfinite(value):
                    raise DomainError("The metric result exceeded the numeric range.")
                result_map.setdefault(key, {})[ref] = value
            queries.append({"view_id": view.id, "sql": sql, "parameters": params})
            evidence.append(
                {
                    "metric": ref,
                    "definition": metric.model_dump(),
                    "source": source["source_name"],
                    "loaded_at": source["loaded_at"],
                    "sha256": source["fingerprint"],
                    "view_filters": [f.model_dump() for f in view.filters],
                    "question_filters": [f.model_dump() for f in plan.filters.get(view.id, [])],
                }
            )
            if not metric.confirmed:
                warnings.append(f"{ref}: inferred definition; confirm its business meaning and unit.")
    except sqlite3.OperationalError as exc:
        raise DomainError("Query failed or exceeded the 3-second execution budget.") from exc
    finally:
        conn.set_progress_handler(None, 0)
    if len(result_map) > 500:
        raise DomainError("Combined result exceeds 500 groups. Narrow the query.")
    rows = []
    for key in sorted(result_map, key=lambda k: str(k)):
        item = {plan.group_by: key} if plan.group_by else {}
        item.update({ref: result_map[key].get(ref) for ref in plan.metrics})
        rows.append(item)
    if groups:
        warnings.append(
            "Groups are sorted by key, not ranked by metric. Missing group results are null, not zero."
        )
    if len({v.id for _, v, _ in resolved}) > 1:
        warnings.append(
            "Each view was aggregated independently before a full outer merge on the confirmed key. Uploads are separate snapshots."
        )
    truncated = len(rows) > plan.limit
    rows = rows[: plan.limit]
    if truncated:
        warnings.append(f"Showing the first {plan.limit} groups; the result is truncated.")
    warnings.append(
        "Numeric calculations use SQLite INTEGER/REAL; financial exact-decimal accounting is outside v0.1."
    )
    return {
        "columns": ([plan.group_by] if plan.group_by else []) + plan.metrics,
        "rows": rows,
        "queries": queries,
        "evidence": evidence,
        "warnings": list(dict.fromkeys(warnings)),
        "truncated": truncated,
        "plan": plan.model_dump(),
        "summary": f"Computed {len(plan.metrics)} metric(s); returned {len(rows)} row(s).",
    }


def rows_match(actual, expected):
    if len(actual) != len(expected):
        return False

    def canonical(row):
        return json.dumps(row, sort_keys=True, default=str)

    actual, expected = sorted(actual, key=canonical), sorted(expected, key=canonical)
    for left, right in zip(actual, expected, strict=True):
        if left.keys() != right.keys():
            return False
        for key, value in left.items():
            other = right[key]
            if type(value) in (float, int) and type(other) in (float, int):
                if not math.isclose(value, other, rel_tol=1e-9, abs_tol=1e-8):
                    return False
            elif value != other:
                return False
    return True
