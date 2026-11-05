import { useState } from "react";
import type { Evidence, EvidenceStatus } from "../api";

interface EvidencePanelProps {
  evidence: Evidence[] | null;
  evidenceStatus: EvidenceStatus | null;
  evidenceError: string | null;
}

export function EvidencePanel({
  evidence,
  evidenceStatus,
  evidenceError,
}: EvidencePanelProps) {
  const [relatedOpen, setRelatedOpen] = useState(false);
  const [morePageOpen, setMorePageOpen] = useState(false);

  if (!evidenceStatus) {
    return null;
  }

  if (evidenceStatus === "no_manual") {
    return (
      <section
        aria-labelledby="evidence-heading"
        className="rounded-md border border-ink-200 bg-white px-4 py-3"
      >
        <h3 id="evidence-heading" className="text-sm font-semibold text-ink-900">
          Evidence
        </h3>
        <p className="mt-1 text-sm text-ink-500">
          No manual passages available for this citation yet.
        </p>
      </section>
    );
  }

  if (evidenceStatus === "unavailable") {
    return (
      <section
        aria-labelledby="evidence-heading"
        className="rounded-md border border-ink-200 bg-white px-4 py-3"
      >
        <h3 id="evidence-heading" className="text-sm font-semibold text-ink-900">
          Evidence
        </h3>
        <p className="mt-1 text-sm text-ink-500">
          Manual evidence unavailable
          {evidenceError ? `: ${evidenceError}` : "."}
        </p>
      </section>
    );
  }

  const cited = (evidence ?? []).filter((item) => item.kind === "cited");
  const related = (evidence ?? []).filter((item) => item.kind === "related");

  return (
    <section
      aria-labelledby="evidence-heading"
      className="rounded-md border border-ink-200 bg-white px-4 py-3"
    >
      <h3 id="evidence-heading" className="text-sm font-semibold text-ink-900">
        Evidence
      </h3>

      {cited.length === 0 ? (
        <p className="mt-2 text-sm text-ink-500">No cited passage attached.</p>
      ) : (
        <div className="mt-2">
          {/* The API orders a cited page's chunks by relevance to the check;
              the rest of that page (often other faults' entries) is folded. */}
          <Passage item={cited[0]} />
          {cited.length > 1 ? (
            <div className="mt-2">
              <button
                type="button"
                className="text-sm font-medium text-accent underline"
                aria-expanded={morePageOpen}
                onClick={() => setMorePageOpen((open) => !open)}
              >
                {morePageOpen ? "Hide" : "Show"} more from this page ({cited.length - 1})
              </button>
              {morePageOpen ? (
                <ul className="mt-2 space-y-3">
                  {/* Several chunks share doc, page and section, so those
                      cannot be the key; the API order is stable per response. */}
                  {cited.slice(1).map((item, index) => (
                    <li key={`cited-${index + 1}`}>
                      <Passage item={item} />
                    </li>
                  ))}
                </ul>
              ) : null}
            </div>
          ) : null}
        </div>
      )}

      {related.length > 0 ? (
        <div className="mt-3 border-t border-ink-100 pt-3">
          <button
            type="button"
            className="text-sm font-medium text-accent underline"
            aria-expanded={relatedOpen}
            onClick={() => setRelatedOpen((open) => !open)}
          >
            {relatedOpen ? "Hide" : "Show"} related passages ({related.length})
          </button>
          {relatedOpen ? (
            <ul className="mt-2 space-y-3">
              {related.map((item, index) => (
                <li key={`related-${index}`}>
                  <Passage item={item} />
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

function Passage({ item }: { item: Evidence }) {
  return (
    <figure className="rounded border border-ink-100 bg-ink-50 px-3 py-2">
      <figcaption className="text-xs font-medium text-ink-500">
        {item.title} — {item.doc_id}
        {item.section ? `, §${item.section}` : ""}, p.{item.page}
      </figcaption>
      <blockquote className="mt-1 whitespace-pre-wrap text-sm text-ink-800">
        {item.text}
      </blockquote>
    </figure>
  );
}
