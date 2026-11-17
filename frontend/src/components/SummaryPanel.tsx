import { useState } from "react";
import {
  ApiError,
  formatSource,
  getSessionSummary,
  getSessionSummaryMarkdown,
  type SessionSummary,
} from "../api";
import { ErrorBanner } from "./ErrorBanner";

interface SummaryPanelProps {
  sessionId: string;
}

export function SummaryPanel({ sessionId }: SummaryPanelProps) {
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

  return (
    <section
      aria-labelledby="summary-heading"
      className="rounded-md border border-ink-200 bg-white px-4 py-4"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
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
            </>
          ) : null}
        </div>
      </div>

      {error ? (
        <div className="mt-3">
          <ErrorBanner message={error} onDismiss={() => setError(null)} />
        </div>
      ) : null}

      {open && summary ? (
        <div className="mt-4 space-y-3 text-sm text-ink-800">
          <p>
            {summary.display_name} · {summary.equipment_label} ·{" "}
            {summary.status}
          </p>
          {summary.root_cause ? (
            <div>
              <h3 className="text-xs font-semibold uppercase tracking-wide text-ink-500">
                Root cause
              </h3>
              <p className="mt-1 font-medium">{summary.root_cause.name}</p>
              <p className="mt-1">{summary.root_cause.corrective_action}</p>
              <p className="mt-1 text-xs text-ink-500">
                {formatSource(summary.root_cause.source)}
              </p>
            </div>
          ) : null}
          {summary.escalation_reason ? (
            <div>
              <h3 className="text-xs font-semibold uppercase tracking-wide text-ink-500">
                Escalation
              </h3>
              <p className="mt-1">{summary.escalation_reason}</p>
            </div>
          ) : null}
          <div>
            <h3 className="text-xs font-semibold uppercase tracking-wide text-ink-500">
              Facts
            </h3>
            {summary.facts.length === 0 ? (
              <p className="mt-1 text-ink-400">No facts reported.</p>
            ) : (
              <ul className="mt-1 space-y-1">
                {summary.facts.map((fact) => (
                  <li
                    key={`${fact.event_id}-${fact.field}-${fact.how}`}
                    className={fact.undone ? "text-ink-400 line-through" : ""}
                  >
                    <code>{fact.field}</code> = {String(fact.value)} via{" "}
                    {fact.how === "observation" ? "typed observation" : "form"}
                    {fact.text ? ` (“${fact.text}”)` : ""}
                    {fact.undone ? " (undone)" : ""}
                  </li>
                ))}
              </ul>
            )}
          </div>
          {summary.citations.length > 0 ? (
            <div>
              <h3 className="text-xs font-semibold uppercase tracking-wide text-ink-500">
                Citations
              </h3>
              <ul className="mt-1 space-y-1 text-xs text-ink-500">
                {summary.citations.map((cite) => (
                  <li key={`${cite.used_for}-${cite.doc_id}-${cite.page}`}>
                    {cite.doc_id}, §{cite.section}
                    {cite.page != null ? `, p.${cite.page}` : ""} — {cite.used_for}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
