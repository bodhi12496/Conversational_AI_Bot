# Semantic model and conversational correction logic

## What a semantic view means here

One uploaded table creates one platform semantic view. It references an immutable dataset and holds columns, descriptions, row grain, metric definitions and default filters. The project model also contains selected views, relationships and fiscal calendar metadata.

The automatic draft establishes observable properties: types, nulls, distinct values and candidate unique columns. Business descriptions and additive measures are suggestions. A number column is not necessarily a meaningful sum; stock snapshots, prices, percentages and balances particularly need review. Detected uniqueness does not establish an entity or a business primary key.

IDs and `*_id`/`*_code` columns stay text, preserving identifiers such as `001`. Dates are inferred only when every non-null value is ISO `YYYY-MM-DD`. Other date formats remain text. Excel date cells may remain text after normalization and should be standardized before analytical use. Currency parsing, date normalization and implicit unit conversion are not performed.

## A metric is executable structured data

```json
{
  "name": "revenue",
  "description": "Order amount less refunds, after the view's cancellation filter.",
  "aggregation": "sum",
  "expression": "amount - refund",
  "unit": "INR",
  "filters": [],
  "confirmed": true
}
```

`aggregation` is an enum. Arithmetic expressions are parsed into Python's syntax tree and compiled with a tiny allowlist: existing numeric column names, finite constants, parentheses, unary signs and `+`, `-`, `*`. The parser does not evaluate Python and does not accept calls, attributes, SQL, exponentiation or division.

`count(*)` counts rows. Column counts exclude nulls. `count_distinct` works on one named column. Sum, average, min and max accept the safe numeric expression grammar. Ratios and fiscal calculations require future explicit operations with defined semantics.

View filters apply to every metric in that view; metric filters apply only to that metric; question filters are additional restrictions for that query. A cancellation rule stored at view scope affects row counts and other totals as well as revenue. The UI displays this scope in the diff.

SQLite null semantics apply: `status != 'cancelled'` also excludes null statuses; arithmetic on null produces null; aggregate functions generally ignore null expressions. Sum of an empty set is null and count is zero. This release does not silently coalesce nulls or invent missing business rules.

Numbers use SQLite INTEGER/REAL. Floating-point arithmetic is adequate for the included analytical example but is not exact decimal accounting. Numeric results are checked for non-finite outputs. Add Decimal/warehouse numeric semantics and currency contracts before relying on financial ledger precision.

## How a chat correction changes the backend

1. The owner chooses **Edit definitions**, separating persistent changes from read-only questions.
2. The server loads the requested base version.
3. The interpreter returns a `ChangeSet`, or requests clarification.
4. Each operation belongs to an explicit union: describe a column, set grain, upsert a metric, replace view filters, define a relationship, select views or set the fiscal start month.
5. The change service deep-copies the model. It cannot change dataset ownership, execute code or mutate physical source values.
6. Structural and data-dependent validations run. Registered reference cases run against the candidate.
7. The owner sees the summary and exact JSON diff, including wider filter effects.
8. Applying reruns checks against the still-current base and creates a new draft atomically.
9. Publishing independently checks the reviewed head. Warnings require acknowledgement. Acknowledgement does not turn an inference into proven business truth.
10. Subsequent questions use the published model; already-running questions retain their original version.

Editing a definition is not the same as changing one answer's filter. V0.1 uses an explicit edit/query mode instead of trying to infer this permission-sensitive distinction from chat wording.

## Selecting views

The checkbox picker produces a normal typed proposal. Applying it stores the new selection in a new model revision. The deterministic composition compiler then generates a selected-view catalog, routing instructions, relationship rules, response guidance and suggested questions.

Execution checks the same selected-view state in code. Instructions describe policy, but never enforce access by themselves. After publishing a selection that removes Inventory, a new typed query referring to Inventory is rejected. Historical runs remain available to the single owner.

## Combining views

The owner can say:

```text
Link sales.product_id to inventory.product_id as many_to_one.
```

This asserts both semantic equivalence of the keys and declared row cardinality. Validation checks that both views and keys exist, key types agree, neither key contains nulls, and any side declared `one` is actually unique. Data checks do not prove that two business identifiers mean the same thing; the owner's confirmation supplies that assertion.

The supported compiled question is:

```json
{
  "metrics": ["sales.revenue", "inventory.total_stock"],
  "group_by": "sales.product_id",
  "filters": {},
  "limit": 100
}
```

The engine calculates each metric at its own source, grouping both by the mapped product key. It then merges the already aggregated results. This avoids multiplying inventory when several orders share a product. A many-to-many source cardinality is allowed only in this independent-aggregation workflow; it is not permission to perform a raw many-to-many fact join.

Only one direct relationship per view pair is supported. Composite keys, dimension joins, bridge tables, temporal relationships, multi-hop paths, alternate key mappings and cross-view row filters are deliberately rejected or unavailable. A combined result compares the uploaded snapshots; it does not establish a shared live snapshot or automatically pick an inventory timestamp.

Units of separate side-by-side metrics may differ. The engine does not calculate cross-view arithmetic, convert currencies, sum averages or combine distinct counts. Those require explicit additional contracts.

## Independent correctness tests

Store a manually reviewed logical plan and expected rows through the interface or API. Candidate changes and publishing must preserve those answers. A business definition can legitimately change an answer; its reference test must then be intentionally revised by the owner, with an audit event.

The platform-generated sample prompts are suggestions. Neither a self-generated prompt nor valid SQL is evidence that a business calculation is correct.
