import { useState } from "react";
import {
  AlertTriangle,
  Check,
  Circle,
  CircleDashed,
  HelpCircle,
  X,
} from "lucide-react";
import type { CauseStatus, CauseStatusKind } from "../api";
import { fieldLabel } from "../labels";
import type { FieldInfo } from "../api";

interface CauseRailProps {
  causes: CauseStatus[];
  fields: FieldInfo[];
  /** When true (outcome view), remaining open causes show as Not checked. */
  outcomeMode?: boolean;
}

function statusIcon(status: CauseStatusKind, notChecked: boolean) {
  if (notChecked) {
    return <CircleDashed className="h-3.5 w-3.5 text-hud-faint" aria-hidden />;
  }
  switch (status) {
    case "confirmed":
      return <Check className="h-3.5 w-3.5 text-hud-confirmed" aria-hidden />;
    case "ruled_out":
      return <X className="h-3.5 w-3.5 text-hud-faint" aria-hidden />;
    case "inconclusive":
      return <HelpCircle className="h-3.5 w-3.5 text-hud-inconclusive" aria-hidden />;
    case "contradiction":
      return <AlertTriangle className="h-3.5 w-3.5 text-hud-escalated" aria-hidden />;
    default:
      return <Circle className="h-3.5 w-3.5 text-hud-muted" aria-hidden />;
  }
}

function reasonLine(
  cause: CauseStatus,
  fields: FieldInfo[],
  notChecked: boolean,
): string {
  if (notChecked) {
    return "Not checked";
  }
  if (cause.because.length === 0) {
    switch (cause.status) {
      case "open":
        return "Still open";
      case "confirmed":
        return "Confirmed";
      case "ruled_out":
        return "Ruled out";
      case "inconclusive":
        return "Inconclusive";
      case "contradiction":
        return "Contradiction";
    }
  }
  const labeled = cause.because.map((name) => fieldLabel(fields, name)).join(", ");
  switch (cause.status) {
    case "ruled_out":
      return `Ruled out by ${labeled}`;
    case "confirmed":
      return `Confirmed by ${labeled}`;
    case "inconclusive":
      return `Left unresolved by ${labeled}`;
    case "contradiction":
      return `Conflicting facts: ${labeled}`;
    default:
      return labeled;
  }
}

export function CauseRail({
  causes,
  fields,
  outcomeMode = false,
}: CauseRailProps) {
  const [selected, setSelected] = useState<string | null>(null);

  return (
    <nav aria-label="Cause progress" className="no-print">
      <ul className="flex gap-2 overflow-x-auto pb-1 max-[899px]:flex-row min-[900px]:flex-col min-[900px]:gap-1 min-[900px]:overflow-visible min-[900px]:pb-0">
        {causes.map((cause) => {
          const notChecked =
            outcomeMode &&
            (cause.status === "open" || cause.status === "inconclusive") &&
            cause.because.length === 0;
          const isSelected = selected === cause.cause_id;
          return (
            <li key={cause.cause_id} className="min-w-[10rem] min-[900px]:min-w-0">
              <button
                type="button"
                className={`flex w-full items-start gap-2 rounded-[4px] border px-2 py-2 text-left transition-colors duration-hud ${
                  isSelected
                    ? "border-white/16 bg-hud-surface"
                    : "border-transparent hover:border-white/10"
                }`}
                aria-pressed={isSelected}
                onClick={() =>
                  setSelected((prev) =>
                    prev === cause.cause_id ? null : cause.cause_id,
                  )
                }
              >
                <span className="mt-0.5 shrink-0">
                  {statusIcon(cause.status, notChecked)}
                </span>
                <span className="min-w-0">
                  <span className="block text-14 text-hud-text leading-snug">
                    {cause.name}
                  </span>
                  {isSelected ? (
                    <span className="mt-1 block text-12 text-hud-muted">
                      {reasonLine(cause, fields, notChecked)}
                    </span>
                  ) : null}
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
