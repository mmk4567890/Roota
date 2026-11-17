import type { FieldInfo } from "./api";

/** Look up a field by graph name. */
export function findField(
  fields: FieldInfo[],
  name: string,
): FieldInfo | undefined {
  return fields.find((field) => field.name === name);
}

export function fieldLabel(fields: FieldInfo[], name: string): string {
  return findField(fields, name)?.label ?? name;
}

export function valueLabel(
  fields: FieldInfo[],
  name: string,
  value: unknown,
): string {
  const field = findField(fields, name);
  if (!field) {
    return String(value);
  }
  if (field.value_labels && typeof value === "string") {
    return field.value_labels[value] ?? String(value);
  }
  if (field.type === "boolean" && typeof value === "boolean") {
    return value ? "Yes" : "No";
  }
  return String(value);
}

/** ``Fan status: Noisy`` — never raw ids. */
export function formatFactLabel(
  fields: FieldInfo[],
  name: string,
  value: unknown,
): string {
  return `${fieldLabel(fields, name)}: ${valueLabel(fields, name, value)}`;
}

export function formatUnderstood(
  fields: FieldInfo[],
  extracted: Record<string, unknown>,
): string {
  const entries = Object.entries(extracted);
  if (entries.length === 0) {
    return "Nothing extracted yet.";
  }
  return entries
    .map(([name, value]) => formatFactLabel(fields, name, value))
    .join("; ");
}

export function enumOptions(field: FieldInfo): { value: string; label: string }[] {
  if (field.type !== "enum" || !field.values) {
    return [];
  }
  return field.values.map((value) => ({
    value,
    label: field.value_labels?.[value] ?? value,
  }));
}

export function causeStatusLabel(status: string): string {
  switch (status) {
    case "confirmed":
      return "Confirmed";
    case "ruled_out":
      return "Ruled out";
    case "inconclusive":
      return "Inconclusive";
    case "contradiction":
      return "Contradiction";
    case "open":
      return "Open";
    default:
      return status.replace(/_/g, " ");
  }
}

/** Open causes with no completed checks show as Not checked in the outcome rail. */
export function railStatusLabel(
  status: string,
  notChecked: boolean,
): string {
  if (notChecked && (status === "open" || status === "inconclusive")) {
    return "Not checked";
  }
  return causeStatusLabel(status);
}
