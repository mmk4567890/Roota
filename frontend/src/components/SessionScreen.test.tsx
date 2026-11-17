import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import * as api from "../api";
import {
  makeObservationResponse,
  makeSession,
  sampleFault,
} from "../test/fixtures";
import { SessionScreen } from "./SessionScreen";

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

  it("opens the session log drawer", () => {
    renderSession();
    fireEvent.click(screen.getByRole("button", { name: "Session log" }));
    expect(screen.getByRole("dialog", { name: /session log/i })).toBeInTheDocument();
  });
});
