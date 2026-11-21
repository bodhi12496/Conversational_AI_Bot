# API examples

The OpenAPI schema at `/api/openapi.json` is generated from the request types. The interactive `/api/docs` page loads its Swagger assets from jsDelivr and needs internet access. All examples assume the local server at `http://127.0.0.1:8000`.

If a workspace token is configured, add `Authorization: Bearer YOUR_TOKEN` to each API request. These examples omit it for the default loopback demo.

## Create and import

```bash
curl -X POST http://127.0.0.1:8000/api/projects \
  -H 'Content-Type: application/json' -d '{"name":"Sales workspace"}'
```

Copy the returned `id` and use it as `PROJECT_ID` in the examples below. `python scripts/demo.py` automates the complete flow without requiring curl or jq.

```bash
curl -X POST http://127.0.0.1:8000/api/projects/PROJECT_ID/datasets \
  -F 'file=@sample_data/sales.csv'
curl http://127.0.0.1:8000/api/projects/PROJECT_ID
```

The project detail response contains the current draft `head`, `active` published version, full semantic model, validation report and compiled instructions. Do not guess version numbers; carry them forward from responses.

## Propose a correction

```http
POST /api/projects/PROJECT_ID/changes
Content-Type: application/json

{
  "base_version": 2,
  "message": "Define revenue as amount minus refund in sales."
}
```

The result includes the proposal `id`, summary, typed operations, exact diff and validation report. Clarifications return without a proposal. A pending proposal with failed validation cannot be applied.

```http
POST /api/projects/PROJECT_ID/proposals/PROPOSAL_ID/apply
```

A stale base or already-applied proposal returns HTTP 409. Applying creates a draft, not a release.

## Use the typed operation API

The same route used by the view picker can create exact developer-controlled proposals. It does not bypass validation or review.

```http
POST /api/projects/PROJECT_ID/changes/structured
Content-Type: application/json

{
  "base_version": 4,
  "changes": {
    "summary": "Confirm revenue units and select Sales and Inventory.",
    "operations": [
      {
        "op": "upsert_metric",
        "view_id": "sales",
        "metric": {
          "name": "revenue",
          "description": "Order amount minus refund, after cancellation filtering.",
          "aggregation": "sum",
          "expression": "amount - refund",
          "unit": "INR",
          "filters": [],
          "confirmed": true
        }
      },
      {"op": "select_views", "view_ids": ["sales", "inventory"]}
    ]
  }
}
```

The complete union is defined in `backend/app/domain/models.py` and exported into `docs/schemas/change-set.schema.json`. Upserting a metric replaces that metric's complete definition; include any existing metric filters that should be preserved.

## Publish and query

```http
POST /api/projects/PROJECT_ID/publish
Content-Type: application/json

{"version": 7, "acknowledge_inferred_definitions": true}
```

```http
POST /api/projects/PROJECT_ID/ask
Content-Type: application/json

{"message": "Show sales.revenue and inventory.total_stock by sales.product_id."}
```

For deterministic application integration, submit a logical query plan directly:

```http
POST /api/projects/PROJECT_ID/query
Content-Type: application/json

{
  "metrics": ["sales.revenue"],
  "group_by": "sales.product_id",
  "filters": {
    "sales": [{"column": "order_date", "op": "gte", "value": "2026-01-01"}]
  },
  "limit": 100
}
```

Both routes require a published version and use the same execution engine. The response carries rows, logical plan, compiled queries, evidence, warnings, pinned version and run ID. No route accepts raw SQL.

## Reference tests

```http
POST /api/projects/PROJECT_ID/regressions
Content-Type: application/json

{
  "name": "Finance checked revenue",
  "plan": {"metrics": ["sales.revenue"]},
  "expected_rows": [{"sales.revenue": 415}]
}
```

A reference can be saved even if the draft currently fails it; publishing and future edits then fail until resolved. Tests compare row keys and scalar values, with small numeric tolerance. No model-generated evaluation is treated as an independent answer.

## Restore and inspect

| Request | Behavior |
|---|---|
| `GET /api/projects/ID/versions/N` | Export a historical semantic snapshot. |
| `POST /api/projects/ID/rollback` with `base_version`, `target_version` | Validate and copy the target into a new draft; does not publish. |
| `GET /api/projects/ID/runs/RUN_ID` | Retrieve the exact stored result and evidence. |
| `GET /api/projects/ID/audit` | Return the latest 100 audit events. |
| `DELETE /api/projects/ID/regressions/TEST_ID` | Remove an owner-managed reference test and record the event. |

Validation errors use HTTP 422, absent resources 404, token errors 401, stale edits 409 and model-provider failures 502. Unsupported natural-language requests may return HTTP 200 with a `clarification` field; consumers must handle it before rendering a result.
