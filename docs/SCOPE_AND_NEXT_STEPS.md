# Scope, known limits and next milestones

## What this release establishes

V0.1 makes the central semantic workflow concrete. You can upload data, inspect its inferred structure, describe business changes, review the exact backend patch, validate it, publish it and ask reproducible analytical questions. Selected semantic views influence both generated instructions and actual executable plans.

This establishes an implementation to evaluate. It does not establish general natural-language correctness, production scale or the complete original platform.

## Scope matrix

| Product requirement | V0.1 state | Expansion needed |
|---|---|---|
| Upload any data | CSV and one-sheet XLSX. | JSON/Parquet, document extraction/OCR, supported source/type contracts. |
| Automatic semantic creation | Deterministic profiling and clearly labelled candidate descriptions/metrics. | Business-context retrieval, richer model-assisted drafting and measured ambiguity resolution. |
| Conversational correction | Typed change proposals, review, checks and versions; Bedrock adapter. | Held-out language evaluation, multi-turn clarification state, better patch-preservation controls. |
| Select several views | Up to 12 selected views; compiled catalog/instructions. | Per-user permissions and reusable hosted compositions. |
| Compile answers across views | Two queried views, one shared key, aggregate-before-merge. | Composite/multi-hop/temporal relationships, source-native pushdown and governed federation. |
| Current data | Immutable uploaded snapshots with import timestamp. | Read-only database connectors, source refresh, schema drift and source watermarks. |
| Hosted collaborating agents | Not implemented. | Versioned agent packages, durable run dispatch, bounded delegation and scoped identity. |
| Plugin suggestions/execution | Not implemented. | Capability registry, OAuth, MCP/REST gateways, scopes and consent. |
| Internet enrichment | Not implemented. | Controlled search/fetch, provenance, outbound privacy rules and source-quality checks. |
| Production multi-tenancy | Single-owner local workspace. | OIDC, tenant boundaries/RLS, role policies, secret management and data-residency decisions. |
| Real-time UX | Request/response with working-state indicator. | Durable asynchronous jobs, SSE reconnect, cancellation and traceable run state. |
| Operational scale | Small, bounded SQLite workloads; one API worker. | PostgreSQL, source/query workers, quotas, tracing, backup drills and workload benchmarks. |

## Known limitations that affect answers

- Business correctness still needs domain input. Names, unique values and executable SQL do not prove the inferred meaning.
- The Bedrock adapter has mocked contract tests; its real model quality, region compatibility, latency and cost need your AWS account and representative questions.
- Generated prompts are suggestions, not verified questions. Registered reference tests must come from independent expected calculations.
- Draft grain is descriptive metadata. Arbitrary semantic grain assertions cannot be proved from uploaded values alone.
- No implicit currency conversion, fiscal-period calculation, ranking, time comparison, forecast, ratio or cross-view row filtering exists.
- Data is not continuously refreshed. Different uploaded sources can represent different cutoffs; no shared transaction timestamp is inferred.
- Sensitivity detection is a column-name heuristic. It is incomplete and not a compliance classifier or row-level security system.
- Floating-point calculations are unsuitable for exact-decimal ledger requirements without an additional numeric implementation.
- Reference cases can deliberately block view removal or a legitimate changed metric. The owner must intentionally revise those cases.
- The workspace is protected as one unit by an optional bearer token. There are no users, sharing rules or per-project access roles.
- Local audit events can be changed by someone with database-file access; they are not a tamper-proof external audit ledger.
- Import data and run histories remain until the workspace is removed. Lifecycle deletion, tenant quotas and retention services are not implemented.
- Query execution has a three-second SQLite budget, but this is not an overall model-call timeout or a distributed CPU/memory sandbox.
- The upload cap is enforced after multipart parsing; internet exposure requires upstream body-size limits, rate limits, scanning and worker isolation.
- Docker and CI files are provided as runnable configuration, but were not executed on Docker/GitHub in this environment.

## Suggested next milestones

### 1. Evaluate the semantic loop

Use a real but authorised Sales/Inventory or Finance dataset. Write 30–50 independently checked questions, including deliberately ambiguous ones. Measure correct metric selection, correct numerical results, appropriate clarification, patch preservation and regressions after edits. Keep unsupported questions in the evaluation and check that the app refuses them.

### 2. Improve semantic setup

Add richer business definitions, owner/source lineage, units and non-additive metric contracts. Introduce a targeted clarification workflow rather than asking an LLM to guess. Store multi-turn clarification as a proposal thread that references a base version. Require stale-state handling throughout.

### 3. Add one live source

Implement PostgreSQL **or** Snowflake first with a read-only role, table/column discovery, parameterized bounded queries and source-level freshness. Preserve the canonical registry; a Snowflake adapter should explicitly compile supported definitions into native objects. Do not promise identical capabilities across engines without conformance tests.

### 4. Add the shared deployment boundary

Move metadata/versioning to PostgreSQL with migrations, separate source/query access, add OIDC and real owner/editor/viewer policies, and enforce tenant isolation in persistence, retrieval, caches and job execution. Put credentials in a secrets service. Add TLS, proxy limits, structured redacted logs and restore tests before shared deployment.

### 5. Expand composition from measured needs

Start with independently aggregated facts, then add dimensions/composite keys and source-native execution. Each additional join class needs explicit grain and cardinality contracts, expected-row examples, unit/time compatibility and failure behavior. Do not add arbitrary raw joins as a shortcut.

### 6. Add durable operations and extensions

Only after the semantic/data boundary passes evaluation, add hosted agents, durable queues, streaming progress, plugin capability recommendations and controlled external enrichment. Agents must inherit the requesting identity and approved definitions; collaboration must not grant extra access.

## Documentation used for implementation boundaries

- FastAPI upload handling: https://fastapi.tiangolo.com/tutorial/request-files/
- Amazon Bedrock client-side tools and Converse: https://docs.aws.amazon.com/bedrock/latest/userguide/tool-use-client-side.html
- Bedrock Converse inference interface: https://docs.aws.amazon.com/bedrock/latest/userguide/conversation-inference.html

These are API references, not independent validation of this product's answer accuracy. Runtime package versions are captured in the dependency lockfiles.
