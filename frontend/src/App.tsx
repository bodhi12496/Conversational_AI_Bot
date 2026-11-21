import { useEffect, useRef, useState, type FormEvent } from "react";
import { api, setToken } from "./api";
import { Empty, Icon, Modal, ResultPanel } from "./components";
import type { Project, Proposal, Result, State, Model } from "./types";

type Page = "overview" | "data" | "model" | "agent" | "chat" | "history";
const pages: { id: Page; label: string; icon: string; description: string }[] =
  [
    {
      id: "overview",
      label: "Overview",
      icon: "home",
      description: "A clear path from your data to a published assistant.",
    },
    {
      id: "data",
      label: "Data sources",
      icon: "data",
      description:
        "Upload tables and inspect the data available to your project.",
    },
    {
      id: "model",
      label: "Semantic model",
      icon: "model",
      description:
        "Define what your data means, one business concept at a time.",
    },
    {
      id: "agent",
      label: "Agent setup",
      icon: "agent",
      description:
        "Choose your semantic views, review the configuration, and publish.",
    },
    {
      id: "chat",
      label: "Chat",
      icon: "chat",
      description: "Ask questions using your published business definitions.",
    },
    {
      id: "history",
      label: "Activity & versions",
      icon: "history",
      description:
        "Review releases, restore a version, and maintain reference tests.",
    },
  ];
const edits = [
  "Define revenue as amount minus refund in sales.",
  "Exclude cancelled orders from sales.",
  "Set grain of sales to one row per order.",
  "Link sales.product_id to inventory.product_id as many_to_one.",
];
export default function App() {
  const [publishedModel, setPublishedModel] = useState<Model | null>(null);
  const [projects, setProjects] = useState<Project[]>([]),
    [id, setId] = useState(""),
    [state, setState] = useState<State | null>(null);
  const [page, setPage] = useState<Page>("overview"),
    [provider, setProvider] = useState("demo"),
    [busy, setBusy] = useState(false),
    [loading, setLoading] = useState(true);
  const [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [dialog, setDialog] = useState<
      "project" | "upload" | "edit" | "settings" | null
    >(null);
  const [projectName, setProjectName] = useState(""),
    [message, setMessage] = useState(""),
    [question, setQuestion] = useState(""),
    [proposal, setProposal] = useState<Proposal | null>(null);
  const [selection, setSelection] = useState<string[]>([]),
    [ack, setAck] = useState(false),
    [viewId, setViewId] = useState(""),
    [modelTab, setModelTab] = useState("columns"),
    [search, setSearch] = useState("");
  const [restore, setRestore] = useState(""),
    [reference, setReference] = useState(""),
    [testName, setTestName] = useState(""),
    [testMetric, setTestMetric] = useState(""),
    [testValue, setTestValue] = useState("");
  const [turns, setTurns] = useState<{ question: string; result: Result }[]>(
      [],
    ),
    [historyTab, setHistoryTab] = useState("versions");
  const fileRef = useRef<HTMLInputElement>(null),
    seq = useRef(0),
    dialogRef = useRef<HTMLDivElement>(null),
    returnFocus = useRef<HTMLElement | null>(null);
  const current = pages.find((p) => p.id === page)!;
  async function list() {
    const p = await api<Project[]>("/projects");
    setProjects(p);
    return p;
  }
  async function refresh() {
    const s = await api<State>(`/projects/${id}`);
    setState(s);
    setSelection(s.model.selected_views);
    setAck(false);
    return s;
  }
  async function task(fn: () => Promise<void>) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await fn();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }
  useEffect(() => {
    void task(async () => {
      const c = await api<{ provider: string }>("/config");
      setProvider(c.provider);
      const p = await list();
      if (p.length) setId(p[0].id);
    }).finally(() => setLoading(false));
  }, []);
  useEffect(() => {
    const n = ++seq.current;
    setState(null);
    setTurns([]);
    setProposal(null);
    setViewId("");
    setSearch("");
    setMessage("");
    setReference("");
    setAck(false);
    if (id)
      void task(async () => {
        const s = await api<State>(`/projects/${id}`);
        if (n === seq.current) {
          setState(s);
          setSelection(s.model.selected_views);
        }
      });
  }, [id]);
  useEffect(() => {
    if (!dialog) return;
    returnFocus.current = document.activeElement as HTMLElement;
    const timer = setTimeout(
      () =>
        dialogRef.current
          ?.querySelector<HTMLElement>("input,textarea,button")
          ?.focus(),
      0,
    );
    return () => {
      clearTimeout(timer);
      returnFocus.current?.focus();
    };
  }, [dialog]);
  useEffect(() => {
    let cancelled = false;
    setPublishedModel(null);
    if (state?.project.active)
      void api<Model>(`/projects/${id}/versions/${state.project.active}`)
        .then((m) => {
          if (!cancelled) setPublishedModel(m);
        })
        .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [id, state?.project.active]);
  function go(next: Page) {
    setPage(next);
    setError("");
    setNotice("");
  }
  function edit(example = "") {
    setMessage(example);
    setProposal(null);
    setDialog("edit");
  }
  async function upload(file: File) {
    await task(async () => {
      const data = new FormData();
      data.append("file", file);
      await api(`/projects/${id}/datasets`, "POST", data);
      await refresh();
      setDialog(null);
      setNotice(
        `${file.name} imported. Review its definitions in Semantic model.`,
      );
    });
  }
  async function sample() {
    await task(async () => {
      await api(`/projects/${id}/demo`, "POST");
      await refresh();
      setDialog(null);
      setNotice("Sample data loaded. Next, review the semantic model.");
    });
  }
  async function apply() {
    await task(async () => {
      await api(`/projects/${id}/proposals/${proposal!.id}/apply`, "POST");
      await refresh();
      setProposal(null);
      setDialog(null);
      setNotice(
        "Change saved to a new draft. Publish from Agent setup when ready.",
      );
    });
  }
  const view =
    state?.model.views.find((v) => v.id === viewId) || state?.model.views[0];
  const ready = !!state?.project.active,
    hasData = !!state?.model.views.length,
    changed = state?.project.head !== state?.project.active;
  const steps = [
    {
      title: "Connect data",
      detail: "Upload CSV or Excel tables",
      done: hasData,
      page: "data" as Page,
    },
    {
      title: "Review definitions",
      detail: "Confirm metrics and relationships",
      done:
        hasData &&
        state!.model.views.every(
          (v) =>
            !v.grain.startsWith("Unconfirmed") &&
            v.metrics.every((m) => m.confirmed),
        ),
      page: "model" as Page,
    },
    {
      title: "Configure & publish",
      detail: "Select views and review assumptions",
      done: ready,
      page: "agent" as Page,
    },
    {
      title: "Ask your data",
      detail: "Get answers with source evidence",
      done: !!state?.recent_runs.length,
      page: "chat" as Page,
    },
  ];
  const selectedChanged =
    JSON.stringify([...selection].sort()) !==
    JSON.stringify([...(state?.model.selected_views || [])].sort());
  const canClose = !busy;
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a
          className="brand"
          href="#"
          onClick={(e) => {
            e.preventDefault();
            go("overview");
          }}
        >
          <span className="brand-logo">
            <Icon name="model" size={22} />
          </span>
          <span>
            COE<span className="brand-caption">Data Platform</span>
          </span>
        </a>
        <div className="workspace-switch">
          <span className="workspace-avatar">W</span>
          <div>
            My workspace<small>Local environment</small>
          </div>
          <span className="online-dot" />
        </div>
        <div className="nav-caption">WORKSPACE</div>
        <nav aria-label="Main navigation">
          {pages.map((p) => (
            <button
              key={p.id}
              className={`nav-item ${page === p.id ? "active" : ""}`}
              aria-current={page === p.id ? "page" : undefined}
              onClick={() => go(p.id)}
            >
              <Icon name={p.icon} />
              {p.label}
              {p.id === "chat" && ready && <span className="nav-dot" />}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <button className="nav-item" onClick={() => setDialog("settings")}>
            <Icon name="settings" />
            Connection settings
          </button>
          <div className="user-profile">
            <span className="user-avatar">
              <Icon name="agent" />
            </span>
            <div>
              Local workspace<small>Single owner · v0.1</small>
            </div>
          </div>
        </div>
      </aside>
      <main>
        <header className="topbar">
          <div className="breadcrumbs">
            Workspace <Icon name="chevron" size={12} />
            <span>{current.label}</span>
          </div>
          <div className="top-actions">
            <span className="env-label">
              <span className="online-dot" />
              {provider === "demo" ? "Demo mode" : "Amazon Bedrock"}
            </span>
            <span className="top-divider" />
            <label className="sr-only" htmlFor="project-switch">
              Current project
            </label>
            <select
              id="project-switch"
              value={id}
              disabled={busy}
              onChange={(e) => setId(e.target.value)}
            >
              <option value="" disabled>
                Select project
              </option>
              {projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
            <button
              className="icon-button"
              aria-label="New project"
              onClick={() => setDialog("project")}
            >
              <Icon name="plus" />
            </button>
            <button
              className="icon-button"
              aria-label="API connection settings"
              onClick={() => setDialog("settings")}
            >
              <Icon name="settings" />
            </button>
          </div>
        </header>
        <div className={`page-content ${page === "chat" ? "chat-page" : ""}`}>
          <div className="page-header">
            <div>
              <div className="eyebrow">
                {state?.project.name || "GET STARTED"}
              </div>
              <h1>{current.label}</h1>
              <p>{current.description}</p>
            </div>
            <div className="header-actions">
              {state && (
                <span className={`tag ${ready ? "green" : "neutral"}`}>
                  {ready
                    ? `Published v${state.project.active}`
                    : "Not published"}
                </span>
              )}
              {state && changed && (
                <span className="tag amber">Draft v{state.project.head}</span>
              )}
              {page === "data" && state && (
                <button
                  className="primary"
                  disabled={busy}
                  onClick={() => setDialog("upload")}
                >
                  <Icon name="plus" size={16} />
                  Add data
                </button>
              )}
              {page === "model" && hasData && (
                <button
                  className="primary"
                  disabled={busy}
                  onClick={() => edit()}
                >
                  <Icon name="spark" size={16} />
                  Edit with AI
                </button>
              )}
            </div>
          </div>
          {busy && (
            <div className="loading-bar" role="status">
              Working on your request…
            </div>
          )}
          {error && (
            <div className="toast error" role="alert">
              <Icon name="info" />
              {error}
              <button
                className="icon-button"
                aria-label="Dismiss error"
                onClick={() => setError("")}
              >
                <Icon name="close" size={15} />
              </button>
            </div>
          )}
          {notice && (
            <div className="toast success" role="status">
              <Icon name="check" />
              {notice}
              <button
                className="icon-button"
                aria-label="Dismiss notification"
                onClick={() => setNotice("")}
              >
                <Icon name="close" size={15} />
              </button>
            </div>
          )}
          {!state && !busy && !loading && (
            <section className="panel">
              <Empty
                title="Your first data assistant starts here"
                icon="spark"
                action={
                  <button
                    className="primary"
                    onClick={() => setDialog("project")}
                  >
                    <Icon name="plus" size={16} />
                    Create project
                  </button>
                }
              >
                Create a project, connect your tables, and define what they
                mean. We’ll guide you through each step.
              </Empty>
              <div className="intro-steps">
                {steps.map((s, i) => (
                  <div key={s.title}>
                    <span>{i + 1}</span>
                    <strong>{s.title}</strong>
                    <p>{s.detail}</p>
                  </div>
                ))}
              </div>
            </section>
          )}
          {state && (
            <>
              {page === "overview" && (
                <>
                  <section className="welcome-card">
                    <div>
                      <span className="tag blue">YOUR SETUP GUIDE</span>
                      <h2>
                        {ready
                          ? "Your assistant is ready."
                          : "Let’s turn your tables into answers."}
                      </h2>
                      <p>
                        {ready
                          ? "Continue asking questions, or refine the definitions behind your assistant."
                          : "Follow these four steps. You can review every change before it goes live."}
                      </p>
                      <button
                        className="primary"
                        onClick={() =>
                          go(ready ? "chat" : hasData ? "model" : "data")
                        }
                      >
                        {ready
                          ? "Open chat"
                          : hasData
                            ? "Review semantic model"
                            : "Connect your data"}
                        <Icon name="arrow" size={16} />
                      </button>
                    </div>
                    <div className="welcome-visual" aria-hidden="true">
                      <span>
                        <Icon name="data" size={27} />
                      </span>
                      <i />
                      <span>
                        <Icon name="model" size={27} />
                      </span>
                      <i />
                      <span>
                        <Icon name="chat" size={27} />
                      </span>
                    </div>
                  </section>
                  <div className="setup-grid">
                    {steps.map((s, i) => (
                      <button
                        key={s.title}
                        className="setup-card"
                        onClick={() => go(s.page)}
                      >
                        <span className={`step-number ${s.done ? "done" : ""}`}>
                          {s.done ? (
                            <Icon name="check" size={16} />
                          ) : (
                            String(i + 1).padStart(2, "0")
                          )}
                        </span>
                        <h3>{s.title}</h3>
                        <p>{s.detail}</p>
                        <span className="setup-link">
                          {s.done ? "Open" : "Get started"}
                          <Icon name="arrow" size={14} />
                        </span>
                      </button>
                    ))}
                  </div>
                  <div className="overview-grid">
                    <section className="panel">
                      <div className="panel-title">
                        <h2>Project at a glance</h2>
                        <span className="tag neutral">Current draft</span>
                      </div>
                      <div className="metric-grid">
                        <div>
                          <strong>{state.model.views.length}</strong>
                          <span>Semantic views</span>
                        </div>
                        <div>
                          <strong>
                            {state.model.views.reduce(
                              (n, v) => n + v.metrics.length,
                              0,
                            )}
                          </strong>
                          <span>Defined metrics</span>
                        </div>
                        <div>
                          <strong>{state.model.relationships.length}</strong>
                          <span>Relationships</span>
                        </div>
                      </div>
                      <div className="panel-foot">
                        <Icon name="info" size={16} />
                        Uploaded files are snapshots, not live database
                        connections.
                      </div>
                    </section>
                    <section className="panel">
                      <div className="panel-title">
                        <h2>Recent questions</h2>
                        <button
                          className="text-button"
                          onClick={() => go("chat")}
                        >
                          Open chat
                          <Icon name="arrow" size={14} />
                        </button>
                      </div>
                      {state.recent_runs.length ? (
                        state.recent_runs.slice(0, 3).map((r) => (
                          <button
                            className="recent-item"
                            key={r.id}
                            disabled={busy}
                            onClick={() =>
                              void task(async () => {
                                const result = await api<Result>(
                                  `/projects/${id}/runs/${r.id}`,
                                );
                                setTurns([{ question: r.question, result }]);
                                setPage("chat");
                              })
                            }
                          >
                            <Icon name="chat" size={16} />
                            <span>{r.question}</span>
                            <small>v{r.version}</small>
                          </button>
                        ))
                      ) : (
                        <div className="quiet-empty">
                          <Icon name="chat" size={22} />
                          <p>
                            Your questions will appear here after you publish
                            and chat.
                          </p>
                        </div>
                      )}
                    </section>
                  </div>
                </>
              )}
              {page === "data" && (
                <>
                  <section className="panel">
                    {!hasData ? (
                      <Empty
                        title="Connect your first data source"
                        action={
                          <div className="button-row">
                            <button
                              className="primary"
                              onClick={() => setDialog("upload")}
                            >
                              <Icon name="upload" size={16} />
                              Upload a file
                            </button>
                            <button
                              className="secondary"
                              disabled={busy}
                              onClick={() => void sample()}
                            >
                              Try sample data
                            </button>
                          </div>
                        }
                      >
                        Upload a CSV or Excel table. The platform will profile
                        its columns and create a draft semantic view.
                      </Empty>
                    ) : (
                      <>
                        <div className="table-toolbar">
                          <h2>
                            Connected tables{" "}
                            <span className="count">
                              {state.datasets.length}
                            </span>
                          </h2>
                          <label className="search-box">
                            <Icon name="search" size={16} />
                            <input
                              aria-label="Search data sources"
                              placeholder="Search tables…"
                              value={search}
                              onChange={(e) => setSearch(e.target.value)}
                            />
                          </label>
                        </div>
                        <div className="table-scroll">
                          <table>
                            <thead>
                              <tr>
                                <th>Source</th>
                                <th>Rows</th>
                                <th>Imported</th>
                                <th>Type</th>
                                <th />
                              </tr>
                            </thead>
                            <tbody>
                              {state.datasets
                                .filter((d) =>
                                  d.view_id
                                    .toLowerCase()
                                    .includes(search.toLowerCase()),
                                )
                                .map((d, i) => (
                                  <tr key={i}>
                                    <td>
                                      <div className="table-name">
                                        <span className="table-icon">
                                          <Icon name="data" size={17} />
                                        </span>
                                        <strong>{d.view_id}</strong>
                                      </div>
                                    </td>
                                    <td>{d.row_count.toLocaleString()}</td>
                                    <td>
                                      {new Date(
                                        d.loaded_at,
                                      ).toLocaleDateString()}
                                    </td>
                                    <td>
                                      <span className="tag neutral">
                                        File snapshot
                                      </span>
                                    </td>
                                    <td>
                                      <button
                                        className="text-button"
                                        onClick={() => {
                                          setViewId(d.view_id);
                                          go("model");
                                        }}
                                      >
                                        Review model
                                        <Icon name="arrow" size={14} />
                                      </button>
                                    </td>
                                  </tr>
                                ))}
                            </tbody>
                          </table>
                          {!state.datasets.some((d) =>
                            d.view_id
                              .toLowerCase()
                              .includes(search.toLowerCase()),
                          ) && (
                            <p className="table-empty">
                              No sources match your search.
                            </p>
                          )}
                        </div>
                      </>
                    )}
                  </section>
                  <div className="callout">
                    <Icon name="info" />
                    <div>
                      <strong>What happens after upload?</strong>
                      <p>
                        We detect column types, missing values, potential keys,
                        and candidate metrics. Business definitions are drafts
                        for you to review.
                      </p>
                    </div>
                  </div>
                  {hasData && (
                    <div className="next-step">
                      <div>
                        <strong>
                          Data connected. Next: review its meaning.
                        </strong>
                        <p>
                          Confirm metrics and relationships before using them in
                          answers.
                        </p>
                      </div>
                      <button className="primary" onClick={() => go("model")}>
                        Review semantic model
                        <Icon name="arrow" size={16} />
                      </button>
                    </div>
                  )}
                </>
              )}
              {page === "model" &&
                (!view ? (
                  <section className="panel">
                    <Empty
                      title="No semantic views yet"
                      icon="model"
                      action={
                        <button className="primary" onClick={() => go("data")}>
                          Connect data
                          <Icon name="arrow" size={16} />
                        </button>
                      }
                    >
                      A semantic view is created when you upload a table.
                    </Empty>
                  </section>
                ) : (
                  <div className="model-layout">
                    <aside className="model-explorer">
                      <div className="explorer-heading">
                        SEMANTIC VIEWS <span>{state.model.views.length}</span>
                      </div>
                      {state.model.views.map((v) => (
                        <button
                          key={v.id}
                          className={`explorer-item ${v.id === view.id ? "active" : ""}`}
                          onClick={() => setViewId(v.id)}
                        >
                          <Icon name="data" size={16} />
                          <span>
                            {v.name}
                            <small>
                              {v.columns.length} columns · {v.metrics.length}{" "}
                              metrics
                            </small>
                          </span>
                          <Icon name="chevron" size={13} />
                        </button>
                      ))}
                    </aside>
                    <section className="panel model-detail">
                      <div className="model-heading">
                        <span className="table-icon">
                          <Icon name="data" size={23} />
                        </span>
                        <div>
                          <h2>{view.name}</h2>
                          <p>{view.grain}</p>
                        </div>
                        <span className="tag neutral">
                          Draft v{state.project.head}
                        </span>
                      </div>
                      <div
                        className="tabs"
                        role="tablist"
                        aria-label="Semantic model sections"
                      >
                        {[
                          "columns",
                          "metrics",
                          "relationships",
                          "instructions",
                        ].map((t) => (
                          <button
                            role="tab"
                            aria-selected={modelTab === t}
                            key={t}
                            className={modelTab === t ? "active" : ""}
                            onClick={() => setModelTab(t)}
                          >
                            {t[0].toUpperCase() + t.slice(1)}
                            {t === "columns" && (
                              <span>{view.columns.length}</span>
                            )}
                            {t === "metrics" && (
                              <span>{view.metrics.length}</span>
                            )}
                          </button>
                        ))}
                      </div>
                      {modelTab === "columns" && (
                        <>
                          <div className="section-help">
                            Column names, types, and business descriptions. Use{" "}
                            <strong>Edit with AI</strong> to clarify a
                            definition.
                          </div>
                          <div className="table-scroll">
                            <table>
                              <thead>
                                <tr>
                                  <th>Column</th>
                                  <th>Type</th>
                                  <th>Business description</th>
                                  <th>Quality</th>
                                </tr>
                              </thead>
                              <tbody>
                                {view.columns.map((c) => (
                                  <tr key={c.name}>
                                    <td>
                                      <code>{c.name}</code>
                                      {c.sensitive && (
                                        <span className="tag amber">
                                          Blocked
                                        </span>
                                      )}
                                    </td>
                                    <td>
                                      <span className="type-pill">
                                        {c.dtype}
                                      </span>
                                    </td>
                                    <td className="description-cell">
                                      {c.description}
                                    </td>
                                    <td>
                                      <span
                                        className={
                                          c.null_count ? "text-amber" : "muted"
                                        }
                                      >
                                        {c.null_count} missing
                                      </span>
                                      <small>{c.distinct_count} distinct</small>
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        </>
                      )}
                      {modelTab === "metrics" && (
                        <>
                          <div className="section-help">
                            Metrics tell the assistant exactly how to calculate
                            an answer.
                          </div>
                          <div className="table-scroll">
                            <table>
                              <thead>
                                <tr>
                                  <th>Metric</th>
                                  <th>Calculation</th>
                                  <th>Unit</th>
                                  <th>Status</th>
                                </tr>
                              </thead>
                              <tbody>
                                {view.metrics.map((m) => (
                                  <tr key={m.name}>
                                    <td>
                                      <strong>{m.name}</strong>
                                      <small>{m.description}</small>
                                    </td>
                                    <td>
                                      <code>
                                        {m.aggregation}({m.expression})
                                      </code>
                                    </td>
                                    <td>{m.unit}</td>
                                    <td>
                                      <span
                                        className={`tag ${m.confirmed ? "green" : "amber"}`}
                                      >
                                        {m.confirmed
                                          ? "Defined"
                                          : "Review needed"}
                                      </span>
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                          <details className="inset">
                            <summary>Default filters for this view</summary>
                            <pre>{JSON.stringify(view.filters, null, 2)}</pre>
                          </details>
                        </>
                      )}
                      {modelTab === "relationships" && (
                        <div className="inset">
                          {state.model.relationships.length ? (
                            state.model.relationships.map((r, i) => {
                              const x = r as {
                                left_view: string;
                                left_key: string;
                                right_view: string;
                                right_key: string;
                                cardinality: string;
                                confirmed: boolean;
                              };
                              return (
                                <div className="relationship" key={i}>
                                  <div>
                                    <Icon name="data" />
                                    <strong>{x.left_view}</strong>
                                    <code>{x.left_key}</code>
                                  </div>
                                  <span className="relationship-line">
                                    {x.cardinality.replaceAll("_", " ")}
                                  </span>
                                  <div>
                                    <Icon name="data" />
                                    <strong>{x.right_view}</strong>
                                    <code>{x.right_key}</code>
                                  </div>
                                </div>
                              );
                            })
                          ) : (
                            <Empty title="Connect related views" icon="model">
                              Explain which keys refer to the same entity. We’ll
                              check the key types and declared cardinality
                              before combining answers.
                            </Empty>
                          )}
                          <button
                            className="secondary"
                            onClick={() => edit(edits[3])}
                          >
                            <Icon name="plus" size={16} />
                            Define a relationship
                          </button>
                        </div>
                      )}
                      {modelTab === "instructions" && (
                        <div className="inset">
                          <h3>How the assistant uses selected views</h3>
                          <ul className="readable-list">
                            {state.instructions.orchestration.map((s) => (
                              <li key={s}>{s}</li>
                            ))}
                          </ul>
                          <h3>How answers are presented</h3>
                          <ul className="readable-list">
                            {state.instructions.response.map((s) => (
                              <li key={s}>{s}</li>
                            ))}
                          </ul>
                          <details>
                            <summary>View complete configuration</summary>
                            <pre>
                              {JSON.stringify(state.instructions, null, 2)}
                            </pre>
                          </details>
                        </div>
                      )}
                    </section>
                  </div>
                ))}
              {page === "agent" && (
                <div className="agent-layout">
                  <div>
                    <section className="panel">
                      <div className="panel-title">
                        <h2>
                          <span className="number-label">1</span>Choose semantic
                          views
                        </h2>
                        <span className="muted">
                          {selection.length} selected
                        </span>
                      </div>
                      <p className="section-description">
                        Select the views your assistant can use. Adding a view
                        also updates its routing and response instructions.
                      </p>
                      {!hasData ? (
                        <button
                          className="secondary"
                          onClick={() => go("data")}
                        >
                          Connect data first
                        </button>
                      ) : (
                        <div className="selection-grid">
                          {state.model.views.map((v) => (
                            <label
                              className={`selection-card ${selection.includes(v.id) ? "selected" : ""}`}
                              key={v.id}
                            >
                              <input
                                type="checkbox"
                                disabled={busy}
                                checked={selection.includes(v.id)}
                                onChange={(e) => {
                                  setSelection(
                                    e.target.checked
                                      ? [...selection, v.id]
                                      : selection.filter((x) => x !== v.id),
                                  );
                                  setAck(false);
                                }}
                              />
                              <span className="table-icon">
                                <Icon name="data" />
                              </span>
                              <span>
                                <strong>{v.name}</strong>
                                <small>
                                  {v.metrics.length} metrics ·{" "}
                                  {v.columns.length} columns
                                </small>
                              </span>
                            </label>
                          ))}
                        </div>
                      )}
                      <div className="panel-actions">
                        <span className="muted">
                          {selectedChanged
                            ? "You have unsaved view selections."
                            : "Selection matches the current draft."}
                        </span>
                        <button
                          className="secondary"
                          disabled={
                            busy || !selectedChanged || !selection.length
                          }
                          onClick={() =>
                            void task(async () => {
                              setProposal(
                                await api<Proposal>(
                                  `/projects/${id}/changes/structured`,
                                  "POST",
                                  {
                                    base_version: state.project.head,
                                    changes: {
                                      summary:
                                        "Update selected views and rebuild instructions.",
                                      operations: [
                                        {
                                          op: "select_views",
                                          view_ids: selection,
                                        },
                                      ],
                                    },
                                  },
                                ),
                              );
                              setDialog("edit");
                            })
                          }
                        >
                          Review selection change
                          <Icon name="arrow" size={16} />
                        </button>
                      </div>
                    </section>
                    <section className="panel">
                      <div className="panel-title">
                        <h2>
                          <span className="number-label">2</span>Review
                          configuration
                        </h2>
                        <span
                          className={`tag ${state.validation.valid ? "green" : "amber"}`}
                        >
                          {state.validation.valid
                            ? "Checks passed"
                            : "Needs attention"}
                        </span>
                      </div>
                      <p className="section-description">
                        Structural checks confirm executable definitions. Review
                        the business meaning and assumptions before publishing.
                      </p>
                      {state.validation.errors.map((e) => (
                        <div className="callout danger" key={e}>
                          {e}
                        </div>
                      ))}
                      <details
                        className="review-notes"
                        open={!state.validation.valid}
                      >
                        <summary>
                          {state.validation.warnings.length} assumptions to
                          review
                        </summary>
                        <ul className="readable-list">
                          {state.validation.warnings.map((w) => (
                            <li key={w}>{w}</li>
                          ))}
                        </ul>
                      </details>
                      <details className="review-notes">
                        <summary>
                          {state.validation.checks.length} validation checks
                        </summary>
                        <ul>
                          {state.validation.checks.map((c) => (
                            <li key={c}>{c}</li>
                          ))}
                        </ul>
                      </details>
                      <details className="review-notes">
                        <summary>Generated agent instructions</summary>
                        <ul>
                          {state.instructions.orchestration.map((c) => (
                            <li key={c}>{c}</li>
                          ))}
                        </ul>
                      </details>
                    </section>
                  </div>
                  <aside>
                    <section className="panel publish-card">
                      <div className="publish-icon">
                        <Icon name="agent" size={30} />
                      </div>
                      <h2>Publish your assistant</h2>
                      <p>
                        Publishing activates the reviewed draft for new
                        questions. Your existing published version stays active
                        until then.
                      </p>
                      <div className="release-summary">
                        <span>
                          Current draft<strong>v{state.project.head}</strong>
                        </span>
                        <span>
                          Published version
                          <strong>
                            {ready ? `v${state.project.active}` : "None yet"}
                          </strong>
                        </span>
                        <span>
                          Selected views
                          <strong>{state.model.selected_views.length}</strong>
                        </span>
                      </div>
                      {selectedChanged && (
                        <div className="callout compact">
                          Review and apply your selection change before
                          publishing.
                        </div>
                      )}
                      <label className="ack">
                        <input
                          type="checkbox"
                          checked={ack}
                          onChange={(e) => setAck(e.target.checked)}
                        />
                        <span>
                          I reviewed the definitions and accept the listed
                          assumptions.
                        </span>
                      </label>
                      <button
                        className="primary full"
                        disabled={
                          busy ||
                          !ack ||
                          !state.validation.valid ||
                          !state.model.selected_views.length ||
                          selectedChanged ||
                          !changed
                        }
                        onClick={() =>
                          void task(async () => {
                            await api(`/projects/${id}/publish`, "POST", {
                              version: state.project.head,
                              acknowledge_inferred_definitions: ack,
                            });
                            await refresh();
                            setNotice(
                              "Assistant published. Open Chat to ask your data.",
                            );
                          })
                        }
                      >
                        <Icon name="check" size={16} />
                        {!changed
                          ? "Up to date"
                          : `Publish v${state.project.head}`}
                      </button>
                      {ready && (
                        <button
                          className="text-button full"
                          onClick={() => go("chat")}
                        >
                          Open chat
                          <Icon name="arrow" size={15} />
                        </button>
                      )}
                    </section>
                    <div className="side-note">
                      <Icon name="info" size={17} />
                      <p>
                        Combining two views requires a confirmed relationship.
                        Define it in Semantic model before asking a combined
                        question.
                      </p>
                    </div>
                  </aside>
                </div>
              )}
              {page === "chat" &&
                (!ready ? (
                  <section className="panel">
                    <Empty
                      title="Publish your assistant to start chatting"
                      icon="chat"
                      action={
                        <button className="primary" onClick={() => go("agent")}>
                          Go to Agent setup
                          <Icon name="arrow" size={16} />
                        </button>
                      }
                    >
                      Choose the views it can use and review the definitions.
                      New questions will use that published version.
                    </Empty>
                  </section>
                ) : (
                  <div className="chat-layout">
                    <section className="chat-main">
                      <div className="chat-context">
                        <Icon name="agent" />
                        <div>
                          <strong>{state.project.name}</strong>
                          <small>
                            Using published v{state.project.active} · answers
                            include source evidence
                          </small>
                        </div>
                        <button
                          className="text-button"
                          disabled={busy || !turns.length}
                          onClick={() => setTurns([])}
                        >
                          New conversation
                        </button>
                      </div>
                      <div className="chat-thread" aria-live="polite">
                        {!turns.length ? (
                          <div className="chat-welcome">
                            <span className="chat-spark">
                              <Icon name="spark" size={30} />
                            </span>
                            <h2>What would you like to know?</h2>
                            <p>
                              Explore your published metrics. Start with a
                              suggested question below.
                            </p>
                            <div className="question-suggestions">
                              {(
                                publishedModel?.views
                                  .filter((v) =>
                                    publishedModel.selected_views.includes(
                                      v.id,
                                    ),
                                  )
                                  .flatMap((v) =>
                                    v.metrics
                                      .slice(0, 2)
                                      .map((m) => `Show ${v.id}.${m.name}.`),
                                  ) || []
                              ).map((p) => (
                                <button key={p} onClick={() => setQuestion(p)}>
                                  <Icon name="chat" size={16} />
                                  <span>{p}</span>
                                  <Icon name="arrow" size={14} />
                                </button>
                              ))}
                            </div>
                          </div>
                        ) : (
                          turns.map((t, i) => (
                            <div className="chat-turn" key={i}>
                              <div className="user-message">{t.question}</div>
                              <div className="assistant-message">
                                <span className="assistant-mark">
                                  <Icon name="spark" size={17} />
                                </span>
                                <ResultPanel result={t.result} />
                              </div>
                            </div>
                          ))
                        )}
                      </div>
                      {changed && (
                        <div className="chat-draft-note">
                          Draft v{state.project.head} is not published. Answers
                          still use v{state.project.active}.
                          <button
                            className="text-button"
                            onClick={() => go("agent")}
                          >
                            Review draft
                          </button>
                        </div>
                      )}
                      <form
                        className="chat-composer"
                        onSubmit={(e) => {
                          e.preventDefault();
                          if (!question.trim()) return;
                          const q = question;
                          void task(async () => {
                            const r = await api<Result>(
                              `/projects/${id}/ask`,
                              "POST",
                              { message: q },
                            );
                            setTurns((t) => [...t, { question: q, result: r }]);
                            setQuestion("");
                            await refresh();
                          });
                        }}
                      >
                        <label className="sr-only" htmlFor="question">
                          Ask your data
                        </label>
                        <textarea
                          id="question"
                          rows={2}
                          value={question}
                          disabled={busy}
                          onChange={(e) => setQuestion(e.target.value)}
                          placeholder="Ask a question about your data…"
                          maxLength={4000}
                        />
                        <div>
                          <span>
                            {provider === "demo"
                              ? "Demo mode · use the suggested question patterns"
                              : "Powered by Amazon Bedrock"}{" "}
                            · Each question is independent
                          </span>
                          <button
                            className="primary"
                            disabled={busy || !question.trim()}
                            type="submit"
                          >
                            Send
                            <Icon name="arrow" size={16} />
                          </button>
                        </div>
                      </form>
                    </section>
                    <aside className="chat-help">
                      <h3>YOUR ASSISTANT</h3>
                      <p>
                        Published version{" "}
                        <strong>v{state.project.active}</strong>
                      </p>
                      <p>
                        Answers are calculated from the published model. Draft
                        changes appear only after publishing.
                      </p>
                      <hr />
                      <h3>NEED TO CHANGE A DEFINITION?</h3>
                      <p>
                        Keep business definitions in the semantic model so every
                        future answer uses the same logic.
                      </p>
                      <button
                        className="secondary full"
                        onClick={() => {
                          go("model");
                          edit();
                        }}
                      >
                        Edit definitions
                      </button>
                    </aside>
                  </div>
                ))}
              {page === "history" && (
                <>
                  <div
                    className="tabs"
                    role="tablist"
                    aria-label="Activity sections"
                  >
                    {[
                      ["versions", "Versions"],
                      ["questions", "Questions"],
                      ["tests", "Reference tests"],
                    ].map(([key, label]) => (
                      <button
                        key={key}
                        role="tab"
                        aria-selected={historyTab === key}
                        className={historyTab === key ? "active" : ""}
                        onClick={() => setHistoryTab(key)}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                  <section className="panel">
                    {historyTab === "versions" && (
                      <>
                        <div className="panel-title">
                          <h2>Model version history</h2>
                          <span className="muted">
                            {state.versions.length} versions
                          </span>
                        </div>
                        <div className="table-scroll">
                          <table>
                            <thead>
                              <tr>
                                <th>Version</th>
                                <th>Change</th>
                                <th>Created</th>
                                <th>Status</th>
                              </tr>
                            </thead>
                            <tbody>
                              {state.versions.map((v) => (
                                <tr key={v.number}>
                                  <td>
                                    <strong>v{v.number}</strong>
                                  </td>
                                  <td>{v.reason}</td>
                                  <td>
                                    {new Date(v.created_at).toLocaleString()}
                                  </td>
                                  <td>
                                    {v.number === state.project.active ? (
                                      <span className="tag green">
                                        Published
                                      </span>
                                    ) : v.number === state.project.head ? (
                                      <span className="tag amber">Draft</span>
                                    ) : (
                                      <span className="muted">Historical</span>
                                    )}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                        <div className="restore-bar">
                          <div>
                            <h3>Restore an earlier version</h3>
                            <p>
                              Creates a new draft. Review and publish it to make
                              it active.
                            </p>
                          </div>
                          <label className="sr-only" htmlFor="restore">
                            Version to restore
                          </label>
                          <select
                            id="restore"
                            value={restore}
                            onChange={(e) => setRestore(e.target.value)}
                          >
                            <option value="">Choose version</option>
                            {state.versions
                              .filter((v) => v.number !== state.project.head)
                              .map((v) => (
                                <option value={v.number} key={v.number}>
                                  v{v.number} · {v.reason}
                                </option>
                              ))}
                          </select>
                          <button
                            className="secondary"
                            disabled={busy || !restore}
                            onClick={() =>
                              void task(async () => {
                                await api(`/projects/${id}/rollback`, "POST", {
                                  base_version: state.project.head,
                                  target_version: Number(restore),
                                });
                                await refresh();
                                setRestore("");
                                setNotice(
                                  "Version restored as a new draft. Review it in Agent setup.",
                                );
                              })
                            }
                          >
                            Restore draft
                          </button>
                        </div>
                      </>
                    )}
                    {historyTab === "questions" &&
                      (state.recent_runs.length ? (
                        state.recent_runs.map((r) => (
                          <button
                            className="recent-item"
                            key={r.id}
                            disabled={busy}
                            onClick={() =>
                              void task(async () => {
                                const result = await api<Result>(
                                  `/projects/${id}/runs/${r.id}`,
                                );
                                setTurns([{ question: r.question, result }]);
                                go("chat");
                              })
                            }
                          >
                            <Icon name="chat" />
                            <span>{r.question}</span>
                            <small>Published v{r.version}</small>
                            <Icon name="chevron" size={16} />
                          </button>
                        ))
                      ) : (
                        <Empty title="No questions yet" icon="chat">
                          Executed questions and their evidence will appear
                          here.
                        </Empty>
                      ))}
                    {historyTab === "tests" && (
                      <>
                        <div className="panel-title">
                          <h2>Independent reference tests</h2>
                          <span className="tag neutral">Advanced</span>
                        </div>
                        <p className="section-description">
                          Save a metric total you have checked independently.
                          Future model changes must preserve that answer.
                        </p>
                        {state.regressions.map((r) => (
                          <div className="reference" key={r.id}>
                            <Icon name="check" size={16} />
                            <span>{r.name}</span>
                            <button
                              className="text-button"
                              disabled={busy}
                              onClick={() =>
                                void task(async () => {
                                  await api(
                                    `/projects/${id}/regressions/${r.id}`,
                                    "DELETE",
                                  );
                                  await refresh();
                                })
                              }
                            >
                              Remove
                            </button>
                          </div>
                        ))}
                        <form
                          className="test-form"
                          onSubmit={(e: FormEvent) => {
                            e.preventDefault();
                            void task(async () => {
                              await api(`/projects/${id}/regressions`, "POST", {
                                name: testName,
                                plan: { metrics: [testMetric] },
                                expected_rows: [
                                  { [testMetric]: Number(testValue) },
                                ],
                              });
                              await refresh();
                              setTestName("");
                              setTestValue("");
                              setNotice(
                                "Reference test saved. Review validation in Agent setup.",
                              );
                            });
                          }}
                        >
                          <label>
                            Test name
                            <input
                              value={testName}
                              onChange={(e) => setTestName(e.target.value)}
                              required
                              placeholder="e.g. Finance-checked revenue"
                            />
                          </label>
                          <label>
                            Metric
                            <select
                              required
                              value={testMetric}
                              onChange={(e) => setTestMetric(e.target.value)}
                            >
                              <option value="">Choose metric</option>
                              {state.model.views.flatMap((v) =>
                                v.metrics.map((m) => (
                                  <option key={`${v.id}.${m.name}`}>
                                    {v.id}.{m.name}
                                  </option>
                                )),
                              )}
                            </select>
                          </label>
                          <label>
                            Expected total
                            <input
                              type="number"
                              step="any"
                              required
                              value={testValue}
                              onChange={(e) => setTestValue(e.target.value)}
                            />
                          </label>
                          <button className="primary" disabled={busy}>
                            Add reference test
                          </button>
                        </form>
                        <details className="inset">
                          <summary>
                            Advanced: grouped reference test JSON
                          </summary>
                          <label className="sr-only" htmlFor="reference">
                            Reference test JSON
                          </label>
                          <textarea
                            id="reference"
                            rows={7}
                            value={reference}
                            onChange={(e) => setReference(e.target.value)}
                            placeholder='{"name":"Checked total","plan":{"metrics":["sales.revenue"]},"expected_rows":[{"sales.revenue":415}]}'
                          />
                          <button
                            className="secondary"
                            disabled={busy || !reference.trim()}
                            onClick={() =>
                              void task(async () => {
                                await api(
                                  `/projects/${id}/regressions`,
                                  "POST",
                                  JSON.parse(reference),
                                );
                                await refresh();
                                setReference("");
                                setNotice("Reference test saved.");
                              })
                            }
                          >
                            Save JSON test
                          </button>
                        </details>
                      </>
                    )}
                  </section>
                </>
              )}
            </>
          )}
          <footer>
            <span>COE Data Platform</span>
            <span>
              Local workspace · Source snapshots ·{" "}
              {provider === "demo" ? "Demo interpreter" : "Bedrock interpreter"}
            </span>
          </footer>
        </div>
      </main>
      {dialog && (
        <div
          ref={dialogRef}
          onKeyDown={(e) => {
            if (e.key === "Escape" && canClose) setDialog(null);
            if (e.key === "Tab") {
              const elements = dialogRef.current?.querySelectorAll<HTMLElement>(
                "button:not(:disabled),input:not(:disabled),textarea:not(:disabled),select:not(:disabled),summary",
              );
              if (elements?.length) {
                const first = elements[0],
                  last = elements[elements.length - 1];
                if (e.shiftKey && document.activeElement === first) {
                  e.preventDefault();
                  last.focus();
                } else if (!e.shiftKey && document.activeElement === last) {
                  e.preventDefault();
                  first.focus();
                }
              }
            }
          }}
        >
          <Modal
            title={
              dialog === "project"
                ? "Create a project"
                : dialog === "upload"
                  ? "Add a data source"
                  : dialog === "settings"
                    ? "Connection settings"
                    : proposal
                      ? "Review proposed change"
                      : "Edit business definitions"
            }
            description={
              dialog === "edit"
                ? "Describe the change in plain language. Review its scope before saving."
                : undefined
            }
            onClose={() => {
              if (canClose) setDialog(null);
            }}
          >
            {dialog === "project" && (
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  void task(async () => {
                    const p = await api<Project>("/projects", "POST", {
                      name: projectName.trim(),
                    });
                    await list();
                    setId(p.id);
                    setPage("data");
                    setDialog(null);
                    setProjectName("");
                  });
                }}
              >
                <label>
                  Project name
                  <input
                    autoComplete="off"
                    value={projectName}
                    onChange={(e) => setProjectName(e.target.value)}
                    placeholder="e.g. Sales & inventory"
                    maxLength={100}
                    required
                  />
                </label>
                <p className="form-hint">
                  Keep related tables, definitions, and questions together.
                </p>
                <div className="modal-actions">
                  <button
                    type="button"
                    className="secondary"
                    disabled={busy}
                    onClick={() => setDialog(null)}
                  >
                    Cancel
                  </button>
                  <button
                    className="primary"
                    disabled={busy || !projectName.trim()}
                  >
                    Create project
                  </button>
                </div>
              </form>
            )}
            {dialog === "upload" && (
              <>
                <div
                  className="upload-drop"
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={(e) => {
                    e.preventDefault();
                    const file = e.dataTransfer.files[0];
                    if (file && !busy) void upload(file);
                  }}
                >
                  <span className="empty-icon">
                    <Icon name="upload" size={25} />
                  </span>
                  <h3>Drop your table here</h3>
                  <p>
                    CSV or Excel · Up to 5 MiB · 25,000 rows
                    <br />
                    Excel files must contain one worksheet with values.
                  </p>
                  <input
                    ref={fileRef}
                    type="file"
                    className="sr-only"
                    accept=".csv,.xlsx"
                    aria-label="Upload CSV or XLSX"
                    onChange={(e) => {
                      const file = e.target.files?.[0];
                      if (file) void upload(file);
                      e.target.value = "";
                    }}
                  />
                  <button
                    className="primary"
                    disabled={busy}
                    onClick={() => fileRef.current?.click()}
                  >
                    Choose file
                  </button>
                </div>
                {!hasData && (
                  <button
                    className="sample-option"
                    disabled={busy}
                    onClick={() => void sample()}
                  >
                    <span className="table-icon">
                      <Icon name="data" />
                    </span>
                    <span>
                      <strong>Explore with sample data</strong>
                      <small>
                        Sales + Inventory · ready for the demo walkthrough
                      </small>
                    </span>
                    <Icon name="arrow" />
                  </button>
                )}
              </>
            )}
            {dialog === "edit" &&
              (!proposal ? (
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    void task(async () => {
                      setProposal(
                        await api<Proposal>(`/projects/${id}/changes`, "POST", {
                          message,
                          base_version: state!.project.head,
                        }),
                      );
                    });
                  }}
                >
                  <label htmlFor="edit-message">
                    What would you like to change?
                  </label>
                  <textarea
                    id="edit-message"
                    value={message}
                    onChange={(e) => setMessage(e.target.value)}
                    rows={4}
                    maxLength={4000}
                    placeholder="Explain a metric, exclusion, or relationship…"
                    required
                  />
                  {provider === "demo" && (
                    <p className="form-hint">
                      Demo mode supports the example patterns below. Bedrock
                      supports broader wording within the same available
                      operations.
                    </p>
                  )}
                  <div className="edit-examples">
                    {edits.map((s) => (
                      <button
                        type="button"
                        key={s}
                        onClick={() => setMessage(s)}
                      >
                        {s}
                        <Icon name="arrow" size={13} />
                      </button>
                    ))}
                  </div>
                  <div className="modal-actions">
                    <button
                      type="button"
                      className="secondary"
                      onClick={() => setDialog(null)}
                      disabled={busy}
                    >
                      Cancel
                    </button>
                    <button
                      className="primary"
                      disabled={busy || !message.trim()}
                    >
                      Preview change
                      <Icon name="arrow" size={16} />
                    </button>
                  </div>
                </form>
              ) : (
                <div>
                  {proposal.clarification ? (
                    <div className="callout">{proposal.clarification}</div>
                  ) : (
                    <>
                      <div
                        className={`callout ${proposal.validation?.valid ? "success" : "danger"}`}
                      >
                        <Icon
                          name={proposal.validation?.valid ? "check" : "info"}
                        />
                        <div>
                          <strong>
                            {proposal.validation?.valid
                              ? "Validation passed"
                              : "Resolve these issues before saving"}
                          </strong>
                          <p>{proposal.changes?.summary}</p>
                          {proposal.validation?.errors.map((e) => (
                            <p key={e}>{e}</p>
                          ))}
                        </div>
                      </div>
                      <details className="change-details" open>
                        <summary>Exact changes</summary>
                        <pre className="diff">{proposal.diff}</pre>
                      </details>
                      {!!proposal.validation?.warnings.length && (
                        <details>
                          <summary>
                            Assumptions to review (
                            {proposal.validation.warnings.length})
                          </summary>
                          <ul>
                            {proposal.validation.warnings.map((w) => (
                              <li key={w}>{w}</li>
                            ))}
                          </ul>
                        </details>
                      )}
                    </>
                  )}
                </div>
              ))}
            {dialog === "edit" && proposal && (
              <div className="modal-actions">
                <button
                  className="secondary"
                  disabled={busy}
                  onClick={() => {
                    setProposal(null);
                  }}
                >
                  Back to editing
                </button>
                {proposal.id && (
                  <button
                    className="primary"
                    disabled={busy || !proposal.validation?.valid}
                    onClick={() => void apply()}
                  >
                    Save to draft
                    <Icon name="check" size={16} />
                  </button>
                )}
              </div>
            )}
            {dialog === "settings" && (
              <>
                <div className="callout">
                  <Icon name="info" />
                  <div>
                    <strong>
                      {provider === "demo"
                        ? "Offline demo mode"
                        : "Amazon Bedrock mode"}
                    </strong>
                    <p>
                      The model provider is configured when starting the server.
                      This token connects the interface to a protected local
                      API.
                    </p>
                  </div>
                </div>
                <label>
                  API token
                  <input
                    type="password"
                    autoComplete="off"
                    onChange={(e) => setToken(e.target.value)}
                    placeholder="Only if configured on the server"
                  />
                </label>
                <div className="modal-actions">
                  <button
                    className="primary"
                    disabled={busy}
                    onClick={() =>
                      void task(async () => {
                        const c = await api<{ provider: string }>("/config");
                        setProvider(c.provider);
                        const p = await list();
                        if (p.length) setId(p[0].id);
                        setDialog(null);
                        setNotice("Connection established.");
                      })
                    }
                  >
                    Reconnect
                  </button>
                </div>
              </>
            )}
            {busy && (
              <p role="status" className="dialog-status">
                Working…
              </p>
            )}
            {error && (
              <p role="alert" className="dialog-error">
                {error}
              </p>
            )}
          </Modal>
        </div>
      )}
    </div>
  );
}
