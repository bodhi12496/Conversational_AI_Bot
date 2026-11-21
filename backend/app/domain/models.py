from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

Identifier = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{0,62}$")]
Scalar = str | int | float | bool


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Column(StrictModel):
    name: Identifier
    source_name: str
    dtype: Literal["integer", "number", "text", "date"]
    description: str = ""
    null_count: int = 0
    distinct_count: int = 0
    candidate_key: bool = False
    sensitive: bool = False


class Filter(StrictModel):
    column: Identifier
    op: Literal["eq", "ne", "gt", "gte", "lt", "lte", "in", "not_in", "is_null", "not_null"]
    value: Scalar | list[Scalar] | None = None


class Metric(StrictModel):
    name: Identifier
    description: str = Field(min_length=1, max_length=2000)
    aggregation: Literal["sum", "avg", "count", "count_distinct", "min", "max"]
    expression: str = Field(default="*", min_length=1, max_length=500)
    unit: str = Field(default="unspecified", max_length=100)
    filters: list[Filter] = Field(default_factory=list, max_length=20)
    confirmed: bool = False


class View(StrictModel):
    id: Identifier
    dataset_id: str
    name: str
    description: str = ""
    grain: str = "Unconfirmed: one uploaded row. Confirm its business meaning."
    columns: list[Column]
    metrics: list[Metric]
    filters: list[Filter] = Field(default_factory=list, max_length=20)


class Relationship(StrictModel):
    left_view: Identifier
    left_key: Identifier
    right_view: Identifier
    right_key: Identifier
    cardinality: Literal["one_to_one", "one_to_many", "many_to_one", "many_to_many"]
    description: str = Field(min_length=5, max_length=2000)
    confirmed: bool = False


class SemanticModel(StrictModel):
    schema_version: Literal[1] = 1
    views: list[View] = Field(default_factory=list, max_length=12)
    selected_views: list[Identifier] = Field(default_factory=list, max_length=12)
    relationships: list[Relationship] = Field(default_factory=list, max_length=66)
    fiscal_year_start_month: int = Field(default=1, ge=1, le=12)


class DescribeColumn(StrictModel):
    op: Literal["describe_column"]
    view_id: Identifier
    column: Identifier
    description: str = Field(min_length=1, max_length=2000)


class SetGrain(StrictModel):
    op: Literal["set_grain"]
    view_id: Identifier
    grain: str = Field(min_length=5, max_length=1000)


class UpsertMetric(StrictModel):
    op: Literal["upsert_metric"]
    view_id: Identifier
    metric: Metric


class SetFilters(StrictModel):
    op: Literal["set_view_filters"]
    view_id: Identifier
    filters: list[Filter] = Field(max_length=20)


class SetRelationship(StrictModel):
    op: Literal["set_relationship"]
    relationship: Relationship


class SelectViews(StrictModel):
    op: Literal["select_views"]
    view_ids: list[Identifier] = Field(max_length=12)


class SetFiscalYear(StrictModel):
    op: Literal["set_fiscal_year"]
    month: int = Field(ge=1, le=12)


Operation = Annotated[
    DescribeColumn | SetGrain | UpsertMetric | SetFilters | SetRelationship | SelectViews | SetFiscalYear,
    Field(discriminator="op"),
]


class ChangeSet(StrictModel):
    summary: str = Field(min_length=1, max_length=2000)
    clarification: str | None = Field(default=None, max_length=2000)
    operations: list[Operation] = Field(default_factory=list, max_length=20)


class QueryPlan(StrictModel):
    metrics: list[str] = Field(default_factory=list, max_length=8)
    group_by: str | None = None
    filters: dict[str, list[Filter]] = Field(default_factory=dict)
    limit: int = Field(default=100, ge=1, le=500)
    clarification: str | None = Field(default=None, max_length=2000)


class ProjectCreate(StrictModel):
    name: str = Field(min_length=1, max_length=100)


class EditRequest(StrictModel):
    message: str = Field(min_length=1, max_length=4000)
    base_version: int = Field(ge=1)


class StructuredEdit(StrictModel):
    base_version: int = Field(ge=1)
    changes: ChangeSet


class PublishRequest(StrictModel):
    version: int = Field(ge=1)
    acknowledge_inferred_definitions: bool = False


class AskRequest(StrictModel):
    message: str = Field(min_length=1, max_length=4000)


class RollbackRequest(StrictModel):
    base_version: int = Field(ge=1)
    target_version: int = Field(ge=1)


class RegressionCreate(StrictModel):
    name: str = Field(min_length=1, max_length=100)
    plan: QueryPlan
    expected_rows: list[dict[str, Scalar | None]] = Field(max_length=500)
