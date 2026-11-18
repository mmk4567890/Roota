import { ScrollText } from "lucide-react";
import type { FaultInfo, SessionStatus } from "../api";
import { StatusPill } from "./StatusPill";

interface TopBarProps {
  fault?: FaultInfo | null;
  equipmentLabel?: string | null;
  status?: SessionStatus;
  actionType?: string;
  onOpenLog?: () => void;
  showLog?: boolean;
}

export function TopBar({
  fault = null,
  equipmentLabel = null,
  status = "active",
  actionType,
  onOpenLog,
  showLog = false,
}: TopBarProps) {
  return (
    <header className="no-print border-b border-white/10">
      <div className="mx-auto flex max-w-content items-center justify-between gap-4 px-4 py-4 sm:px-6">
        <h1 className="hud-display text-20 sm:text-32">ROOTA</h1>
        {fault ? (
          <div className="flex flex-wrap items-center justify-end gap-3">
            <div className="text-right">
              <p className="text-14 text-hud-text">{fault.display_name}</p>
              {equipmentLabel ? (
                <p className="text-12 text-hud-muted">{equipmentLabel}</p>
              ) : null}
              <p className="font-mono text-12 uppercase tracking-label text-hud-muted">
                {fault.fault_codes.join(" · ")}
              </p>
            </div>
            <StatusPill status={status} actionType={actionType} />
            {showLog && onOpenLog ? (
              <button type="button" className="hud-button" onClick={onOpenLog}>
                <ScrollText className="h-4 w-4" aria-hidden />
                Session log
              </button>
            ) : null}
          </div>
        ) : null}
      </div>
    </header>
  );
}
