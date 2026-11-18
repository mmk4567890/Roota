import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import * as api from "../api";
import {
  makeEscalatedSession,
  makeObservationResponse,
  makeSession,
  sampleFault,
} from "../test/fixtures";
import { SessionScreen, UNCLEAR_MOVED_ON_MESSAGE } from "./SessionScreen";

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

describe("SessionScreen", () => {
  it("submits an observation for the current check", async () => {
    const response = makeObservationResponse();
    vi.spyOn(api, "reportObservation").mockResolvedValue(response);
    const props = renderSession();

    fireEvent.change(screen.getByLabelText("Or describe what you see"), {
      target: { value: "Fan is fine" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Submit observation" }));

    await waitFor(() =>
      expect(api.reportObservation).toHaveBeenCalledWith(props.session.id, {
        text: "Fan is fine",
        check_id: "check_fan_operation",
      }),
    );
    expect(props.onSessionChange).toHaveBeenCalledWith(response);
    expect(screen.getByText(/Fan status: Normal/)).toBeInTheDocument();
  });

  it("shows the specific unclear reason from the API, not the generic line", async () => {
    const message =
      "You said the fan is noisy and running fine. " +
      "Marked as not sure — moving to the next check.";
    vi.spyOn(api, "reportObservation").mockResolvedValue(
      makeObservationResponse({
        parse: {
          extracted: {},
          unclear_fields: ["fan_status"],
          rejected: [],
          notes: "You said the fan is noisy and running fine.",
        },
        message,
      }),
    );
    renderSession();

    fireEvent.change(screen.getByLabelText("Or describe what you see"), {
      target: { value: "Fan is noisy, fan is running fine" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Submit observation" }));

    expect(await screen.findByText(message)).toBeInTheDocument();
    expect(screen.queryByText(UNCLEAR_MOVED_ON_MESSAGE)).not.toBeInTheDocument();
  });

  it("shows the outcome as the API's plain sentences", () => {
    renderSession({ session: makeEscalatedSession() });
    expect(screen.getByRole("heading", { name: "Escalated" })).toBeInTheDocument();
    expect(
      screen.getByText(/^None of the four documented causes could be confirmed\./),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Escalate to a senior technician or OEM support."),
    ).toBeInTheDocument();
    expect(
      screen.queryByText("All documented causes for this fault have been ruled out."),
    ).toBeNull();
  });

  it("shows API errors without clearing the text box", async () => {
    vi.spyOn(api, "reportObservation").mockRejectedValue(
      new api.ApiError(502, "down", "Anthropic API call failed"),
    );
    renderSession();
    const box = screen.getByLabelText("Or describe what you see");
    fireEvent.change(box, { target: { value: "Fan stopped" } });
    fireEvent.click(screen.getByRole("button", { name: "Submit observation" }));
    await screen.findByText("Anthropic API call failed");
    expect(box).toHaveValue("Fan stopped");
  });

  it("submits a quick-answer chip as facts", async () => {
    const updated = makeSession({
      state: {
        ...makeSession().state,
        facts: { fan_status: "noisy" },
      },
    });
    vi.spyOn(api, "reportFacts").mockResolvedValue(updated);
    const props = renderSession();

    fireEvent.click(screen.getByRole("button", { name: "Noisy" }));

    await waitFor(() =>
      expect(api.reportFacts).toHaveBeenCalledWith(props.session.id, {
        facts: { fan_status: "noisy" },
        check_id: "check_fan_operation",
      }),
    );
  });

  it("marks Not sure and shows the move-on message", async () => {
    const updated = makeSession({
      state: {
        ...makeSession().state,
        facts: { fan_status: "unclear" },
        checks_completed: ["check_fan_operation"],
        causes: makeSession().state.causes.map((cause) =>
          cause.cause_id === "cooling_fan_failure"
            ? { ...cause, status: "inconclusive" as const, because: ["fan_status"] }
            : cause,
        ),
        next_action: {
          ...makeSession().state.next_action,
          type: "check",
          message: "Check the airflow path.",
          check: {
            id: "check_airflow_path",
            instruction: "Inspect the vents.",
            reason: "Blocked airflow is next.",
            collects: ["airflow_obstruction"],
            source: {
              doc_id: "TBD_MANUAL",
              section: "Airflow",
              page: 13,
              printed_page: 13,
            },
          },
        },
      },
    });
    vi.spyOn(api, "reportFacts").mockResolvedValue(updated);
    const props = renderSession();

    fireEvent.click(screen.getByRole("button", { name: "Not sure" }));

    await waitFor(() =>
      expect(api.reportFacts).toHaveBeenCalledWith(props.session.id, {
        facts: { fan_status: "unclear" },
        check_id: "check_fan_operation",
      }),
    );
    expect(props.onSessionChange).toHaveBeenCalledWith(updated);
    expect(screen.getByText(UNCLEAR_MOVED_ON_MESSAGE)).toBeInTheDocument();
    expect(screen.getByText(/Fan status: Not sure/)).toBeInTheDocument();
  });

  it("opens the session log drawer", () => {
    const sessionId = makeSession().id;
    renderSession({
      session: makeSession({
        events: [
          {
            id: 1,
            session_id: sessionId,
            seq: 1,
            type: "facts_reported",
            created_at: "2026-01-01T12:01:00Z",
            payload: {
              facts: { fan_status: "normal" },
              check_id: "check_fan_operation",
            },
          },
        ],
      }),
    });
    fireEvent.click(screen.getByRole("button", { name: "Session log" }));
    expect(screen.getByRole("dialog", { name: /session log/i })).toBeInTheDocument();
    expect(screen.getByText("Fan status: Normal")).toBeInTheDocument();
  });

  it("undoes a log event from the drawer", async () => {
    const sessionId = makeSession().id;
    const session = makeSession({
      events: [
        {
          id: 7,
          session_id: sessionId,
          seq: 1,
          type: "facts_reported",
          created_at: "2026-01-01T12:01:00Z",
          payload: {
            facts: { fan_status: "noisy" },
            check_id: "check_fan_operation",
          },
        },
      ],
    });
    const undone = makeSession({ events: session.events });
    vi.spyOn(api, "undoEvent").mockResolvedValue(undone);
    const props = renderSession({ session });

    fireEvent.click(screen.getByRole("button", { name: "Session log" }));
    fireEvent.click(screen.getByRole("button", { name: "Undo" }));

    await waitFor(() =>
      expect(api.undoEvent).toHaveBeenCalledWith(session.id, { event_id: 7 }),
    );
    expect(props.onSessionChange).toHaveBeenCalledWith(undone);
  });
});
