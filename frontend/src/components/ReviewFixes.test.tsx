/**
 * Regression tests for session UI review fixes.
 */
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import * as api from "../api";
import {
  makeCause,
  makeObservationResponse,
  makeSession,
  sampleFault,
} from "../test/fixtures";
import { CauseRail } from "./CauseRail";
import { SessionScreen } from "./SessionScreen";
import { StartScreen } from "./StartScreen";

afterEach(() => {
  vi.restoreAllMocks();
});

function renderSession(
  overrides: Partial<Parameters<typeof SessionScreen>[0]> = {},
) {
  const props = {
    session: makeSession(),
    fault: sampleFault,
    onSessionChange: vi.fn(),
    onClosed: vi.fn(),
    ...overrides,
  };
  render(<SessionScreen {...props} />);
  return props;
}

describe("start screen initial notes", () => {
  it("enters the created session when the initial notes fail, never creating a second one", async () => {
    vi.spyOn(api, "listFaults").mockResolvedValue([sampleFault]);
    const create = vi.spyOn(api, "createSession").mockResolvedValue(makeSession());
    vi.spyOn(api, "reportObservation").mockRejectedValue(
      new api.ApiError(502, "Anthropic API call failed", "Anthropic API call failed"),
    );
    const onStarted = vi.fn();
    render(<StartScreen onStarted={onStarted} />);

    await screen.findByLabelText("Equipment");
    fireEvent.change(screen.getByLabelText("Equipment"), {
      target: { value: "Bay 1" },
    });
    fireEvent.change(screen.getByLabelText("Initial notes (optional)"), {
      target: { value: "Fan is dead" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Start session" }));

    await waitFor(() => expect(onStarted).toHaveBeenCalledTimes(1));
    expect(create).toHaveBeenCalledTimes(1);
    const [session, , initial] = onStarted.mock.calls[0];
    expect(session.id).toBe(makeSession().id);
    expect(initial.observation).toBeNull();
    expect(initial.error).toContain("initial notes were not recorded");
  });

  it("submits initial notes as the first observation and starts with those facts", async () => {
    vi.spyOn(api, "listFaults").mockResolvedValue([sampleFault]);
    vi.spyOn(api, "createSession").mockResolvedValue(makeSession());
    const observed = makeObservationResponse({
      state: {
        ...makeSession().state,
        facts: { fan_status: "normal" },
      },
      parse: {
        extracted: { fan_status: "normal" },
        unclear_fields: [],
        rejected: [],
        notes: "",
      },
    });
    const observe = vi.spyOn(api, "reportObservation").mockResolvedValue(observed);
    const onStarted = vi.fn();
    render(<StartScreen onStarted={onStarted} />);

    await screen.findByLabelText("Equipment");
    fireEvent.change(screen.getByLabelText("Equipment"), {
      target: { value: "Bay 1" },
    });
    fireEvent.change(screen.getByLabelText("Initial notes (optional)"), {
      target: { value: "Fan is fine" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Start session" }));

    await waitFor(() => expect(onStarted).toHaveBeenCalledTimes(1));
    expect(observe).toHaveBeenCalledWith(makeSession().id, {
      text: "Fan is fine",
    });
    const [session, , initial] = onStarted.mock.calls[0];
    expect(session).toBe(observed);
    expect(session.state.facts.fan_status).toBe("normal");
    expect(initial.observation).toBe(observed);
    expect(initial.error).toBeNull();
  });
});

describe("session screen", () => {
  it("shows the initial notes' Understood feedback and error", () => {
    renderSession({
      initialObservation: makeObservationResponse(),
      initialError: "Session started, but the initial notes were not recorded: x",
    });

    expect(screen.getByText(/Fan status: Normal/)).toBeInTheDocument();
    expect(
      screen.getByText("Session started, but the initial notes were not recorded: x"),
    ).toBeInTheDocument();
  });

  it("stays on the closed session after closing", async () => {
    const closed = makeSession({
      status: "closed",
      state: {
        ...makeSession().state,
        next_action: {
          type: "root_cause",
          message: "Replace the fan.",
          check: null,
          cause_id: "cooling_fan_failure",
          fields: null,
          source: {
            doc_id: "TBD_MANUAL",
            section: "Cooling",
            page: 12,
          },
          evidence: null,
          evidence_status: null,
          evidence_error: null,
        },
      },
    });
    vi.spyOn(api, "closeSession").mockResolvedValue(closed);
    const active = makeSession({
      state: {
        ...makeSession().state,
        next_action: {
          type: "root_cause",
          message: "Replace the fan.",
          check: null,
          cause_id: "cooling_fan_failure",
          fields: null,
          source: {
            doc_id: "TBD_MANUAL",
            section: "Cooling",
            page: 12,
          },
          evidence: null,
          evidence_status: null,
          evidence_error: null,
        },
      },
    });
    const props = renderSession({ session: active });

    fireEvent.click(screen.getByRole("button", { name: "Close session" }));

    await waitFor(() => expect(props.onSessionChange).toHaveBeenCalledWith(closed));
    expect(props.onClosed).not.toHaveBeenCalled();
  });

  it("New session on a closed session leaves it", () => {
    const props = renderSession({
      session: makeSession({
        status: "closed",
        state: {
          ...makeSession().state,
          next_action: {
            type: "root_cause",
            message: "Replace the fan.",
            check: null,
            cause_id: "cooling_fan_failure",
            fields: null,
            source: {
              doc_id: "TBD_MANUAL",
              section: "Cooling",
              page: 12,
            },
            evidence: null,
            evidence_status: null,
            evidence_error: null,
          },
        },
      }),
    });

    fireEvent.click(screen.getByRole("button", { name: "New session" }));
    expect(props.onClosed).toHaveBeenCalledTimes(1);
  });
});

describe("cause rail", () => {
  it("shows a one-line reason when a cause is selected", () => {
    render(
      <CauseRail
        fields={sampleFault.fields}
        causes={[
          makeCause({
            cause_id: "excessive_load",
            name: "Excessive load",
            status: "contradiction",
            because: ["load_percent"],
          }),
        ]}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /Excessive load/ }));
    expect(screen.getByText(/Conflicting facts: Load/)).toBeInTheDocument();
  });
});
