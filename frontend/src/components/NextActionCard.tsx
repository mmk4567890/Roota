import {
  formatSource,
  type CauseStatus,
  type NextAction,
} from "../api";

interface NextActionCardProps {
  action: NextAction;
  causes: CauseStatus[];
}

function causeName(
  causes: CauseStatus[],
  causeId: string | null,
): string | null {
  if (!causeId) {
    return null;
  }
  return causes.find((item) => item.cause_id === causeId)?.name ?? causeId;
}

export function NextActionCard({ action, causes }: NextActionCardProps) {
  const title = headingFor(action.type);
  const shell = shellClasses(action.type);

  return (
    <section
      aria-labelledby="next-action-heading"
      className={`rounded-md border px-4 py-4 sm:px-5 ${shell}`}
    >
      <p className="text-xs font-semibold uppercase tracking-wider opacity-80">
        Next action
      </p>
      <h2 id="next-action-heading" className="mt-1 text-lg font-semibold">
        {title}
      </h2>

      {action.type === "check" && action.check ? (
        <div className="mt-3 space-y-2 text-sm">
          <p className="text-base font-medium leading-snug">
            {action.check.instruction}
          </p>
          <p className="text-ink-600">
            <span className="font-medium text-ink-800">Reason: </span>
            {action.check.reason}
          </p>
          <p className="text-ink-600">
            <span className="font-medium text-ink-800">Source: </span>
            {formatSource(action.check.source)}
          </p>
        </div>
      ) : null}

      {action.type === "need_info" ? (
        <div className="mt-3 space-y-2 text-sm">
          <p className="rounded border border-amber-300 bg-amber-50 px-3 py-3 text-base font-medium text-amber-950">
            {action.message}
          </p>
          {action.fields && action.fields.length > 0 ? (
            <p className="text-ink-600">
              Needs clarification on: {action.fields.join(", ")}
            </p>
          ) : null}
        </div>
      ) : null}

      {action.type === "root_cause" ? (
        <div className="mt-3 space-y-2 text-sm">
          <p>
            <span className="font-medium">Cause: </span>
            {causeName(causes, action.cause_id) ?? "—"}
          </p>
          <p className="text-base font-medium leading-snug">{action.message}</p>
          {action.source ? (
            <p className="text-ink-600">
              <span className="font-medium text-ink-800">Source: </span>
              {formatSource(action.source)}
            </p>
          ) : null}
        </div>
      ) : null}

      {action.type === "escalate" ? (
        <div className="mt-3 space-y-3 text-sm">
          <p className="rounded border-2 border-red-700 bg-red-100 px-3 py-3 text-base font-semibold text-red-950">
            Stop — escalate to a senior technician / OEM support
          </p>
          <p className="leading-snug text-red-950">{action.message}</p>
        </div>
      ) : null}
    </section>
  );
}

function headingFor(type: NextAction["type"]): string {
  switch (type) {
    case "check":
      return "Perform this check";
    case "need_info":
      return "Need more information";
    case "root_cause":
      return "Root cause identified";
    case "escalate":
      return "Escalate";
  }
}

function shellClasses(type: NextAction["type"]): string {
  switch (type) {
    case "check":
      return "border-accent bg-white text-ink-950";
    case "need_info":
      return "border-amber-400 bg-amber-50 text-ink-950";
    case "root_cause":
      return "border-accent bg-accent-muted text-ink-950";
    case "escalate":
      return "border-red-600 bg-red-50 text-red-950";
  }
}
