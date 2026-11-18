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

/** Shown after a "Not sure" / unclear chip when the session moves on. */
export const UNCLEAR_MOVED_ON_MESSAGE =
  "Marked as not sure. Moving to the next check.";

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
        // Unclear is an answer, not a re-ask — the move-on message covers it.
        unclear_fields: [],
        rejected: [],
        notes: "",
      });
      setLastMessage(
        value === "unclear" ? UNCLEAR_MOVED_ON_MESSAGE : null,
      );
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

      <div
        className={`mx-auto grid max-w-content gap-6 px-4 py-6 sm:px-6 min-[900px]:grid-cols-[220px_minmax(0,1fr)]${
          reportOpen ? " no-print" : ""
        }`}
      >
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

          {isOutcome ? (
            <OutcomeView
              kind={
                action.type === "root_cause" || action.type === "escalate"
                  ? action.type
                  : "closed"
              }
              paragraphs={
                session.outcome ?? ["Session closed without a diagnosis."]
              }
              onViewReport={() => setReportOpen(true)}
              onCloseSession={() => void handleClose()}
              closeBusy={closeBusy}
              closed={closed}
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

      {reportOpen && isOutcome ? (
        <ReportView
          sessionId={session.id}
          onClose={() => setReportOpen(false)}
        />
      ) : null}
    </>
  );
}
