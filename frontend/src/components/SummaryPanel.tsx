import { useEffect, useState } from "react";
import {
  ApiError,
  formatSource,
  getSessionSummary,
  getSessionSummaryMarkdown,
  type CauseStatus,
  type SessionSummary,
} from "../api";
import { ErrorBanner } from "./ErrorBanner";

interface SummaryPanelProps {
  sessionId: string;
  /** Load and reveal when the session reaches a terminal outcome or is closed. */
  autoOpen?: boolean;
  /** Changes when diagnostic outcome changes so an open summary refreshes. */
  outcomeKey?: string;
}

export function SummaryPanel({
  sessionId,
  autoOpen = false,
  outcomeKey = "",
}: SummaryPanelProps) {
  const [open, setOpen] = useState(false);
  const [summary, setSummary] = useState<SessionSummary | null>(null);
  const [markdown, setMarkdown] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  async function load(): Promise<void> {
    setBusy(true);
    setError(null);
    try {
      const [json, md] = await Promise.all([
        getSessionSummary(sessionId),
        getSessionSummaryMarkdown(sessionId),
      ]);
      setSummary(json);
      setMarkdown(md);
      setOpen(true);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : err instanceof Error
            ? err.message
            : "Failed to load summary",
      );
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    if (!autoOpen) {
      return;
    }
    void load();
    // Intentionally omit `load`: only re-fetch on outcome / session changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoOpen, sessionId, outcomeKey]);

  async function copyMarkdown(): Promise<void> {
    if (!markdown) {
      return;
    }
    try {
      await navigator.clipboard.writeText(markdown);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      setError("Could not copy to clipboard");
    }
  }

  function downloadMarkdown(): void {
    if (!markdown) {
      return;
    }
    const blob = new Blob([markdown], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `roota-session-${sessionId}.md`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  function printSummary(): void {
    window.print();
  }

  return (
    <section
      id="session-summary"
      aria-labelledby="summary-heading"
      className="session-summary rounded-md border border-ink-200 bg-white px-4 py-4"
    >
      <div className="flex flex-wrap items-center justify-between gap-2 no-print">
        <h2 id="summary-heading" className="text-sm font-semibold text-ink-900">
          Summary
        </h2>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            name="load-summary"
            disabled={busy}
            onClick={() => void load()}
            className="rounded border border-ink-300 px-3 py-1.5 text-sm font-medium text-ink-800 disabled:opacity-50"
          >
            {busy ? "Loading…" : open ? "Refresh" : "Show summary"}
          </button>
          {markdown ? (
            <>
              <button
                type="button"
                name="copy-summary"
                onClick={() => void copyMarkdown()}
                className="rounded border border-ink-300 px-3 py-1.5 text-sm font-medium text-ink-800"
              >
                {copied ? "Copied" : "Copy"}
              </button>
              <button
                type="button"
                name="download-summary"
                onClick={downloadMarkdown}
                className="rounded border border-ink-300 px-3 py-1.5 text-sm font-medium text-ink-800"
              >
                Download
              </button>
              <button
                type="button"
                name="print-summary"
                onClick={printSummary}
                className="rounded border border-ink-300 px-3 py-1.5 text-sm font-medium text-ink-800"
              >
                Print / Save as PDF
              </button>
            </>
          ) : null}
        </div>
      </div>

      {error ? (
        <div className="mt-3 no-print">
          <ErrorBanner message={error} onDismiss={() => setError(null)} />
        </div>
      ) : null}

      {open && summary ? <SummaryBody summary={summary} /> : null}
    </section>
  );
}

function SummaryBody({ summary }: { summary: SessionSummary }) {
  return (
    <div className="summary-print-body mt-4 space-y-4 text-sm text-ink-800">
      <header className="print-only hidden">
        <h1 className="text-lg font-semibold">{summary.display_name}</h1>
        <p className="text-ink-500">
          {summary.equipment_label} · {summary.status}
        </p>
      </header>

      <OutcomeBanner summary={summary} />

      <section aria-labelledby="summary-causes-heading">
        <h3
          id="summary-causes-heading"
          className="text-xs font-semibold uppercase tracking-wide text-ink-500"
        >
          Causes
        </h3>
        <ul className="mt-2 space-y-1">
          {summary.causes.map((cause) => (
            <CauseChecklistItem key={cause.cause_id} cause={cause} />
          ))}
        </ul>
      </section>

      <section aria-labelledby="summary-facts-heading">
        <h3
          id="summary-facts-heading"
          className="text-xs font-semibold uppercase tracking-wide text-ink-500"
        >
          Facts timeline
        </h3>
        {summary.facts.length === 0 ? (
          <p className="mt-1 text-ink-400">No facts reported.</p>
        ) : (
          <ol className="mt-2 space-y-2">
            {summary.facts.map((fact) => (
              <li
                key={`${fact.event_id}-${fact.field}-${String(fact.value)}`}
                className={
                  fact.undone
                    ? "rounded border border-ink-100 bg-ink-50 px-3 py-2 text-ink-400 line-through"
                    : "rounded border border-ink-100 bg-ink-50 px-3 py-2"
                }
              >
                <div className="flex flex-wrap items-baseline gap-2">
                  <code className="font-medium">{fact.field}</code>
                  <span>= {String(fact.value)}</span>
                  <span className="text-xs text-ink-500">
                    {fact.how === "observation" ? "typed observation" : "form"}
                  </span>
                  <time className="text-xs text-ink-400" dateTime={fact.reported_at}>
                    {new Date(fact.reported_at).toLocaleString()}
                  </time>
                  {fact.undone ? (
                    <span className="text-xs">(undone)</span>
                  ) : null}
                </div>
                {fact.text ? (
                  <p className="mt-1 text-xs text-ink-600">“{fact.text}”</p>
                ) : null}
              </li>
            ))}
          </ol>
        )}
      </section>

      <section aria-labelledby="summary-citations-heading">
        <h3
          id="summary-citations-heading"
          className="text-xs font-semibold uppercase tracking-wide text-ink-500"
        >
          Manual citations
        </h3>
        {summary.citations.length === 0 ? (
          <p className="mt-1 text-ink-400">No citations used yet.</p>
        ) : (
          <ul className="mt-2 space-y-3">
            {summary.citations.map((cite) => (
              <li
                key={`${cite.used_for}-${cite.doc_id}-${cite.page}`}
                className="rounded border border-ink-100 px-3 py-2"
              >
                <p className="font-medium text-ink-900">
                  {cite.doc_id}
                  {cite.page != null ? `, p.${cite.page}` : ""}
                </p>
                <p className="text-xs text-ink-500">
                  §{cite.section} — {cite.used_for}
                </p>
                {cite.passage ? (
                  <blockquote className="mt-2 border-l-2 border-ink-200 pl-3 text-xs text-ink-700 whitespace-pre-wrap">
                    {cite.passage}
                  </blockquote>
                ) : (
                  <p className="mt-2 text-xs text-ink-400">
                    Passage unavailable (manual not ingested).
                  </p>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      {summary.root_cause ? (
        <section aria-labelledby="summary-action-heading">
          <h3
            id="summary-action-heading"
            className="text-xs font-semibold uppercase tracking-wide text-ink-500"
          >
            Corrective action
          </h3>
          <p className="mt-1">{summary.root_cause.corrective_action}</p>
          <p className="mt-1 text-xs text-ink-500">
            {formatSource(summary.root_cause.source)}
          </p>
        </section>
      ) : null}
    </div>
  );
}

function OutcomeBanner({ summary }: { summary: SessionSummary }) {
  if (summary.root_cause) {
    return (
      <div
        role="status"
        className="rounded-md border border-emerald-300 bg-emerald-50 px-3 py-3 text-emerald-950"
      >
        <p className="font-semibold">Root cause found</p>
        <p className="mt-1">{summary.root_cause.name}</p>
      </div>
    );
  }
  if (summary.escalation_reason) {
    const inconclusive = summary.causes.filter((c) => c.status === "inconclusive");
    return (
      <div
        role="status"
        className="rounded-md border border-amber-300 bg-amber-50 px-3 py-3 text-amber-950"
      >
        <p className="font-semibold">Escalate</p>
        <p className="mt-1">{summary.escalation_reason}</p>
        {inconclusive.length > 0 ? (
          <p className="mt-2 text-xs">
            Inconclusive causes:{" "}
            {inconclusive.map((c) => c.name).join(", ")}
          </p>
        ) : null}
      </div>
    );
  }
  return (
    <div
      role="status"
      className="rounded-md border border-ink-200 bg-ink-50 px-3 py-3 text-ink-800"
    >
      <p className="font-semibold">Session in progress</p>
      <p className="mt-1 text-ink-500">
        {summary.display_name} · {summary.equipment_label}
      </p>
    </div>
  );
}

function CauseChecklistItem({ cause }: { cause: CauseStatus }) {
  const mark = statusMark(cause.status);
  return (
    <li className="flex flex-wrap items-baseline gap-2 rounded border border-ink-100 px-3 py-2">
      <span aria-hidden="true" className="font-mono text-ink-500">
        {mark}
      </span>
      <span className="font-medium text-ink-900">{cause.name}</span>
      <span className="text-xs uppercase tracking-wide text-ink-500">
        {cause.status.replace("_", " ")}
      </span>
      {cause.because.length > 0 ? (
        <span className="text-xs text-ink-500">
          ({cause.because.join(", ")})
        </span>
      ) : null}
    </li>
  );
}

function statusMark(status: CauseStatus["status"]): string {
  switch (status) {
    case "confirmed":
      return "[x]";
    case "ruled_out":
      return "[-]";
    case "inconclusive":
      return "[?]";
    case "contradiction":
      return "[!]";
    default:
      return "[ ]";
  }
}
