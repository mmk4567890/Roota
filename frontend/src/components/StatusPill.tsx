import type { SessionStatus } from "../api";

type SessionPhase =
  | "active"
  | "root_cause"
  | "escalated"
  | "closed";

interface StatusPillProps {
  status: SessionStatus;
  actionType?: string;
}

export function sessionPhase(
  status: SessionStatus,
  actionType?: string,
): SessionPhase {
  if (status === "closed") {
    return "closed";
  }
  if (actionType === "root_cause") {
    return "root_cause";
  }
  if (actionType === "escalate") {
    return "escalated";
  }
  return "active";
}

const PHASE: Record<
  SessionPhase,
  { label: string; dot: string }
> = {
  active: { label: "ACTIVE", dot: "bg-hud-text" },
  root_cause: { label: "ROOT CAUSE FOUND", dot: "bg-hud-confirmed" },
  escalated: { label: "ESCALATED", dot: "bg-hud-escalated" },
  closed: { label: "CLOSED", dot: "bg-hud-faint" },
};

export function StatusPill({ status, actionType }: StatusPillProps) {
  const phase = sessionPhase(status, actionType);
  const meta = PHASE[phase];
  return (
    <span className="inline-flex items-center gap-2 rounded-[4px] border border-white/10 px-2.5 py-1 font-mono text-12 uppercase tracking-label text-hud-muted">
      <span className={`h-1.5 w-1.5 rounded-full ${meta.dot}`} aria-hidden />
      {meta.label}
    </span>
  );
}
