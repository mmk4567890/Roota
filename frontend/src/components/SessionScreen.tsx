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
import { CausesPanel } from "./CausesPanel";
import { ErrorBanner } from "./ErrorBanner";
import { EvidencePanel } from "./EvidencePanel";
import { FactsForm } from "./FactsForm";
import { FactsTable } from "./FactsTable";
import { NextActionCard } from "./NextActionCard";
import { ObservationForm } from "./ObservationForm";
import { SummaryPanel } from "./SummaryPanel";
import { Timeline } from "./Timeline";

interface SessionScreenProps {
  session: SessionView;
  fault: FaultInfo;
  onSessionChange: (session: SessionView) => void;
  /** Leave this session for the start screen. */
  onClosed: () => void;
  /** Result of the initial-notes observation sent by the start screen. */
  initialObservation?: ObservationResponse | null;
  /** Error from that observation; the session itself was created. */
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
  const [directEntry, setDirectEntry] = useState(false);
  const [lastParse, setLastParse] = useState<ParseResult | null>(
    initialObservation?.parse ?? null,
  );
  const [lastMessage, setLastMessage] = useState<string | null>(
    initialObservation?.message ?? null,
  );

  const closed = session.status === "closed";
  const anyBusy =
    observationBusy || factsBusy || undoBusyId !== null || closeBusy;
  const action = session.state.next_action;
  const checkId =
    action.type === "check" && action.check ? action.check.id : null;
  const showSummary =
    closed || action.type === "root_cause" || action.type === "escalate";
  const summaryOutcomeKey = `${session.status}:${action.type}:${action.cause_id ?? ""}`;

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

  async function handleFacts(
    facts: Record<string, unknown>,
    submittedCheckId: string | null,
  ): Promise<boolean> {
    setFactsBusy(true);
    setError(null);
    try {
      const updated = await reportFacts(session.id, {
        facts,
        check_id: submittedCheckId,
      });
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
      // Stay on the closed, read-only view so the final state stays visible;
      // "New session" leaves it.
      onSessionChange(updated);
    } catch (err) {
      captureError(err);
    } finally {
      setCloseBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="no-print flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="text-lg font-semibold text-ink-900">
            {fault.display_name}
          </h2>
          <p className="text-sm text-ink-500">
            {session.equipment_label}
            <span className="mx-2 text-ink-300">·</span>
            Codes: {fault.fault_codes.join(", ")}
            <span className="mx-2 text-ink-300">·</span>
            Status: {session.status}
          </p>
        </div>
        {!closed ? (
          <button
            type="button"
            name="close-session"
            disabled={anyBusy}
            onClick={() => void handleClose()}
            className="rounded border border-ink-300 px-3 py-2 text-sm font-medium text-ink-800 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {closeBusy ? "Closing…" : "Close session"}
          </button>
        ) : (
          <button
            type="button"
            name="new-session"
            onClick={onClosed}
            className="rounded bg-accent px-3 py-2 text-sm font-medium text-white"
          >
            New session
          </button>
        )}
      </div>

      {error ? (
        <div className="no-print">
          <ErrorBanner message={error} onDismiss={() => setError(null)} />
        </div>
      ) : null}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="no-print space-y-4">
          <NextActionCard action={action} causes={session.state.causes} />
          <EvidencePanel
            evidence={action.evidence}
            evidenceStatus={action.evidence_status}
            evidenceError={action.evidence_error}
          />
          {!closed ? (
            <>
              <ObservationForm
                disabled={anyBusy && !observationBusy}
                submitting={observationBusy}
                lastParse={lastParse}
                lastMessage={lastMessage}
                onSubmit={handleObservation}
              />
              <div className="rounded-md border border-ink-200 bg-white px-4 py-3">
                <label className="flex items-center gap-2 text-sm text-ink-800">
                  <input
                    type="checkbox"
                    name="direct-entry-toggle"
                    checked={directEntry}
                    disabled={anyBusy}
                    onChange={(event) => setDirectEntry(event.target.checked)}
                  />
                  Enter values directly
                </label>
              </div>
              {directEntry ? (
                <FactsForm
                  fields={fault.fields}
                  disabled={anyBusy && !factsBusy}
                  submitting={factsBusy}
                  checkId={checkId}
                  onSubmit={handleFacts}
                />
              ) : null}
            </>
          ) : null}
        </div>

        <div className="space-y-4">
          <div className="no-print space-y-4">
            <CausesPanel causes={session.state.causes} />
            <FactsTable facts={session.state.facts} />
          </div>
          <SummaryPanel
            sessionId={session.id}
            autoOpen={showSummary}
            outcomeKey={summaryOutcomeKey}
          />
          <div className="no-print">
            <Timeline
              events={session.events}
              disabled={closed || anyBusy}
              undoingEventId={undoBusyId}
              onUndo={(id) => void handleUndo(id)}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
