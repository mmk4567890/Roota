import { useState, type FormEvent } from "react";
import type { ParseResult } from "../api";

interface ObservationFormProps {
  disabled: boolean;
  submitting: boolean;
  lastParse: ParseResult | null;
  lastMessage: string | null;
  /** Resolves true when the observation was recorded. */
  onSubmit: (text: string) => Promise<boolean>;
}

export function ObservationForm({
  disabled,
  submitting,
  lastParse,
  lastMessage,
  onSubmit,
}: ObservationFormProps) {
  const [text, setText] = useState("");

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const trimmed = text.trim();
    if (!trimmed || submitting || disabled) {
      return;
    }
    // Clear only on success: a 422/502 must not throw away what was typed.
    if (await onSubmit(trimmed)) {
      setText("");
    }
  }

  return (
    <section
      aria-labelledby="observation-heading"
      className="rounded-md border border-ink-200 bg-white px-4 py-4"
    >
      <h2 id="observation-heading" className="text-sm font-semibold text-ink-900">
        Observation
      </h2>
      <form className="mt-3 space-y-3" onSubmit={(e) => void handleSubmit(e)}>
        <div>
          <label htmlFor="observation-text" className="block text-sm text-ink-700">
            Report what you observed
          </label>
          <textarea
            id="observation-text"
            name="observation"
            rows={4}
            value={text}
            disabled={disabled || submitting}
            onChange={(event) => setText(event.target.value)}
            className="mt-1 w-full rounded border border-ink-300 px-3 py-2 text-sm text-ink-900 disabled:bg-ink-50"
          />
        </div>
        <button
          type="submit"
          name="submit-observation"
          disabled={disabled || submitting || !text.trim()}
          className="rounded bg-accent px-3 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-50"
        >
          {submitting ? "Submitting…" : "Submit"}
        </button>
      </form>

      {lastParse ? (
        <div className="mt-4 space-y-2 rounded border border-ink-100 bg-ink-50 px-3 py-3 text-sm">
          <p>
            <span className="font-medium">Understood: </span>
            {formatUnderstood(lastParse)}
          </p>
          {lastParse.unclear_fields.length > 0 ? (
            <p>
              <span className="font-medium">Unclear: </span>
              {lastParse.unclear_fields.join(", ")}
            </p>
          ) : (
            <p className="text-ink-500">Nothing unclear.</p>
          )}
          {lastParse.rejected.length > 0 ? (
            <p>
              <span className="font-medium">Rejected: </span>
              {lastParse.rejected
                .map((item) => `${item.field} (${item.reason})`)
                .join("; ")}
            </p>
          ) : null}
          {lastMessage ? (
            <p className="text-amber-900" role="status">
              {lastMessage}
            </p>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

function formatUnderstood(parse: ParseResult): string {
  const entries = Object.entries(parse.extracted);
  if (entries.length === 0) {
    return "(no field values extracted)";
  }
  return entries.map(([field, value]) => `${field} = ${String(value)}`).join(", ");
}
