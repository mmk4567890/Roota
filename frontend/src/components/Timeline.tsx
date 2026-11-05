import { isEventUndone, type Event } from "../api";

interface TimelineProps {
  events: Event[];
  disabled: boolean;
  undoingEventId: number | null;
  onUndo: (eventId: number) => void;
}

export function Timeline({
  events,
  disabled,
  undoingEventId,
  onUndo,
}: TimelineProps) {
  const chronological = [...events].sort((a, b) => a.seq - b.seq);

  return (
    <section
      aria-labelledby="timeline-heading"
      className="rounded-md border border-ink-200 bg-white px-4 py-4"
    >
      <h2 id="timeline-heading" className="text-sm font-semibold text-ink-900">
        Timeline
      </h2>
      {chronological.length === 0 ? (
        <p className="mt-2 text-sm text-ink-400">No events yet.</p>
      ) : (
        <ol className="mt-3 space-y-3">
          {chronological.map((event) => {
            const undone = isEventUndone(events, event.id);
            const canUndo =
              !disabled &&
              !undone &&
              event.type !== "undo" &&
              event.type !== "closed";
            return (
              <li
                key={event.id}
                className={`rounded border border-ink-100 px-3 py-2 text-sm ${
                  undone ? "bg-ink-50 text-ink-400 line-through" : "bg-white"
                }`}
              >
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    <p className="font-medium text-ink-900">
                      #{event.seq} · {labelFor(event.type)}
                      {undone ? " (undone)" : ""}
                    </p>
                    <p className="mt-0.5 break-words text-xs text-ink-500">
                      {summarize(event)}
                    </p>
                    <p className="mt-0.5 text-xs text-ink-400">
                      {new Date(event.created_at).toLocaleString()}
                    </p>
                  </div>
                  {canUndo ? (
                    <button
                      type="button"
                      className="rounded border border-ink-300 px-2 py-1 text-xs font-medium text-ink-700 disabled:cursor-not-allowed disabled:opacity-50"
                      disabled={undoingEventId !== null}
                      onClick={() => onUndo(event.id)}
                    >
                      {undoingEventId === event.id ? "Undoing…" : "Undo"}
                    </button>
                  ) : null}
                </div>
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}

function labelFor(type: Event["type"]): string {
  switch (type) {
    case "facts_reported":
      return "Facts reported";
    case "observation":
      return "Observation";
    case "undo":
      return "Undo";
    case "closed":
      return "Session closed";
  }
}

function summarize(event: Event): string {
  const payload = event.payload;
  if (event.type === "observation") {
    const text = payload["text"];
    return typeof text === "string" ? text : JSON.stringify(payload);
  }
  if (event.type === "facts_reported") {
    const facts = payload["facts"];
    if (facts && typeof facts === "object") {
      return Object.entries(facts as Record<string, unknown>)
        .map(([key, value]) => `${key} = ${String(value)}`)
        .join(", ");
    }
  }
  if (event.type === "undo") {
    return `Undid event ${String(payload["target_event_id"])}`;
  }
  return "";
}
