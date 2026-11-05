import { useEffect, useState, type FormEvent } from "react";
import {
  ApiError,
  createSession,
  listFaults,
  reportObservation,
  type FaultInfo,
  type ObservationResponse,
  type SessionView,
} from "../api";
import { ErrorBanner } from "./ErrorBanner";

interface StartScreenProps {
  onStarted: (
    session: SessionView,
    fault: FaultInfo,
    initial: { observation: ObservationResponse | null; error: string | null },
  ) => void;
}

export function StartScreen({ onStarted }: StartScreenProps) {
  const [faults, setFaults] = useState<FaultInfo[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [faultId, setFaultId] = useState("");
  const [equipmentLabel, setEquipmentLabel] = useState("");
  const [initialNotes, setInitialNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const list = await listFaults();
        if (cancelled) {
          return;
        }
        setFaults(list);
        if (list.length === 1) {
          setFaultId(list[0].fault_id);
        }
      } catch (error) {
        if (cancelled) {
          return;
        }
        setLoadError(
          error instanceof ApiError
            ? error.message
            : error instanceof Error
              ? error.message
              : "Failed to load faults",
        );
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (submitting) {
      return;
    }
    const selected = faults?.find((item) => item.fault_id === faultId);
    if (!selected || !equipmentLabel.trim()) {
      return;
    }
    setSubmitting(true);
    setSubmitError(null);
    let session: SessionView;
    try {
      session = await createSession({
        fault_id: selected.fault_id,
        equipment_label: equipmentLabel.trim(),
      });
    } catch (error) {
      setSubmitError(errorText(error, "Failed to start session"));
      setSubmitting(false);
      return;
    }
    // The session exists from here on. If the initial notes fail, still enter
    // it and show the error there: staying here would make "Start" create a
    // second session and orphan this one.
    const notes = initialNotes.trim();
    let observation: ObservationResponse | null = null;
    let notesError: string | null = null;
    if (notes) {
      try {
        observation = await reportObservation(session.id, { text: notes });
      } catch (error) {
        notesError = `Session started, but the initial notes were not recorded: ${errorText(error, "request failed")}`;
      }
    }
    setSubmitting(false);
    onStarted(observation ?? session, selected, { observation, error: notesError });
  }

  if (loadError) {
    return <ErrorBanner message={loadError} />;
  }

  if (faults === null) {
    return (
      <p className="text-sm text-ink-500" role="status">
        Loading faults…
      </p>
    );
  }

  if (faults.length === 0) {
    return (
      <ErrorBanner message="No fault graphs are loaded on the server." />
    );
  }

  const selected = faults.find((item) => item.fault_id === faultId);

  return (
    <section
      aria-labelledby="start-heading"
      className="mx-auto max-w-xl rounded-md border border-ink-200 bg-white px-4 py-6 sm:px-6"
    >
      <h2 id="start-heading" className="text-lg font-semibold text-ink-900">
        Start a diagnostic session
      </h2>
      <p className="mt-1 text-sm text-ink-500">
        Choose the fault, name the equipment, and optionally add notes from the
        keypad or first look.
      </p>

      {submitError ? (
        <div className="mt-4">
          <ErrorBanner
            message={submitError}
            onDismiss={() => setSubmitError(null)}
          />
        </div>
      ) : null}

      <form className="mt-5 space-y-4" onSubmit={(e) => void handleSubmit(e)}>
        <div>
          <label htmlFor="fault-id" className="block text-sm font-medium text-ink-800">
            Fault
          </label>
          <select
            id="fault-id"
            name="fault_id"
            required
            value={faultId}
            disabled={submitting}
            onChange={(event) => setFaultId(event.target.value)}
            className="mt-1 w-full rounded border border-ink-300 px-3 py-2 text-sm"
          >
            <option value="">— select a fault —</option>
            {faults.map((fault) => (
              <option key={fault.fault_id} value={fault.fault_id}>
                {fault.display_name} ({fault.fault_codes.join(", ")})
              </option>
            ))}
          </select>
          {selected ? (
            <p className="mt-1 text-xs text-ink-500">{selected.description}</p>
          ) : null}
        </div>

        <div>
          <label
            htmlFor="equipment-label"
            className="block text-sm font-medium text-ink-800"
          >
            Equipment label
          </label>
          <input
            id="equipment-label"
            name="equipment_label"
            type="text"
            required
            value={equipmentLabel}
            disabled={submitting}
            onChange={(event) => setEquipmentLabel(event.target.value)}
            className="mt-1 w-full rounded border border-ink-300 px-3 py-2 text-sm"
            placeholder="e.g. Line 3 conveyor drive"
          />
        </div>

        <div>
          <label
            htmlFor="initial-notes"
            className="block text-sm font-medium text-ink-800"
          >
            Initial notes (optional)
          </label>
          <textarea
            id="initial-notes"
            name="initial_notes"
            rows={3}
            value={initialNotes}
            disabled={submitting}
            onChange={(event) => setInitialNotes(event.target.value)}
            className="mt-1 w-full rounded border border-ink-300 px-3 py-2 text-sm"
            placeholder="Sent as the first observation after the session starts"
          />
        </div>

        <button
          type="submit"
          name="start-session"
          disabled={submitting || !faultId || !equipmentLabel.trim()}
          className="w-full rounded bg-accent px-3 py-2.5 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-50 sm:w-auto"
        >
          {submitting ? "Starting…" : "Start session"}
        </button>
      </form>
    </section>
  );
}

function errorText(error: unknown, fallback: string): string {
  if (error instanceof ApiError || error instanceof Error) {
    return error.message;
  }
  return fallback;
}
