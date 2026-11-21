"""Export the exact Pydantic schemas used by ingestion, changes and analytics."""

import json
from pathlib import Path

from app.domain.models import ChangeSet, QueryPlan, SemanticModel

destination = Path(__file__).resolve().parents[1] / "docs" / "schemas"
destination.mkdir(exist_ok=True)
for name, model in [("semantic-model", SemanticModel), ("change-set", ChangeSet), ("query-plan", QueryPlan)]:
    (destination / f"{name}.schema.json").write_text(json.dumps(model.model_json_schema(), indent=2) + "\n")
print("Exported canonical model, change-set and query-plan JSON schemas.")
