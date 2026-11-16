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
import { CausesPanel } from "./CausesPanel";
import { EvidencePanel } from "./EvidencePanel";
import { SessionScreen } from "./SessionScreen";
import { StartScreen } from "./StartScreen";

afterEach(() => {
  vi.restoreAllMocks();
});

function renderSession(overrides: Partial<Parameters<typeof SessionScreen>[0]> = {}) {
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

describe("evidence passages", () => {
  it("renders every chunk of a cited page, without duplicate keys", () => {
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => {});
    const chunk = {
      doc_id: "abb_acs580_fw",
      title: "ACS580 firmware manual",
      page: 555,
      section: "",
      kind: "cited" as const,
    };

    render(
      <EvidencePanel
        evidence={[
          { ...chunk, text: "Check air flow and fan operation." },
          { ...chunk, text: "Check heatsink fins for dust pick-up." },
        ]}
        evidenceStatus="attached"
        evidenceError={null}
      />,
    );

    // The most relevant chunk (first, as ordered by the API) is open; the rest
    // of the page is folded so other faults' entries don't lead.
    expect(screen.getByText("Check air flow and fan operation.")).toBeInTheDocument();
    expect(screen.queryByText("Check heatsink fins for dust pick-up.")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Show more from this page (1)" }));
    expect(screen.getByText("Check heatsink fins for dust pick-up.")).toBeInTheDocument();
    // An empty section is not shown as a bare "§".
    expect(screen.queryByText(/§/)).toBeNull();
    const keyWarnings = consoleError.mock.calls.filter((call) =>
      String(call[0]).includes("same key"),
    );
    expect(keyWarnings).toEqual([]);
  });
});

describe("typed input survives a failed request", () => {
  it("keeps the observation text after a 502", async () => {
    vi.spyOn(api, "reportObservation").mockRejectedValue(
      new api.ApiError(502, "Anthropic API call failed", "Anthropic API call failed"),
    );
    renderSession();
    const box = screen.getByLabelText("Report what you observed");

    fireEvent.change(box, { target: { value: "Fan stopped, vents dusty" } });
    fireEvent.click(screen.getByRole("button", { name: "Submit" }));

    await screen.findByText("Anthropic API call failed");
    expect(box).toHaveValue("Fan stopped, vents dusty");
  });

  it("clears the observation text after success", async () => {
    vi.spyOn(api, "reportObservation").mockResolvedValue(makeObservationResponse());
    renderSession();
    const box = screen.getByLabelText("Report what you observed");

    fireEvent.change(box, { target: { value: "Fan is fine" } });
    fireEvent.click(screen.getByRole("button", { name: "Submit" }));

    await waitFor(() => expect(box).toHaveValue(""));
  });

  it("keeps direct-entry values after a 422", async () => {
    vi.spyOn(api, "reportFacts").mockRejectedValue(
      new api.ApiError(422, "invalid value", "invalid value for field"),
    );
    renderSession();
    fireEvent.click(screen.getByLabelText("Enter values directly"));
    const field = sampleFault.fields[0];
    const input = screen.getByLabelText(new RegExp(field.ask.replace(/[?()]/g, "\\$&")));
    const value = field.type === "enum" ? (field.values ?? [])[0] : "5";

    fireEvent.change(input, { target: { value } });
    fireEvent.click(screen.getByRole("button", { name: "Submit values" }));

    await screen.findByText("invalid value for field");
    expect(input).toHaveValue(value);
  });
});

describe("start screen", () => {
  it("enters the created session when the initial notes fail, never creating a second one", async () => {
    vi.spyOn(api, "listFaults").mockResolvedValue([sampleFault]);
    const create = vi.spyOn(api, "createSession").mockResolvedValue(makeSession());
    vi.spyOn(api, "reportObservation").mockRejectedValue(
      new api.ApiError(502, "Anthropic API call failed", "Anthropic API call failed"),
    );
    const onStarted = vi.fn();
    render(<StartScreen onStarted={onStarted} />);

    await screen.findByLabelText("Equipment label");
    fireEvent.change(screen.getByLabelText("Equipment label"), {
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
    expect(initial.error).toContain("Anthropic API call failed");
  });

  it("passes the initial notes' parse result on", async () => {
    vi.spyOn(api, "listFaults").mockResolvedValue([sampleFault]);
    vi.spyOn(api, "createSession").mockResolvedValue(makeSession());
    const observed = makeObservationResponse();
    vi.spyOn(api, "reportObservation").mockResolvedValue(observed);
    const onStarted = vi.fn();
    render(<StartScreen onStarted={onStarted} />);

    await screen.findByLabelText("Equipment label");
    fireEvent.change(screen.getByLabelText("Equipment label"), {
      target: { value: "Bay 1" },
    });
    fireEvent.change(screen.getByLabelText("Initial notes (optional)"), {
      target: { value: "Fan is fine" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Start session" }));

    await waitFor(() => expect(onStarted).toHaveBeenCalledTimes(1));
    expect(onStarted.mock.calls[0][2]).toEqual({ observation: observed, error: null });
  });
});

describe("session screen", () => {
  it("shows the initial notes' Understood feedback and error", () => {
    renderSession({
      initialObservation: makeObservationResponse(),
      initialError: "Session started, but the initial notes were not recorded: x",
    });

    expect(screen.getByText("fan_status = normal")).toBeInTheDocument();
    expect(
      screen.getByText("Session started, but the initial notes were not recorded: x"),
    ).toBeInTheDocument();
  });

  it("stays on the closed session after closing", async () => {
    const closed = makeSession({ status: "closed" });
    vi.spyOn(api, "closeSession").mockResolvedValue(closed);
    const props = renderSession();

    fireEvent.click(screen.getByRole("button", { name: "Close session" }));

    await waitFor(() => expect(props.onSessionChange).toHaveBeenCalledWith(closed));
    expect(props.onClosed).not.toHaveBeenCalled();
  });

  it("New session on a closed session leaves it", () => {
    const props = renderSession({ session: makeSession({ status: "closed" }) });

    fireEvent.click(screen.getByRole("button", { name: "New session" }));

    expect(props.onClosed).toHaveBeenCalledTimes(1);
  });
});

describe("causes", () => {
  it("shows which facts conflict for a contradiction", () => {
    render(
      <CausesPanel
        causes={[
          makeCause({
            cause_id: "excessive_load",
            name: "Excessive load",
            status: "contradiction",
            because: ["high_load_sustained", "load_percent"],
          }),
        ]}
      />,
    );

    expect(screen.getByText("Contradiction")).toBeInTheDocument();
    expect(
      screen.getByText("Conflicting facts: high_load_sustained, load_percent"),
    ).toBeInTheDocument();
  });
});
