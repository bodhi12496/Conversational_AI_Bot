import type { ReactNode } from "react";
import type { Result } from "./types";

export function Icon({ name, size = 18 }: { name: string; size?: number }) {
  const paths: Record<string, ReactNode> = {
    home: (
      <>
        <path d="m3 10 9-7 9 7v10a1 1 0 0 1-1 1h-6v-7h-4v7H4a1 1 0 0 1-1-1z" />
      </>
    ),
    data: (
      <>
        <ellipse cx="12" cy="5" rx="8" ry="3" />
        <path d="M4 5v14c0 4 16 4 16 0V5M4 12c0 4 16 4 16 0" />
      </>
    ),
    model: (
      <>
        <rect x="3" y="3" width="7" height="7" rx="1" />
        <rect x="14" y="14" width="7" height="7" rx="1" />
        <path d="M17 14V7h-7M7 10v7h7" />
      </>
    ),
    agent: (
      <>
        <rect x="4" y="7" width="16" height="13" rx="3" />
        <path d="M12 3v4M8 12v2m8-2v2m-7 3h6M1 11v5m22-5v5" />
      </>
    ),
    chat: (
      <path d="M21 11a8 8 0 0 1-8 8H7l-5 3 1-6a8 8 0 0 1-1-5 9 9 0 0 1 19 0Z" />
    ),
    history: (
      <>
        <path d="M3 11a9 9 0 1 1 2 7M3 3v8h8M12 7v5l3 2" />
      </>
    ),
    settings: (
      <>
        <path d="M4 7h16M4 17h16M8 4v6m8 4v6" />
      </>
    ),
    plus: <path d="M12 5v14M5 12h14" />,
    arrow: <path d="M5 12h14m-5-5 5 5-5 5" />,
    upload: (
      <>
        <path d="M12 16V3m-5 5 5-5 5 5M4 16v5h16v-5" />
      </>
    ),
    check: <path d="m5 12 4 4L19 6" />,
    close: <path d="m6 6 12 12M18 6 6 18" />,
    search: (
      <>
        <circle cx="10" cy="10" r="6" />
        <path d="m15 15 6 6" />
      </>
    ),
    file: (
      <>
        <path d="M14 2H5v20h14V7zM14 2v6h5M8 12h8m-8 4h6" />
      </>
    ),
    chevron: <path d="m9 5 7 7-7 7" />,
    code: (
      <>
        <path d="m8 6-6 6 6 6m8-12 6 6-6 6m-5-16-2 20" />
      </>
    ),
    info: (
      <>
        <circle cx="12" cy="12" r="9" />
        <path d="M12 11v6m0-10v1" />
      </>
    ),
    spark: (
      <>
        <path d="m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5z" />
      </>
    ),
  };
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {paths[name] || paths.file}
    </svg>
  );
}
export function Empty({
  icon = "data",
  title,
  children,
  action,
}: {
  icon?: string;
  title: string;
  children: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="empty-state">
      <div className="empty-icon">
        <Icon name={icon} size={26} />
      </div>
      <h2>{title}</h2>
      <p>{children}</p>
      {action}
    </div>
  );
}
export function Modal({
  title,
  description,
  children,
  onClose,
}: {
  title: string;
  description?: string;
  children: ReactNode;
  onClose: () => void;
}) {
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <section
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onClick={(e) => e.stopPropagation()}
        onKeyDown={(e) => {
          if (e.key === "Escape") onClose();
        }}
      >
        <div className="modal-head">
          <div>
            <h2>{title}</h2>
            {description && <p>{description}</p>}
          </div>
          <button
            aria-label="Close dialog"
            className="icon-button"
            onClick={onClose}
          >
            <Icon name="close" />
          </button>
        </div>
        {children}
      </section>
    </div>
  );
}
export function ResultPanel({ result }: { result: Result }) {
  return (
    <div className="answer">
      {result.clarification ? (
        <div className="callout">{result.clarification}</div>
      ) : (
        <>
          <div className="answer-heading">
            <span className="tag green">
              <Icon name="check" size={12} />
              Computed result
            </span>
            <span>Published v{result.version}</span>
          </div>
          <p>{result.summary}</p>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  {result.columns?.map((c) => (
                    <th key={c}>{c.replaceAll("_", " ")}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {result.rows?.map((r, i) => (
                  <tr key={i}>
                    {result.columns?.map((c) => (
                      <td key={c}>
                        {r[c] === null ? (
                          <span className="muted">No match</span>
                        ) : (
                          String(r[c])
                        )}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {!result.rows?.length && <p>No rows matched this question.</p>}
          <details>
            <summary>How this answer was calculated</summary>
            <pre>
              {JSON.stringify(
                {
                  definitions: result.evidence,
                  queries: result.queries,
                  plan: result.plan,
                },
                null,
                2,
              )}
            </pre>
          </details>
          <details>
            <summary>
              Assumptions & limitations ({result.warnings?.length || 0})
            </summary>
            <ul>
              {result.warnings?.map((w) => (
                <li key={w}>{w}</li>
              ))}
            </ul>
          </details>
        </>
      )}
    </div>
  );
}
