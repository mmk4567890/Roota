import type {
  CauseStatus,
  FaultInfo,
  NextAction,
  ObservationResponse,
  SessionSummary,
  SessionView,
} from "../api";

export const sampleFault: FaultInfo = {
  fault_id: "overtemperature",
  display_name: "Drive / heatsink overtemperature",
  fault_codes: ["OH", "OT", "OH1"],
  description: "Generic overtemperature fault.",
  check_count: 5,
  fields: [
    {
      name: "fan_status",
      label: "Fan status",
      type: "enum",
      values: ["normal", "not_running", "noisy", "unclear"],
      value_labels: {
        normal: "Normal",
        not_running: "Not running",
        noisy: "Noisy",
        unclear: "Not sure",
      },
      unit: null,
      description: "Fan status",
      ask: "What is the cooling fan doing?",
    },
    {
      name: "load_percent",
      label: "Load",
      type: "number",
      values: null,
      value_labels: null,
      unit: "%",
      description: "Load",
      ask: "What is the drive load?",
    },
  ],
};

export function makeAction(
  overrides: Partial<NextAction> & Pick<NextAction, "type" | "message">,
): NextAction {
  return {
    check: null,
    cause_id: null,
    fields: null,
    source: null,
    evidence: null,
    evidence_status: null,
    evidence_error: null,
    ...overrides,
  };
}

export function makeCause(
  overrides: Partial<CauseStatus> &
    Pick<CauseStatus, "cause_id" | "name" | "status">,
): CauseStatus {
  return {
    because: [],
    promoted: false,
    ...overrides,
  };
}

export function makeSession(
  overrides: Partial<SessionView> = {},
): SessionView {
  return {
    id: "11111111-1111-1111-1111-111111111111",
    fault_id: "overtemperature",
    equipment_label: "Line 3 conveyor drive",
    status: "active",
    created_at: "2026-01-01T12:00:00Z",
    events: [],
    outcome: null,
    state: {
      fault_id: "overtemperature",
      facts: {},
      causes: [
        makeCause({
          cause_id: "cooling_fan_failure",
          name: "Cooling fan failure",
          status: "open",
        }),
        makeCause({
          cause_id: "blocked_airflow",
          name: "Blocked airflow",
          status: "open",
        }),
        makeCause({
          cause_id: "excessive_load",
          name: "Excessive load",
          status: "open",
        }),
        makeCause({
          cause_id: "high_ambient",
          name: "High ambient",
          status: "open",
        }),
      ],
      checks_completed: [],
      next_action: makeAction({
        type: "check",
        message: "Check the fan",
        check: {
          id: "check_fan_operation",
          instruction: "Observe the cooling fan.",
          reason: "Fan failure is common.",
          collects: ["fan_status"],
          source: {
            doc_id: "TBD_MANUAL",
            section: "Cooling",
            page: 12,
            printed_page: 12,
          },
        },
        source: {
          doc_id: "TBD_MANUAL",
          section: "Cooling",
          page: 12,
          printed_page: 12,
        },
      }),
    },
    ...overrides,
  };
}

export function makeObservationResponse(
  overrides: Partial<ObservationResponse> = {},
): ObservationResponse {
  const base = makeSession();
  return {
    ...base,
    parse: {
      extracted: { fan_status: "normal" },
      unclear_fields: [],
      rejected: [],
      notes: "",
    },
    message: null,
    ...overrides,
  };
}

/** A session the engine has escalated, with the API's outcome sentences. */
export function makeEscalatedSession(
  overrides: Partial<SessionView> = {},
): SessionView {
  const base = makeSession();
  return {
    ...base,
    outcome: {
      headline: "Escalated",
      paragraphs: [
        "None of the four documented causes could be confirmed. All four were ruled out by the checks.",
        "Escalate to a senior technician or OEM support.",
      ],
      source: null,
    },
    state: {
      ...base.state,
      causes: base.state.causes.map((cause) => ({
        ...cause,
        status: "ruled_out" as const,
        because: ["fan_status"],
      })),
      next_action: makeAction({
        type: "escalate",
        message: "All documented causes for this fault have been ruled out.",
      }),
    },
    ...overrides,
  };
}

export function makeSummary(
  overrides: Partial<SessionSummary> = {},
): SessionSummary {
  return {
    session_id: "11111111-1111-1111-1111-111111111111",
    fault_id: "overtemperature",
    display_name: "Drive / heatsink overtemperature",
    equipment_label: "Line 3 conveyor drive",
    status: "active",
    started_at: "2026-01-01T12:00:00Z",
    closed_at: null,
    causes: [],
    root_cause: null,
    outcome: {
      headline: "Escalated",
      paragraphs: ["Escalate to a senior technician or OEM support."],
      source: null,
    },
    facts: [],
    citations: [],
    ...overrides,
  };
}
