"""An intentionally narrow, offline command interpreter, not an LLM simulation."""

import re

from app.domain.models import ChangeSet, QueryPlan, SemanticModel


class DemoInterpreter:
    def propose(self, message: str, model: SemanticModel):
        text = message.strip().rstrip(".")
        match = re.fullmatch(r"Define (\w+) as (.+?) in (\w+)", text, re.I)
        if match:
            name, expression, view = match.groups()
            expression = (
                expression.lower()
                .replace(" minus ", " - ")
                .replace(" plus ", " + ")
                .replace(" times ", " * ")
            )
            return ChangeSet.model_validate(
                {
                    "summary": f"Define {view}.{name} as a sum of {expression}.",
                    "operations": [
                        {
                            "op": "upsert_metric",
                            "view_id": view.lower(),
                            "metric": {
                                "name": name.lower(),
                                "description": f"User-defined sum of {expression}.",
                                "aggregation": "sum",
                                "expression": expression,
                                "confirmed": True,
                            },
                        }
                    ],
                }
            )
        match = re.fullmatch(r"Exclude (cancelled|canceled) orders from (\w+)", text, re.I)
        if match:
            status, view_id = (s.lower() for s in match.groups())
            view = next((v for v in model.views if v.id == view_id), None)
            filters = [f.model_dump() for f in view.filters] if view else []
            filters = [
                f
                for f in filters
                if not (f["column"] == "status" and f["op"] == "ne" and f["value"] == status)
            ]
            filters.append({"column": "status", "op": "ne", "value": status})
            return ChangeSet.model_validate(
                {
                    "summary": f"Exclude status '{status}' from all {view_id} metrics; null status also excluded by SQL semantics.",
                    "operations": [{"op": "set_view_filters", "view_id": view_id, "filters": filters}],
                }
            )
        match = re.fullmatch(r"Describe (\w+)\.(\w+) as (.+)", text, re.I)
        if match:
            view, col, description = match.groups()
            return ChangeSet.model_validate(
                {
                    "summary": "Update column description.",
                    "operations": [
                        {
                            "op": "describe_column",
                            "view_id": view.lower(),
                            "column": col.lower(),
                            "description": description,
                        }
                    ],
                }
            )
        match = re.fullmatch(r"Set grain of (\w+) to (.+)", text, re.I)
        if match:
            view, grain = match.groups()
            return ChangeSet.model_validate(
                {
                    "summary": "Confirm row grain.",
                    "operations": [{"op": "set_grain", "view_id": view.lower(), "grain": grain}],
                }
            )
        match = re.fullmatch(
            r"Link (\w+)\.(\w+) to (\w+)\.(\w+) as (one_to_one|one_to_many|many_to_one|many_to_many)",
            text,
            re.I,
        )
        if match:
            left, lk, right, rk, cardinality = [s.lower() for s in match.groups()]
            return ChangeSet.model_validate(
                {
                    "summary": "Confirm a business relationship for aggregate-before-merge queries.",
                    "operations": [
                        {
                            "op": "set_relationship",
                            "relationship": {
                                "left_view": left,
                                "left_key": lk,
                                "right_view": right,
                                "right_key": rk,
                                "cardinality": cardinality,
                                "description": f"User states {left}.{lk} and {right}.{rk} identify the same entity.",
                                "confirmed": True,
                            },
                        }
                    ],
                }
            )
        match = re.fullmatch(r"Set fiscal year to (\w+)", text, re.I)
        if match:
            months = [
                "january",
                "february",
                "march",
                "april",
                "may",
                "june",
                "july",
                "august",
                "september",
                "october",
                "november",
                "december",
            ]
            if match[1].lower() in months:
                return ChangeSet.model_validate(
                    {
                        "summary": "Store fiscal calendar metadata; fiscal grouping is not implemented in v0.1.",
                        "operations": [
                            {"op": "set_fiscal_year", "month": months.index(match[1].lower()) + 1}
                        ],
                    }
                )
        return ChangeSet(
            summary="More detail needed.",
            clarification="Demo mode supports the exact examples in the interface. Enable Bedrock for broader wording; unsupported edits are never silently applied.",
        )

    def plan(self, message: str, model: SemanticModel):
        match = re.fullmatch(
            r"Show ([a-z0-9_.]+(?: and [a-z0-9_.]+)*)(?: by ([a-z0-9_.]+))?",
            message.strip().rstrip("."),
            re.I,
        )
        if not match:
            return QueryPlan(
                clarification="In demo mode use: Show sales.revenue by sales.product_id. Ranking, time intelligence and free-form analysis require additional planner support."
            )
        refs = []
        for token in match[1].lower().split(" and "):
            options = [
                f"{v.id}.{m.name}"
                for v in model.views
                if v.id in model.selected_views
                for m in v.metrics
                if token == f"{v.id}.{m.name}" or token == m.name
            ]
            if len(options) != 1:
                return QueryPlan(
                    clarification=f"Metric '{token}' is missing or ambiguous. Use a qualified metric name from the semantic model."
                )
            refs.append(options[0])
        group = match[2].lower() if match[2] else None
        if group and "." not in group:
            # Prefer the first metric's view; cross-view mapping is checked by the engine.
            group = refs[0].split(".")[0] + "." + group
        return QueryPlan(metrics=refs, group_by=group)
