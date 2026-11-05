import { useState, type FormEvent } from "react";
import type { FieldInfo } from "../api";

interface FactsFormProps {
  fields: FieldInfo[];
  disabled: boolean;
  submitting: boolean;
  checkId: string | null;
  /** Resolves true when the facts were recorded. */
  onSubmit: (facts: Record<string, unknown>, checkId: string | null) => Promise<boolean>;
}

export function FactsForm({
  fields,
  disabled,
  submitting,
  checkId,
  onSubmit,
}: FactsFormProps) {
  const [values, setValues] = useState<Record<string, string>>({});

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (submitting || disabled) {
      return;
    }
    const facts: Record<string, unknown> = {};
    for (const field of fields) {
      const raw = (values[field.name] ?? "").trim();
      if (!raw) {
        continue;
      }
      facts[field.name] = coerce(field, raw);
    }
    if (Object.keys(facts).length === 0) {
      return;
    }
    // Clear only on success: a rejected value stays on screen to correct.
    if (await onSubmit(facts, checkId)) {
      setValues({});
    }
  }

  function setField(name: string, value: string) {
    setValues((prev) => ({ ...prev, [name]: value }));
  }

  const hasAny = fields.some((field) => (values[field.name] ?? "").trim() !== "");

  return (
    <section
      aria-labelledby="facts-form-heading"
      className="rounded-md border border-ink-200 bg-white px-4 py-4"
    >
      <h2 id="facts-form-heading" className="text-sm font-semibold text-ink-900">
        Enter values directly
      </h2>
      <p className="mt-1 text-xs text-ink-500">
        Fallback when the observation parser misreads a value. Only filled fields
        are submitted.
      </p>
      <form className="mt-3 space-y-3" onSubmit={(e) => void handleSubmit(e)}>
        {fields.map((field) => (
          <div key={field.name}>
            <label
              htmlFor={`fact-${field.name}`}
              className="block text-sm text-ink-700"
            >
              {field.ask}
              {field.unit ? ` (${field.unit})` : ""}
            </label>
            <FieldInput
              field={field}
              value={values[field.name] ?? ""}
              disabled={disabled || submitting}
              onChange={(value) => setField(field.name, value)}
            />
          </div>
        ))}
        <button
          type="submit"
          name="submit-facts"
          disabled={disabled || submitting || !hasAny}
          className="rounded border border-accent bg-accent-muted px-3 py-2 text-sm font-medium text-accent disabled:cursor-not-allowed disabled:opacity-50"
        >
          {submitting ? "Submitting…" : "Submit values"}
        </button>
      </form>
    </section>
  );
}

function FieldInput({
  field,
  value,
  disabled,
  onChange,
}: {
  field: FieldInfo;
  value: string;
  disabled: boolean;
  onChange: (value: string) => void;
}) {
  const id = `fact-${field.name}`;
  const className =
    "mt-1 w-full rounded border border-ink-300 px-3 py-2 text-sm disabled:bg-ink-50";

  if (field.type === "enum") {
    return (
      <select
        id={id}
        name={field.name}
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
        className={className}
      >
        <option value="">— select —</option>
        {(field.values ?? []).map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    );
  }

  if (field.type === "boolean") {
    return (
      <select
        id={id}
        name={field.name}
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
        className={className}
      >
        <option value="">— select —</option>
        <option value="true">true</option>
        <option value="false">false</option>
      </select>
    );
  }

  return (
    <input
      id={id}
      name={field.name}
      type="number"
      step="any"
      value={value}
      disabled={disabled}
      onChange={(event) => onChange(event.target.value)}
      className={className}
    />
  );
}

function coerce(field: FieldInfo, raw: string): unknown {
  if (field.type === "number") {
    return Number(raw);
  }
  if (field.type === "boolean") {
    return raw === "true";
  }
  return raw;
}
