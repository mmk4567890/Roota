import { FileText, XCircle } from "lucide-react";
import {
  formatCitationLine,
  fullDocCitation,
  type CauseStatus,
  type NextAction,
  type Source,
} from "../api";
import { CornerTicks } from "./CornerTicks";

interface OutcomeViewProps {
  action: NextAction;
  causes: CauseStatus[];
  onViewReport: () => void;
  onCloseSession: () => void;
  closeBusy: boolean;
  closed: boolean;
}

export function OutcomeView({
  action,
  causes,
  onViewReport,
  onCloseSession,
  closeBusy,
  closed,
}: OutcomeViewProps) {
  const isRoot = action.type === "root_cause";
  const cause = causes.find((item) => item.cause_id === action.cause_id);
  const source: Source | null = action.source;
  const inconclusive = causes.filter((item) => item.status === "inconclusive");

  return (
    <CornerTicks className="bg-transparent px-4 py-5 sm:px-6 sm:py-6">
      <p className="hud-mono-tag">
        {isRoot ? "[ OUTCOME ]" : "[ ESCALATION ]"}
      </p>
      <h2 className="hud-display mt-3 text-32">
        {isRoot ? "ROOT CAUSE" : "ESCALATED"}
      </h2>

      {isRoot ? (
        <div className="mt-5 space-y-3">
          <p className="text-20 text-hud-text">{cause?.name ?? action.cause_id}</p>
          <p className="text-16 leading-relaxed text-hud-muted">{action.message}</p>
          {source ? (
            <p className="text-14 text-hud-muted">{formatCitationLine(source)}</p>
          ) : null}
        </div>
      ) : (
        <div className="mt-5 space-y-3">
          <p className="flex items-center gap-2 text-16 text-hud-text">
            <span
              className="inline-block h-2 w-2 rounded-full bg-hud-escalated"
              aria-hidden
            />
            Escalate to a senior technician / OEM support
          </p>
          <p className="text-16 leading-relaxed text-hud-muted">{action.message}</p>
          {inconclusive.length > 0 ? (
            <div>
              <p className="hud-mono-tag mb-2">[ INCONCLUSIVE ]</p>
              <ul className="space-y-1 text-14 text-hud-muted">
                {inconclusive.map((item) => (
                  <li key={item.cause_id}>{item.name}</li>
                ))}
              </ul>
            </div>
          ) : null}
          {source ? (
            <p className="text-14 text-hud-faint">
              {fullDocCitation(source.doc_id)}
            </p>
          ) : null}
        </div>
      )}

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
