import { FileText, XCircle } from "lucide-react";
import { CornerTicks } from "./CornerTicks";

export type OutcomeKind = "root_cause" | "escalate" | "closed";

interface OutcomeViewProps {
  kind: OutcomeKind;
  /** Plain sentences from the API, one paragraph each. */
  paragraphs: string[];
  onViewReport: () => void;
  onCloseSession: () => void;
  closeBusy: boolean;
  closed: boolean;
}

const HEADINGS: Record<OutcomeKind, string> = {
  root_cause: "ROOT CAUSE",
  escalate: "ESCALATED",
  closed: "CLOSED",
};

export function OutcomeView({
  kind,
  paragraphs,
  onViewReport,
  onCloseSession,
  closeBusy,
  closed,
}: OutcomeViewProps) {
  return (
    <CornerTicks className="bg-transparent px-4 py-5 sm:px-6 sm:py-6">
      <h2 className="hud-display flex items-center gap-3 text-32">
        {kind === "escalate" ? (
          <span
            className="inline-block h-2 w-2 rounded-full bg-hud-escalated"
            aria-hidden
          />
        ) : null}
        {HEADINGS[kind]}
      </h2>

      <div className="mt-5 space-y-3">
        {paragraphs.map((paragraph, index) => (
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
