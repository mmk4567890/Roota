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
    <div className="fixed inset-0 z-50 overflow-y-auto bg-white text-black">
      <div className="no-print sticky top-0 z-10 flex flex-wrap items-center justify-between gap-2 border-b border-black/10 bg-white px-4 py-3">
        <p className="font-mono text-12 uppercase tracking-label text-black/60">
          Session report
        </p>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            className="inline-flex items-center gap-2 rounded-[4px] border border-black/20 px-3 py-1.5 text-14 disabled:opacity-40"
            disabled={!markdown}
            onClick={() => void copyMarkdown()}
          >
            <Copy className="h-4 w-4" aria-hidden />
            {copied ? "Copied" : "Copy"}
          </button>
          <button
            type="button"
            className="inline-flex items-center gap-2 rounded-[4px] border border-black/20 px-3 py-1.5 text-14 disabled:opacity-40"
            disabled={!markdown}
            onClick={downloadMarkdown}
          >
            <Download className="h-4 w-4" aria-hidden />
            Download
          </button>
          <button
            type="button"
            className="inline-flex items-center gap-2 rounded-[4px] border border-black/20 px-3 py-1.5 text-14"
            onClick={() => window.print()}
          >
            <Printer className="h-4 w-4" aria-hidden />
            Print / Save as PDF
          </button>
          <button
            type="button"
            className="inline-flex items-center gap-2 rounded-[4px] border border-black/20 px-3 py-1.5 text-14"
            onClick={onClose}
            aria-label="Close report"
          >
            <X className="h-4 w-4" aria-hidden />
            Close
          </button>
        </div>
      </div>

      <article
        id="session-report"
        className="session-report mx-auto max-w-content px-6 py-8 summary-print-body"
      >
        {error ? <ErrorBanner message={error} /> : null}
        {busy ? <p className="text-14 text-black/60">Loading report…</p> : null}
        {summary ? <ReportBody summary={summary} /> : null}
      </article>
    </div>
  );
}

function ReportBody({ summary }: { summary: SessionSummary }) {
  return (
    <div className="space-y-8 text-[15px] leading-relaxed text-black">
      <header>
        <h1 className="text-2xl font-normal tracking-wide">
          {summary.display_name}
        </h1>
        <p className="mt-1 text-black/70">
          {summary.equipment_label}
          {summary.status === "closed" ? " · Closed" : ""}
        </p>
      </header>

      <section>
        <h2 className="mb-2 text-lg font-medium">Outcome</h2>
        {summary.root_cause ? (
          <div className="space-y-2">
            <p>
              <span className="font-medium">Root cause:</span>{" "}
              {summary.root_cause.name}
            </p>
            <p>{summary.root_cause.corrective_action}</p>
            <p className="text-black/70">
              {summary.root_cause.source
                ? citationLine(summary, summary.root_cause.source.doc_id, summary.root_cause.source.section, summary.root_cause.source.printed_page ?? summary.root_cause.source.page)
                : null}
            </p>
          </div>
        ) : summary.escalation_reason ? (
          <div className="space-y-2">
            <p className="font-medium">Escalated</p>
            <p>{summary.escalation_reason}</p>
          </div>
        ) : (
          <p>Session closed without a terminal diagnosis.</p>
        )}
      </section>

      <section>
        <h2 className="mb-2 text-lg font-medium">Cause checklist</h2>
        <ul className="space-y-2">
          {summary.causes.map((cause) => (
            <li key={cause.cause_id} className="flex flex-wrap items-baseline gap-2">
              <span className="inline-block rounded-[3px] border border-black/20 px-1.5 py-0.5 text-12">
                {cause.status_label}
              </span>
              <span>{cause.name}</span>
              {cause.reason ? (
                <span className="text-black/60">— {cause.reason}</span>
              ) : null}
            </li>
          ))}
        </ul>
      </section>

      <section>
        <h2 className="mb-2 text-lg font-medium">Timeline</h2>
        {summary.facts.length === 0 ? (
          <p className="text-black/60">No facts reported.</p>
        ) : (
          <ol className="space-y-2">
            {summary.facts.map((fact) => (
              <li key={`${fact.event_id}-${fact.field}`}>
                <span className="font-medium">
                  {fact.field_label}: {fact.value_label}
                </span>
                {fact.text ? (
                  <span className="text-black/70"> — “{fact.text}”</span>
                ) : null}
                {fact.undone ? (
                  <span className="text-black/50"> (undone)</span>
                ) : null}
              </li>
            ))}
          </ol>
        )}
      </section>

      <section>
        <h2 className="mb-2 text-lg font-medium">Citations</h2>
        {summary.citations.length === 0 ? (
          <p className="text-black/60">No citations.</p>
        ) : (
          <ul className="space-y-3">
            {summary.citations.map((cite) => (
              <li key={`${cite.doc_id}-${cite.section}-${cite.used_for}`}>
                <p>
                  {cite.short_name} · {cite.section_label}
                  {cite.page != null ? ` · p. ${cite.page}` : ""}
                </p>
                <p className="text-black/60">{cite.full_title}</p>
                {cite.passage ? (
                  <blockquote className="mt-1 border-l-2 border-black/20 pl-3 text-black/80 whitespace-pre-wrap">
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

function citationLine(
  summary: SessionSummary,
  docId: string,
  section: string,
  page: number | null | undefined,
): string {
  const cite = summary.citations.find((item) => item.doc_id === docId);
  const name = cite?.short_name ?? docId;
  const label = cite?.section_label ?? section;
  const pageBit = page != null ? ` · p. ${page}` : "";
  return `${name} · ${label}${pageBit}`;
}
