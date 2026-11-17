/**
 * Typed Roota API client. Paths are prefixed with `/api` and proxied to the
 * backend in Vite dev (see vite.config.ts). Types mirror backend Pydantic models.
 */

const API_BASE = "/api";

// --- Types mirroring backend models ---

export type FieldType = "enum" | "number" | "boolean";

export interface FieldInfo {
  name: string;
  label: string;
  type: FieldType;
  values: string[] | null;
  value_labels: Record<string, string> | null;
  unit: string | null;
  description: string;
  ask: string;
}

export interface FaultInfo {
  fault_id: string;
  display_name: string;
  fault_codes: string[];
  description: string;
  fields: FieldInfo[];
  check_count: number;
}

export interface Source {
  doc_id: string;
  section: string;
  /** PDF page used for evidence retrieval. */
  page: number | null;
  /** Printed page for UI / report when it differs from the PDF page. */
  printed_page?: number | null;
}

export interface Check {
  id: string;
  instruction: string;
  reason: string;
  collects: string[];
  source: Source;
}

export interface Evidence {
  doc_id: string;
  title: string;
  page: number;
  section: string;
  text: string;
  kind: "cited" | "related";
}

export type NextActionType = "check" | "need_info" | "root_cause" | "escalate";

export type EvidenceStatus = "attached" | "no_manual" | "unavailable";

export interface NextAction {
  type: NextActionType;
  message: string;
  check: Check | null;
  cause_id: string | null;
  fields: string[] | null;
  source: Source | null;
  evidence: Evidence[] | null;
  evidence_status: EvidenceStatus | null;
  evidence_error: string | null;
}

export type CauseStatusKind =
  | "confirmed"
  | "ruled_out"
  | "contradiction"
  | "open"
  | "inconclusive";

export interface CauseStatus {
  cause_id: string;
  name: string;
  status: CauseStatusKind;
  because: string[];
  promoted: boolean;
}

export interface DiagnosticState {
  fault_id: string;
  facts: Record<string, unknown>;
  causes: CauseStatus[];
  checks_completed: string[];
  next_action: NextAction;
}

export type EventType = "facts_reported" | "observation" | "undo" | "closed";

export interface Event {
  id: number;
  session_id: string;
  seq: number;
  type: EventType;
  payload: Record<string, unknown>;
  created_at: string;
}

export type SessionStatus = "active" | "closed";

export interface SessionView {
  id: string;
  fault_id: string;
  equipment_label: string;
  status: SessionStatus;
  created_at: string;
  events: Event[];
  state: DiagnosticState;
}

export interface RejectedValue {
  field: string;
  value: unknown;
  reason: string;
}

export interface ParseResult {
  extracted: Record<string, unknown>;
  unclear_fields: string[];
  rejected: RejectedValue[];
  notes: string;
}

export interface ObservationResponse extends SessionView {
  parse: ParseResult;
  message: string | null;
}

export interface SessionCreate {
  fault_id: string;
  equipment_label: string;
  initial_facts?: Record<string, unknown>;
}

export interface FactsReport {
  facts: Record<string, unknown>;
  check_id?: string | null;
}

export interface ObservationReport {
  text: string;
  check_id?: string | null;
}

export interface UndoRequest {
  event_id: number;
}

export interface FactReport {
  field: string;
  field_label: string;
  value: unknown;
  value_label: string;
  reported_at: string;
  event_id: number;
  how: "form" | "observation";
  text: string | null;
  undone: boolean;
}

export interface RootCauseSummary {
  cause_id: string;
  name: string;
  corrective_action: string;
  source: Source;
}

export interface CitationUsed {
  doc_id: string;
  short_name: string;
  full_title: string;
  section: string;
  section_label: string;
  page: number | null;
  used_for: string;
  passage: string | null;
}

export interface SessionSummary {
  session_id: string;
  fault_id: string;
  display_name: string;
  equipment_label: string;
  status: SessionStatus;
  started_at: string;
  closed_at: string | null;
  causes: CauseStatus[];
  root_cause: RootCauseSummary | null;
  escalation_reason: string | null;
  facts: FactReport[];
  citations: CitationUsed[];
}

/** Error raised for any non-OK API response; message is the backend detail. */
export class ApiError extends Error {
  readonly status: number;
  readonly detail: unknown;

  constructor(status: number, detail: unknown, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

/** Format FastAPI `detail` (string or validation error list) for display. */
export function formatApiDetail(detail: unknown): string {
  if (detail == null) {
    return "Unknown error";
  }
  if (typeof detail === "string") {
    return detail;
  }
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (item && typeof item === "object" && "msg" in item) {
          const loc = Array.isArray((item as { loc?: unknown }).loc)
            ? (item as { loc: unknown[] }).loc.join(".")
            : "";
          const msg = String((item as { msg: unknown }).msg);
          return loc ? `${loc}: ${msg}` : msg;
        }
        return JSON.stringify(item);
      })
      .join("; ");
  }
  if (typeof detail === "object" && detail !== null && "message" in detail) {
    return String((detail as { message: unknown }).message);
  }
  return JSON.stringify(detail);
}

async function request<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      Accept: "application/json",
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...init?.headers,
    },
  });

  let body: unknown = null;
  const text = await response.text();
  if (text) {
    try {
      body = JSON.parse(text) as unknown;
    } catch {
      body = text;
    }
  }

  if (!response.ok) {
    const detail =
      body && typeof body === "object" && body !== null && "detail" in body
        ? (body as { detail: unknown }).detail
        : body;
    throw new ApiError(
      response.status,
      detail,
      formatApiDetail(detail) || `Request failed (${response.status})`,
    );
  }

  return body as T;
}

export function listFaults(): Promise<FaultInfo[]> {
  return request<FaultInfo[]>("/faults");
}

export function createSession(payload: SessionCreate): Promise<SessionView> {
  return request<SessionView>("/sessions", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getSession(sessionId: string): Promise<SessionView> {
  return request<SessionView>(`/sessions/${sessionId}`);
}

export function reportFacts(
  sessionId: string,
  payload: FactsReport,
): Promise<SessionView> {
  return request<SessionView>(`/sessions/${sessionId}/facts`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function reportObservation(
  sessionId: string,
  payload: ObservationReport,
): Promise<ObservationResponse> {
  return request<ObservationResponse>(`/sessions/${sessionId}/observations`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function undoEvent(
  sessionId: string,
  payload: UndoRequest,
): Promise<SessionView> {
  return request<SessionView>(`/sessions/${sessionId}/undo`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function closeSession(sessionId: string): Promise<SessionView> {
  return request<SessionView>(`/sessions/${sessionId}/close`, {
    method: "POST",
  });
}

export function getSessionSummary(sessionId: string): Promise<SessionSummary> {
  return request<SessionSummary>(`/sessions/${sessionId}/summary`);
}

export async function getSessionSummaryMarkdown(
  sessionId: string,
): Promise<string> {
  const response = await fetch(
    `${API_BASE}/sessions/${sessionId}/summary?format=markdown`,
    { headers: { Accept: "text/markdown" } },
  );
  const text = await response.text();
  if (!response.ok) {
    let detail: unknown = text;
    try {
      const parsed = JSON.parse(text) as { detail?: unknown };
      detail = parsed.detail ?? parsed;
    } catch {
      /* keep raw text */
    }
    throw new ApiError(
      response.status,
      detail,
      formatApiDetail(detail) || `Request failed (${response.status})`,
    );
  }
  return text;
}

/** True when an undo event in the log targets this event id. */
export function isEventUndone(events: Event[], eventId: number): boolean {
  return events.some(
    (event) =>
      event.type === "undo" &&
      Number(event.payload["target_event_id"]) === eventId,
  );
}

const DOC_SHORT: Record<string, string> = {
  abb_acs580_fw: "ABB ACS580 firmware manual",
};

const DOC_FULL: Record<string, string> = {
  abb_acs580_fw:
    "ABB ACS580 standard control program firmware manual, 3AXD50000016097 Rev J",
};

export function shortDocName(docId: string, fallbackTitle?: string): string {
  return DOC_SHORT[docId] ?? fallbackTitle ?? docId;
}

export function fullDocCitation(docId: string, fallbackTitle?: string): string {
  return DOC_FULL[docId] ?? fallbackTitle ?? docId;
}

export function sectionShortLabel(section: string): string {
  let text = section.trim();
  for (const prefix of ["Fault tracing: ", "Fault tracing:"]) {
    if (text.startsWith(prefix)) {
      text = text.slice(prefix.length).trim();
      break;
    }
  }
  const printed = text.indexOf(" (printed p.");
  if (printed >= 0) {
    text = text.slice(0, printed).trim();
  } else {
    const plain = text.indexOf(" (p.");
    if (plain >= 0) {
      text = text.slice(0, plain).trim();
    }
  }
  return text;
}

export function displayPage(source: Source): number | null {
  if (source.printed_page != null) {
    return source.printed_page;
  }
  return source.page;
}

/** Compact citation line for the current-check panel. */
export function formatCitationLine(
  source: Source,
  evidenceTitle?: string | null,
): string {
  const page = displayPage(source);
  const pageTag = page != null ? ` · [ P. ${page} ]` : "";
  return `${shortDocName(source.doc_id, evidenceTitle ?? undefined)} · ${sectionShortLabel(source.section)}${pageTag}`;
}

/** @deprecated Prefer formatCitationLine for the HUD. */
export function formatSource(source: Source): string {
  return formatCitationLine(source);
}
