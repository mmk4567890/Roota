import type {
  CauseStatus,
  FaultInfo,
  NextAction,
  ObservationResponse,
  SessionView,
} from "../api";

export const sampleFault: FaultInfo = {
  fault_id: "overtemperature",
  display_name: "Drive / heatsink overtemperature",
  fault_codes: ["OH", "OT", "OH1"],
  description: "Generic overtemperature fault.",
  fields: [
    {
      name: "fan_status",
      type: "enum",
      values: ["normal", "not_running", "noisy", "unclear"],
      unit: null,
      description: "Fan status",
      ask: "What is the cooling fan doing?",
    },
    {
      name: "load_percent",
      type: "number",
      values: null,
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
    state: {
      fault_id: "overtemperature",
      facts: {},
      causes: [
        makeCause({
          cause_id: "cooling_fan_failure",
          name: "Cooling fan failure",
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
          },
        },
        source: {
          doc_id: "TBD_MANUAL",
          section: "Cooling",
          page: 12,
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
