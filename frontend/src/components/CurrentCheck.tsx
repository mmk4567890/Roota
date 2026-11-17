import { useState, type FormEvent, type KeyboardEvent } from "react";
import { Send } from "lucide-react";
import {
  formatCitationLine,
  fullDocCitation,
  type Check,
  type Evidence,
  type FieldInfo,
  type ParseResult,
  type Source,
} from "../api";
import { enumOptions, fieldLabel, formatUnderstood } from "../labels";
import { CornerTicks } from "./CornerTicks";

interface CurrentCheckProps {
  check: Check;
  checkIndex: number;
  checkTotal: number;
  fields: FieldInfo[];
  evidence: Evidence[] | null;
  disabled: boolean;
  submitting: boolean;
  lastParse: ParseResult | null;
  lastMessage: string | null;
  onChip: (fieldName: string, value: string) => Promise<boolean>;
  onObserve: (text: string) => Promise<boolean>;
}

export function CurrentCheck({
  check,
  checkIndex,
  checkTotal,
  fields,
  evidence,
  disabled,
  submitting,
  lastParse,
  lastMessage,
  onChip,
  onObserve,
}: CurrentCheckProps) {
  const [text, setText] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const [passageOpen, setPassageOpen] = useState(false);

  const primaryFieldName = check.collects[0];
  const primaryField = fields.find((field) => field.name === primaryFieldName);
  const chips = primaryField ? enumOptions(primaryField) : [];
  const source = check.source;
  const cited = evidence?.find((item) => item.kind === "cited") ?? null;

  async function submitChip(value: string): Promise<void> {
    if (disabled || submitting || !primaryFieldName) {
      return;
    }
    setSelected(value);
    const ok = await onChip(primaryFieldName, value);
    if (!ok) {
      setSelected(null);
    }
  }

  async function handleObserve(event: FormEvent): Promise<void> {
    event.preventDefault();
    const trimmed = text.trim();
    if (!trimmed || disabled || submitting) {
      return;
    }
    if (await onObserve(trimmed)) {
      setText("");
      setSelected(null);
    }
  }

  function onChipKey(event: KeyboardEvent<HTMLButtonElement>, value: string) {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      void submitChip(value);
    }
  }

  return (
    <CornerTicks className="bg-transparent px-4 py-5 sm:px-6 sm:py-6">
      <p className="hud-mono-tag">
        [ CHECK {checkIndex} / {checkTotal} ]
      </p>
      <h2 className="mt-3 text-20 font-medium leading-snug text-hud-text">
        {check.instruction}
      </h2>
      <p className="mt-2 text-14 text-hud-muted">{check.reason}</p>

      <div className="mt-6 space-y-3">
        {chips.length > 0 ? (
          <div
            role="group"
            aria-label={
              primaryField
                ? `${primaryField.label} quick answers`
                : "Quick answers"
            }
            className="flex flex-wrap gap-2"
          >
            {chips.map((option) => (
              <button
                key={option.value}
                type="button"
                className={`hud-chip ${
                  selected === option.value ? "hud-chip-selected" : ""
                }`}
                aria-pressed={selected === option.value}
                disabled={disabled || submitting}
                onClick={() => void submitChip(option.value)}
                onKeyDown={(event) => onChipKey(event, option.value)}
              >
                {option.label}
              </button>
            ))}
          </div>
        ) : null}

        <form className="space-y-2" onSubmit={(e) => void handleObserve(e)}>
          <label htmlFor="observation-text" className="block text-14 text-hud-muted">
            Or describe what you see
          </label>
          <div className="flex gap-2">
            <textarea
              id="observation-text"
              name="observation"
              rows={2}
              value={text}
              disabled={disabled || submitting}
              onChange={(event) => setText(event.target.value)}
              className="w-full resize-y rounded-[4px] border border-white/10 bg-transparent px-3 py-2 text-14 text-hud-text placeholder:text-hud-faint disabled:opacity-40"
              placeholder="Free-text observation"
            />
            <button
              type="submit"
              name="submit-observation"
              disabled={disabled || submitting || !text.trim()}
              className="hud-button h-fit shrink-0"
              aria-label="Submit observation"
            >
              <Send className="h-4 w-4" aria-hidden />
              {submitting ? "…" : "Send"}
            </button>
          </div>
        </form>

        <ParserFeedback
          fields={fields}
          lastParse={lastParse}
          lastMessage={lastMessage}
        />
      </div>

      <CitationBlock
        source={source}
        cited={cited}
        open={passageOpen}
        onToggle={() => setPassageOpen((prev) => !prev)}
      />
    </CornerTicks>
  );
}

function ParserFeedback({
  fields,
  lastParse,
  lastMessage,
}: {
  fields: FieldInfo[];
  lastParse: ParseResult | null;
  lastMessage: string | null;
}) {
  if (!lastParse && !lastMessage) {
    return null;
  }
  return (
    <div className="space-y-1 text-14 text-hud-muted" role="status">
      {lastParse ? (
        <>
          <p>
            Understood: {formatUnderstood(fields, lastParse.extracted)}
          </p>
          {lastParse.unclear_fields.length > 0 ? (
            <p>
              Unclear:{" "}
              {lastParse.unclear_fields
                .map((name) => fieldLabel(fields, name))
                .join(", ")}
            </p>
          ) : null}
          {lastParse.rejected.length > 0 ? (
            <p>
              Rejected:{" "}
              {lastParse.rejected
                .map(
                  (item) =>
                    `${fieldLabel(fields, item.field)} (${item.reason})`,
                )
                .join("; ")}
            </p>
          ) : null}
        </>
      ) : null}
      {lastMessage ? <p className="text-hud-text">{lastMessage}</p> : null}
    </div>
  );
}

function CitationBlock({
  source,
  cited,
  open,
  onToggle,
}: {
  source: Source;
  cited: Evidence | null;
  open: boolean;
  onToggle: () => void;
}) {
  return (
    <div className="mt-6 border-t border-white/10 pt-4">
      <p className="text-14 text-hud-muted">
        {formatCitationLine(source, cited?.title)}
      </p>
      <button
        type="button"
        className="mt-2 hud-mono-tag underline-offset-2 hover:text-hud-text hover:underline"
        aria-expanded={open}
        onClick={onToggle}
      >
        {open ? "Hide passage" : "View passage"}
      </button>
      {open ? (
        <div className="mt-3 space-y-2 text-14 text-hud-muted">
          <p className="text-hud-faint">
            {fullDocCitation(source.doc_id, cited?.title)}
          </p>
          {cited?.text ? (
            <blockquote className="whitespace-pre-wrap border-l border-white/16 pl-3 text-hud-text">
              {cited.text}
            </blockquote>
          ) : (
            <p>Passage unavailable.</p>
          )}
        </div>
      ) : null}
    </div>
  );
}
