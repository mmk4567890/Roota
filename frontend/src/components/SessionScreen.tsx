import { useState } from "react";
import {
  ApiError,
  closeSession,
  reportFacts,
  reportObservation,
  undoEvent,
  type FaultInfo,
  type ObservationResponse,
  type ParseResult,
  type SessionView,
} from "../api";
import { CauseRail } from "./CauseRail";
import { CurrentCheck } from "./CurrentCheck";
import { ErrorBanner } from "./ErrorBanner";
import { OutcomeView } from "./OutcomeView";
import { ReportView } from "./ReportView";
import { SessionLogDrawer } from "./SessionLogDrawer";
import { TopBar } from "./TopBar";

interface SessionScreenProps {
  session: SessionView;
  fault: FaultInfo;
  onSessionChange: (session: SessionView) => void;
  onClosed: () => void;
  initialObservation?: ObservationResponse | null;
  initialError?: string | null;
}

export function SessionScreen({
  session,
  fault,
  onSessionChange,
  onClosed,
  initialObservation = null,
  initialError = null,
}: SessionScreenProps) {
  const [error, setError] = useState<string | null>(initialError);
  const [observationBusy, setObservationBusy] = useState(false);
  const [factsBusy, setFactsBusy] = useState(false);
  const [undoBusyId, setUndoBusyId] = useState<number | null>(null);
  const [closeBusy, setCloseBusy] = useState(false);
  const [lastParse, setLastParse] = useState<ParseResult | null>(
    initialObservation?.parse ?? null,
  );
  const [lastMessage, setLastMessage] = useState<string | null>(
    initialObservation?.message ?? null,
  );
  const [logOpen, setLogOpen] = useState(false);
  const [reportOpen, setReportOpen] = useState(false);

  const closed = session.status === "closed";
  const anyBusy =
    observationBusy || factsBusy || undoBusyId !== null || closeBusy;
  const action = session.state.next_action;
  const checkId =
    action.type === "check" && action.check ? action.check.id : null;
  const isOutcome =
    action.type === "root_cause" || action.type === "escalate" || closed;
  const canViewReport = isOutcome;

  const checkTotal = Math.max(fault.check_count, 1);
  const onActiveCheck = Boolean(checkId) || action.type === "need_info";
  const checkIndex =
    Math.min(
      session.state.checks_completed.length + (onActiveCheck ? 1 : 0),
      checkTotal,
    ) || 1;

  function captureError(err: unknown): void {
    setError(
      err instanceof ApiError
        ? err.message
        : err instanceof Error
          ? err.message
          : "Request failed",
    );
  }

  async function handleObservation(text: string): Promise<boolean> {
    setObservationBusy(true);
    setError(null);
    try {
      const response = await reportObservation(session.id, {
        text,
        check_id: checkId,
      });
      setLastParse(response.parse);
      setLastMessage(response.message);
      onSessionChange(response);
      return true;
    } catch (err) {
      captureError(err);
      return false;
    } finally {
      setObservationBusy(false);
    }
  }

  async function handleChip(
    fieldName: string,
    value: string,
  ): Promise<boolean> {
    setFactsBusy(true);
    setError(null);
    try {
      const updated = await reportFacts(session.id, {
        facts: { [fieldName]: value },
        check_id: checkId,
      });
      setLastParse({
        extracted: { [fieldName]: value },
        unclear_fields: value === "unclear" ? [fieldName] : [],
        rejected: [],
        notes: "",
      });
      setLastMessage(null);
      onSessionChange(updated);
      return true;
    } catch (err) {
      captureError(err);
      return false;
    } finally {
      setFactsBusy(false);
    }
  }

  async function handleUndo(eventId: number): Promise<void> {
    setUndoBusyId(eventId);
    setError(null);
    try {
      const updated = await undoEvent(session.id, { event_id: eventId });
      onSessionChange(updated);
    } catch (err) {
      captureError(err);
    } finally {
      setUndoBusyId(null);
    }
  }

  async function handleClose(): Promise<void> {
    if (closeBusy || closed) {
      return;
    }
    setCloseBusy(true);
    setError(null);
    try {
      const updated = await closeSession(session.id);
      onSessionChange(updated);
    } catch (err) {
      captureError(err);
    } finally {
      setCloseBusy(false);
    }
  }

  const showCheck =
    !closed && (action.type === "check" || action.type === "need_info");

  return (
    <>
      <TopBar
        fault={fault}
        equipmentLabel={session.equipment_label}
        status={session.status}
        actionType={action.type}
        showLog
        onOpenLog={() => setLogOpen(true)}
      />

      {error ? (
        <div className="no-print mx-auto max-w-content px-4 pt-4 sm:px-6">
          <ErrorBanner message={error} onDismiss={() => setError(null)} />
        </div>
      ) : null}

      <div className="mx-auto grid max-w-content gap-6 px-4 py-6 sm:px-6 min-[900px]:grid-cols-[220px_minmax(0,1fr)]">
        <aside className="order-2 min-[900px]:order-1 min-[900px]:pt-2">
          <CauseRail
            causes={session.state.causes}
            fields={fault.fields}
            outcomeMode={isOutcome}
          />
        </aside>

        <div className="order-1 min-w-0 min-[900px]:order-2">
          {showCheck && action.type === "check" && action.check ? (
            <CurrentCheck
              check={action.check}
              checkIndex={Math.max(checkIndex, 1)}
              checkTotal={checkTotal}
              fields={fault.fields}
              evidence={action.evidence}
              disabled={anyBusy && !observationBusy && !factsBusy}
              submitting={observationBusy || factsBusy}
              lastParse={lastParse}
              lastMessage={lastMessage}
              onChip={handleChip}
              onObserve={handleObservation}
            />
          ) : null}

          {showCheck && action.type === "need_info" ? (
            <CurrentCheck
              check={{
                id: action.check?.id ?? "need_info",
                instruction: action.message,
                reason: "Clarify the last report before continuing.",
                collects: action.fields ?? action.check?.collects ?? [],
                source:
                  action.source ??
                  action.check?.source ?? {
                    doc_id: "TBD_MANUAL",
                    section: "—",
                    page: null,
                  },
              }}
              checkIndex={Math.max(checkIndex, 1)}
              checkTotal={checkTotal}
              fields={fault.fields}
              evidence={action.evidence}
              disabled={anyBusy && !observationBusy && !factsBusy}
              submitting={observationBusy || factsBusy}
              lastParse={lastParse}
              lastMessage={lastMessage}
              onChip={handleChip}
              onObserve={handleObservation}
            />
          ) : null}

          {isOutcome &&
          (action.type === "root_cause" || action.type === "escalate") ? (
            <OutcomeView
              action={action}
              causes={session.state.causes}
              onViewReport={() => {
                if (canViewReport) {
                  setReportOpen(true);
                }
              }}
              onCloseSession={() => void handleClose()}
              closeBusy={closeBusy}
              closed={closed}
            />
          ) : null}

          {closed &&
          action.type !== "root_cause" &&
          action.type !== "escalate" ? (
            <OutcomeView
              action={{
                ...action,
                type: "escalate",
                message: "Session closed.",
              }}
              causes={session.state.causes}
              onViewReport={() => setReportOpen(true)}
              onCloseSession={() => undefined}
              closeBusy={false}
              closed
            />
          ) : null}

          {closed ? (
            <div className="no-print mt-4">
              <button type="button" className="hud-button" onClick={onClosed}>
                New session
              </button>
            </div>
          ) : null}
        </div>
      </div>

      <SessionLogDrawer
        open={logOpen}
        events={session.events}
        fields={fault.fields}
        disabled={closed || anyBusy}
        undoingEventId={undoBusyId}
        onClose={() => setLogOpen(false)}
        onUndo={(id) => void handleUndo(id)}
      />

      {reportOpen && canViewReport ? (
        <ReportView
          sessionId={session.id}
          onClose={() => setReportOpen(false)}
        />
      ) : null}
    </>
  );
}
