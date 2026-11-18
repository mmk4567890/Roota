import { FileText, XCircle } from "lucide-react";
import type { Outcome } from "../api";
import { CornerTicks } from "./CornerTicks";

export type OutcomeKind = "root_cause" | "escalate" | "closed";

interface OutcomeViewProps {
  kind: OutcomeKind;
  outcome: Outcome;
  onViewReport: () => void;
  onCloseSession: () => void;
  closeBusy: boolean;
  closed: boolean;
}

export function OutcomeView({
  kind,
  outcome,
  onViewReport,
  onCloseSession,
  closeBusy,
  closed,
}: OutcomeViewProps) {
  return (
    <CornerTicks className="bg-transparent px-4 py-5 sm:px-6 sm:py-6">
      <h2 className="hud-display flex items-center gap-3 text-20 sm:text-32">
        {kind === "escalate" ? (
          <span
            className="inline-block h-2 w-2 shrink-0 rounded-full bg-hud-escalated"
            aria-hidden
          />
        ) : null}
        {outcome.headline}
      </h2>

      <div className="mt-5 space-y-3">
        {outcome.paragraphs.map((paragraph, index) => (
          <p
            key={paragraph}
            className={
              index === 0
                ? "text-16 leading-relaxed text-hud-text"
                : "text-16 leading-relaxed text-hud-muted"
            }
          >
            {paragraph}
          </p>
        ))}
        {outcome.source ? (
          <p className="font-mono text-12 text-hud-muted">
            Source: {outcome.source}
          </p>
        ) : null}
      </div>

      <div className="mt-8 flex flex-wrap gap-3">
        <button type="button" className="hud-button" onClick={onViewReport}>
          <FileText className="h-4 w-4" aria-hidden />
          View report
        </button>
        {!closed ? (
          <button
            type="button"
            className="hud-button"
            disabled={closeBusy}
            onClick={onCloseSession}
          >
            <XCircle className="h-4 w-4" aria-hidden />
            {closeBusy ? "Closing…" : "Close session"}
          </button>
        ) : null}
      </div>
    </CornerTicks>
  );
}
