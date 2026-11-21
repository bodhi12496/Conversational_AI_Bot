# Verification record — v0.1.0

Verified on 12 November 2026 with Python 3.12.14 and Node.js 24.22.1 on Linux.

| Check | Observed result |
|---|---|
| Fresh dependency environment | Created a new virtual environment, installed hash-locked requirements and installed the project without resolving additional dependencies. |
| Backend suite | 37 tests passed in that environment. |
| Python lint/format | Ruff checks passed for `backend` and `scripts`; all 29 Python files formatted. |
| Frontend | TypeScript checking and Vite production build passed. |
| API integration | The executable demo created a project, imported both sources, edited definitions, added a manually checked reference case, published and returned the expected four combined rows. |
| Interface integration | One jsdom integration test passed against the real temporary backend: sample import, three chat corrections, review/apply, publishing, combined answer, semantic inspection, changed selection and restore-as-new-draft. |
| Live Bedrock | Not run: requires user credentials, model access and region selection. Tool response/validation behavior passed mocked tests. |
| Browser rendering/mobile layout | Browser smoke test is supplied. Execution was blocked by browser runtime restrictions in the build environment; visual layout and browser-level behavior remain unverified. jsdom does not replace rendering verification. |
| Docker deployment | Configuration supplied; image build and container startup not run here. |
| GitHub Actions | Workflow supplied; not executed on GitHub. |
| Production load/security assessment | Not performed; this is the documented local baseline. |

The backend checks cover numerical correction, no live change before publishing, stale/double/concurrent apply, immutable restore, reference regression failure, persistence after restart, pre-aggregation to prevent duplicated stock, missing/wrong relationships, selection enforcement, blocked syntax, bound filter values, unsupported questions, input constraints, identifier preservation, sensitivity blocks, invalid/oversized files, XLSX formula rejection, project scoping, workspace token/origin/host boundaries, null keys, excessive groups and model output validation.

There is one non-failing dependency deprecation warning: Starlette's test client currently advises moving from HTTPX to HTTPX2. It does not affect the passing application checks. The lockfile records the tested dependency versions.

Reproduce the checks with:

```bash
python -m pytest -q
python -m ruff check backend scripts
python -m ruff format --check backend scripts
cd frontend
npm ci
npm run build
cd ..
python scripts/verify_local.py --dom
```

For actual browser verification on your machine:

```bash
python -m pip install playwright
python -m playwright install chromium
python scripts/verify_local.py
```

If using an already installed Chromium binary, `COE_CHROMIUM_PATH` can point to it. The browser test uses only generated synthetic data.

## UI redesign verification — 21 November 2026

The redesigned six-page UI passed its updated real-backend jsdom walkthrough: project creation, sample import, unpublished-chat gating, three definition changes with preview/save, metric and relationship inspection, publication, combined answer, unsaved-selection publication guard, selection save, historical restore and source search. All 37 backend tests pass again. TypeScript/Vite build passes. The updated Playwright smoke test is included, but browser rendering remains unverified because Chromium cannot create the required sockets in this environment. See UI_REDESIGN.md for the updated navigation and references.
