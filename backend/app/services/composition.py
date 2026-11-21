from app.domain.models import SemanticModel


def compile_instructions(model: SemanticModel):
    views = [v for v in model.views if v.id in model.selected_views]
    relationships = [
        r.model_dump()
        for r in model.relationships
        if r.confirmed and r.left_view in model.selected_views and r.right_view in model.selected_views
    ]
    return {
        "selected_views": model.selected_views,
        "orchestration": [
            "Use only the selected semantic views and their defined metrics.",
            "Resolve ambiguity before querying; reject unsupported calculations.",
            "For two-view queries, require one confirmed shared-key relationship.",
            "Aggregate each source independently, then full-outer-merge at that common key.",
            "Never join raw fact rows. Do not rank or infer a time comparison.",
            "Pin the published version for the complete run.",
        ],
        "response": [
            "Return computed values, definitions, parameterized SQL and source timestamps.",
            "Label inferred meanings, absent matches, truncation and separate source snapshots.",
            "Use null for absent groups, not an invented zero.",
        ],
        "metric_catalog": {v.id: [m.model_dump() for m in v.metrics] for v in views},
        "relationships": relationships,
        "sample_prompts": [f"Show {v.id}.{m.name}." for v in views for m in v.metrics[:2]],
        "samples_status": "Generated suggestions; not independent correctness tests.",
        "fiscal_year_start_month": model.fiscal_year_start_month,
    }
