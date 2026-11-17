import { Undo2, X } from "lucide-react";
import {
  isEventUndone,
  type Event,
  type FieldInfo,
} from "../api";
import { formatFactLabel } from "../labels";

interface SessionLogDrawerProps {
  open: boolean;
  events: Event[];
  fields: FieldInfo[];
  disabled: boolean;
  undoingEventId: number | null;
  onClose: () => void;
  onUndo: (eventId: number) => void;
}

export function SessionLogDrawer({
  open,
  events,
  fields,
  disabled,
  undoingEventId,
  onClose,
  onUndo,
}: SessionLogDrawerProps) {
  if (!open) {
    return null;
  }

  const timeline = [...events].reverse();

  return (
    <div className="no-print fixed inset-0 z-40 flex justify-end">
      <button
        type="button"
        className="absolute inset-0 bg-black/50"
        aria-label="Close session log"
        onClick={onClose}
      />
      <aside
        className="relative z-10 flex h-full w-full max-w-md flex-col border-l border-white/10 bg-hud-surface"
        role="dialog"
        aria-modal="true"
        aria-labelledby="session-log-heading"
      >
        <div className="flex items-center justify-between border-b border-white/10 px-4 py-3">
          <h2 id="session-log-heading" className="hud-mono-tag">
            [ SESSION LOG ]
          </h2>
          <button
            type="button"
            className="hud-button px-2 py-1"
            onClick={onClose}
            aria-label="Close"
          >
            <X className="h-4 w-4" aria-hidden />
          </button>
        </div>
        <ol className="flex-1 space-y-3 overflow-y-auto px-4 py-4">
          {timeline.length === 0 ? (
            <li className="text-14 text-hud-muted">No events yet.</li>
          ) : (
            timeline.map((event) => {
              const undone = isEventUndone(events, event.id);
              return (
                <li
                  key={event.id}
                  className={`border border-white/10 px-3 py-3 text-14 ${
                    undone ? "opacity-50" : ""
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <p className="hud-mono-tag">
                      [ {event.type.replace(/_/g, " ")} ]
                    </p>
                    {event.type !== "undo" && event.type !== "closed" && !undone ? (
                      <button
                        type="button"
                        className="hud-button px-2 py-1 text-12"
                        disabled={disabled || undoingEventId === event.id}
                        onClick={() => onUndo(event.id)}
                      >
                        <Undo2 className="h-3.5 w-3.5" aria-hidden />
                        {undoingEventId === event.id ? "Undoing…" : "Undo"}
                      </button>
                    ) : null}
                  </div>
                  <EventBody event={event} fields={fields} />
                  {undone ? (
                    <p className="mt-1 text-12 text-hud-faint">Undone</p>
                  ) : null}
                </li>
              );
            })
          )}
        </ol>
      </aside>
    </div>
  );
}

function EventBody({
  event,
  fields,
}: {
  event: Event;
  fields: FieldInfo[];
}) {
  if (event.type === "observation") {
    const text = event.payload["text"];
    const extracted = (event.payload["extracted"] ?? {}) as Record<
      string,
      unknown
    >;
    const facts = Object.entries(extracted)
      .map(([name, value]) => formatFactLabel(fields, name, value))
      .join("; ");
    return (
      <div className="mt-2 space-y-1 text-hud-muted">
        {typeof text === "string" ? (
          <p className="text-hud-text">“{text}”</p>
        ) : null}
        {facts ? <p>{facts}</p> : null}
      </div>
    );
  }
  if (event.type === "facts_reported") {
    const facts = (event.payload["facts"] ?? {}) as Record<string, unknown>;
    return (
      <p className="mt-2 text-hud-muted">
        {Object.entries(facts)
          .map(([name, value]) => formatFactLabel(fields, name, value))
          .join("; ")}
      </p>
    );
  }
  if (event.type === "undo") {
    return (
      <p className="mt-2 text-hud-muted">
        Undid event #{String(event.payload["target_event_id"] ?? "?")}
      </p>
    );
  }
  if (event.type === "closed") {
    return <p className="mt-2 text-hud-muted">Session closed</p>;
  }
  return null;
}
