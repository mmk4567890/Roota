import type { CauseStatus } from "../api";

interface CausesPanelProps {
  causes: CauseStatus[];
}

export function CausesPanel({ causes }: CausesPanelProps) {
  // Preserve API order within each group — no client-side reordering.
  const confirmed = causes.filter((item) => item.status === "confirmed");
  const stillRelevant = causes.filter(
    (item) => item.status === "open" || item.status === "contradiction",
  );
  const ruledOut = causes.filter((item) => item.status === "ruled_out");

  return (
    <section
      aria-labelledby="causes-heading"
      className="rounded-md border border-ink-200 bg-white px-4 py-4"
    >
      <h2 id="causes-heading" className="text-sm font-semibold text-ink-900">
        Causes
      </h2>

      <CauseGroup title="Confirmed" items={confirmed} empty="None confirmed yet." />
      <CauseGroup
        title="Still relevant"
        items={stillRelevant}
        empty="None still under investigation."
        markPromoted
      />
      <CauseGroup
        title="Ruled out"
        items={ruledOut}
        empty="None ruled out yet."
        showBecause
      />
    </section>
  );
}

interface CauseGroupProps {
  title: string;
  items: CauseStatus[];
  empty: string;
  markPromoted?: boolean;
  showBecause?: boolean;
}

function CauseGroup({
  title,
  items,
  empty,
  markPromoted = false,
  showBecause = false,
}: CauseGroupProps) {
  return (
    <div className="mt-4">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-ink-500">
        {title}
      </h3>
      {items.length === 0 ? (
        <p className="mt-1 text-sm text-ink-400">{empty}</p>
      ) : (
        <ul className="mt-2 space-y-2">
          {items.map((item) => (
            <li
              key={item.cause_id}
              className="rounded border border-ink-100 bg-ink-50 px-3 py-2 text-sm"
            >
              <div className="flex flex-wrap items-baseline gap-2">
                <span className="font-medium text-ink-900">{item.name}</span>
                {markPromoted && item.promoted ? (
                  <span className="rounded bg-accent-muted px-1.5 py-0.5 text-xs font-medium text-accent">
                    Promoted
                  </span>
                ) : null}
                {item.status === "contradiction" ? (
                  <span className="rounded bg-red-100 px-1.5 py-0.5 text-xs font-medium text-red-800">
                    Contradiction
                  </span>
                ) : null}
              </div>
              {showBecause && item.because.length > 0 ? (
                <p className="mt-1 text-xs text-ink-500">
                  Ruled out by: {item.because.join(", ")}
                </p>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
