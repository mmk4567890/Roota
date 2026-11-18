import { useEffect, useState } from "react";
import { Copy, Download, Printer, X } from "lucide-react";
import {
  ApiError,
  getSessionSummary,
  getSessionSummaryMarkdown,
  type SessionSummary,
} from "../api";
import { ErrorBanner } from "./ErrorBanner";

interface ReportViewProps {
  sessionId: string;
  onClose: () => void;
}

export function ReportView({ sessionId, onClose }: ReportViewProps) {
  const [summary, setSummary] = useState<SessionSummary | null>(null);
  const [markdown, setMarkdown] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(true);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      setBusy(true);
      setError(null);
      try {
        const [json, md] = await Promise.all([
          getSessionSummary(sessionId),
          getSessionSummaryMarkdown(sessionId),
        ]);
        if (!cancelled) {
          setSummary(json);
          setMarkdown(md);
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof ApiError
              ? err.message
              : err instanceof Error
                ? err.message
                : "Failed to load report",
          );
        }
      } finally {
        if (!cancelled) {
          setBusy(false);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent): void {
      if (event.key === "Escape") {
        onClose();
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

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
    <div className="report-overlay fixed inset-0 z-50 overflow-y-auto bg-hud-bg text-hud-text">
      <div className="no-print sticky top-0 z-10 border-b border-white/10 bg-hud-bg">
        <div className="mx-auto flex max-w-content flex-wrap items-center justify-between gap-2 px-4 py-3 sm:px-6">
          <p className="hud-mono-tag">Session report</p>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              className="hud-button"
              disabled={!markdown}
              onClick={() => void copyMarkdown()}
            >
              <Copy className="h-4 w-4" aria-hidden />
              {copied ? "Copied" : "Copy"}
            </button>
            <button
              type="button"
              className="hud-button"
              disabled={!markdown}
              onClick={downloadMarkdown}
            >
              <Download className="h-4 w-4" aria-hidden />
              Download
            </button>
            <button
              type="button"
              className="hud-button"
              onClick={() => window.print()}
            >
              <Printer className="h-4 w-4" aria-hidden />
              Print / Save as PDF
            </button>
            <button
              type="button"
              className="hud-button"
              onClick={onClose}
              aria-label="Close report"
            >
              <X className="h-4 w-4" aria-hidden />
              Close
            </button>
          </div>
        </div>
      </div>

      <article
        id="session-report"
        className="session-report mx-auto max-w-content px-4 py-8 sm:px-6 summary-print-body"
      >
        {error ? <ErrorBanner message={error} /> : null}
        {busy ? (
          <p className="text-14 text-hud-muted" role="status">
            Loading report…
          </p>
        ) : null}
        {summary ? <ReportBody summary={summary} /> : null}
      </article>
    </div>
  );
}

function ReportBody({ summary }: { summary: SessionSummary }) {
  return (
    <div className="space-y-8 text-[15px] leading-relaxed text-hud-text">
      <header>
        <h1 className="hud-display text-32">
          {summary.display_name}
        </h1>
        <p className="mt-1 text-hud-muted">
          {summary.equipment_label}
          {summary.status === "closed" ? " · Closed" : ""}
        </p>
      </header>

      <section>
        <h2 className="hud-mono-tag mb-3">Outcome</h2>
        {summary.outcome ? (
          <div className="space-y-2">
            {summary.outcome.map((paragraph) => (
              <p key={paragraph}>{paragraph}</p>
            ))}
          </div>
        ) : (
          <p>Session closed without a diagnosis.</p>
        )}
      </section>

      <section>
        <h2 className="hud-mono-tag mb-3">Cause checklist</h2>
        <ul className="space-y-3">
          {summary.causes.map((cause) => (
            <li
              key={cause.cause_id}
              className="report-cause grid grid-cols-[7rem_minmax(0,1fr)] items-start gap-x-3"
            >
              <span className="report-badge inline-block whitespace-nowrap rounded-[3px] border border-white/16 px-1.5 py-0.5 text-center text-12 text-hud-muted">
                {cause.status_label}
              </span>
              <div className="min-w-0">
                <p className="text-hud-text">{cause.name}</p>
                {cause.reason ? (
                  <p className="text-14 text-hud-muted">{cause.reason}</p>
                ) : null}
              </div>
            </li>
          ))}
        </ul>
      </section>

      <section>
        <h2 className="hud-mono-tag mb-3">Timeline</h2>
        {summary.facts.length === 0 ? (
          <p className="text-hud-muted">No facts reported.</p>
        ) : (
          <ol className="space-y-2">
            {summary.facts.map((fact) => (
              <li key={`${fact.event_id}-${fact.field}`}>
                <span className="font-medium">
                  {fact.field_label}: {fact.value_label}
                </span>
                {fact.text ? (
                  <span className="text-hud-muted"> — “{fact.text}”</span>
                ) : null}
                {fact.undone ? (
                  <span className="text-hud-faint"> (undone)</span>
                ) : null}
              </li>
            ))}
          </ol>
        )}
      </section>

      <section>
        <h2 className="hud-mono-tag mb-3">Citations</h2>
        {summary.citations.length === 0 ? (
          <p className="text-hud-muted">No citations.</p>
        ) : (
          <ul className="space-y-3">
            {summary.citations.map((cite) => (
              <li key={`${cite.doc_id}-${cite.section}-${cite.used_for}`}>
                <p>
                  {cite.short_name} · {cite.section_label}
                  {cite.page != null ? ` · p. ${cite.page}` : ""}
                </p>
                <p className="text-hud-muted">{cite.full_title}</p>
                {cite.passage ? (
                  <blockquote className="mt-1 border-l-2 border-white/16 pl-3 text-hud-text whitespace-pre-wrap">
                    {cite.passage}
                  </blockquote>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
