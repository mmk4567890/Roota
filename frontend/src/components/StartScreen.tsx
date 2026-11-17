import { useEffect, useState, type FormEvent } from "react";
import { Play } from "lucide-react";
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
    // Session exists from here. If initial notes fail, still enter it so Start
    // does not create a second orphaned session.
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
    onStarted(observation ?? session, selected, {
      observation,
      error: notesError,
    });
  }

  if (loadError) {
    return <ErrorBanner message={loadError} />;
  }

  if (faults === null) {
    return (
      <p className="text-14 text-hud-muted" role="status">
        Loading faults…
      </p>
    );
  }

  if (faults.length === 0) {
    return <ErrorBanner message="No fault graphs are loaded on the server." />;
  }

  const selected = faults.find((item) => item.fault_id === faultId);

  return (
    <section
      aria-labelledby="start-heading"
      className="mx-auto max-w-lg border border-white/10 bg-hud-surface/80 px-5 py-8 sm:px-8"
    >
      <h2 id="start-heading" className="hud-display text-20">
        Start session
      </h2>
      <p className="mt-2 text-14 text-hud-muted">
        Choose the problem, name the equipment, and optionally add notes from
        the keypad or first look.
      </p>

      {submitError ? (
        <div className="mt-4">
          <ErrorBanner
            message={submitError}
            onDismiss={() => setSubmitError(null)}
          />
        </div>
      ) : null}

      <form className="mt-6 space-y-5" onSubmit={(e) => void handleSubmit(e)}>
        <div>
          <label htmlFor="fault-id" className="hud-mono-tag">
            Problem
          </label>
          <select
            id="fault-id"
            name="fault_id"
            required
            value={faultId}
            disabled={submitting}
            onChange={(event) => setFaultId(event.target.value)}
            className="mt-2 w-full rounded-[4px] border border-white/10 bg-transparent px-3 py-2 text-14 text-hud-text"
          >
            <option value="">— select —</option>
            {faults.map((fault) => (
              <option key={fault.fault_id} value={fault.fault_id}>
                {problemLabel(fault)}
              </option>
            ))}
          </select>
          {selected ? (
            <p className="mt-2 font-mono text-12 uppercase tracking-label text-hud-muted">
              {selected.fault_codes.join(" · ")}
            </p>
          ) : null}
        </div>

        <div>
          <label htmlFor="equipment-label" className="hud-mono-tag">
            Equipment
          </label>
          <input
            id="equipment-label"
            name="equipment_label"
            type="text"
            required
            value={equipmentLabel}
            disabled={submitting}
            onChange={(event) => setEquipmentLabel(event.target.value)}
            className="mt-2 w-full rounded-[4px] border border-white/10 bg-transparent px-3 py-2 text-14 text-hud-text"
            placeholder="e.g. Line 3 conveyor drive"
          />
        </div>

        <div>
          <label htmlFor="initial-notes" className="hud-mono-tag">
            Initial notes (optional)
          </label>
          <textarea
            id="initial-notes"
            name="initial_notes"
            rows={3}
            value={initialNotes}
            disabled={submitting}
            onChange={(event) => setInitialNotes(event.target.value)}
            className="mt-2 w-full rounded-[4px] border border-white/10 bg-transparent px-3 py-2 text-14 text-hud-text"
            placeholder="Sent as the first observation after the session starts"
          />
        </div>

        <button
          type="submit"
          name="start-session"
          disabled={submitting || !faultId || !equipmentLabel.trim()}
          className="hud-button"
        >
          <Play className="h-4 w-4" aria-hidden />
          {submitting ? "Starting…" : "Start session"}
        </button>
      </form>
    </section>
  );
}

function problemLabel(fault: FaultInfo): string {
  // Problem-first: short readable name with equipment brand when present.
  if (fault.fault_id === "acs580_overtemperature") {
    return "Overtemperature — ABB ACS580";
  }
  return fault.display_name;
}

function errorText(error: unknown, fallback: string): string {
  if (error instanceof ApiError || error instanceof Error) {
    return error.message;
  }
  return fallback;
}
