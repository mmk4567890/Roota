/**
 * Typed Roota API client. Paths are prefixed with `/api` and proxied to the
 * backend in Vite dev (see vite.config.ts). Types mirror backend Pydantic models.
 */

const API_BASE = "/api";

// --- Types mirroring backend models ---

export type FieldType = "enum" | "number" | "boolean";

export interface FieldInfo {
  name: string;
  type: FieldType;
  values: string[] | null;
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
}

export interface Source {
  doc_id: string;
  section: string;
  page: number | null;
  _todo?: string | null;
}

export interface Check {
  id: string;
  instruction: string;
  reason: string;
  collects: string[];
  source: Source;
  _todo?: string | null;
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
  | "open";

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

/** True when an undo event in the log targets this event id. */
export function isEventUndone(events: Event[], eventId: number): boolean {
  return events.some(
    (event) =>
      event.type === "undo" &&
      Number(event.payload["target_event_id"]) === eventId,
  );
}

/** Format a citation the way the session UI shows it. */
export function formatSource(source: Source): string {
  const page =
    source.page != null && source.page !== undefined
      ? `, p.${source.page}`
      : "";
  return `${source.doc_id}, §${source.section}${page}`;
}
