import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import * as api from "./api";
import {
  makeEscalatedSession,
  makeSession,
  sampleFault,
} from "./test/fixtures";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("Roota page", () => {
  it("renders the start screen after loading faults", async () => {
    vi.spyOn(api, "listFaults").mockResolvedValue([sampleFault]);

    render(<App />);

    expect(screen.getByRole("heading", { name: "ROOTA" })).toBeInTheDocument();

    await waitFor(() => {
      expect(
        screen.getByRole("heading", { name: "Start session" }),
      ).toBeInTheDocument();
    });
    expect(screen.getByLabelText("Problem")).toBeInTheDocument();
    expect(screen.getByLabelText("Equipment")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Start session" }),
    ).toBeInTheDocument();
    expect(screen.queryByText("MVP")).toBeNull();
  });
});

describe("session in the URL", () => {
  afterEach(() => {
    window.history.replaceState(null, "", "/");
  });

  it("reopens the session named in the URL after a reload", async () => {
    window.history.replaceState(null, "", "/?session=11111111-1111-1111-1111-111111111111");
    vi.spyOn(api, "listFaults").mockResolvedValue([sampleFault]);
    const getSession = vi.spyOn(api, "getSession").mockResolvedValue(makeSession());

    render(<App />);

    expect(await screen.findByText("Observe the cooling fan.")).toBeInTheDocument();
    expect(getSession).toHaveBeenCalledWith("11111111-1111-1111-1111-111111111111");
    expect(screen.queryByRole("heading", { name: "Start session" })).toBeNull();
  });

  it("opens a closed session in its outcome state", async () => {
    window.history.replaceState(null, "", "/?session=11111111-1111-1111-1111-111111111111");
    vi.spyOn(api, "listFaults").mockResolvedValue([sampleFault]);
    vi.spyOn(api, "getSession").mockResolvedValue(
      makeEscalatedSession({ status: "closed" }),
    );

    render(<App />);

    expect(
      await screen.findByRole("heading", { name: "Escalated" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /View report/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "New session" })).toBeInTheDocument();
  });

  it("puts the session id in the URL when a session starts and clears it on New session", async () => {
    vi.spyOn(api, "listFaults").mockResolvedValue([sampleFault]);
    vi.spyOn(api, "createSession").mockResolvedValue(
      makeEscalatedSession({ status: "closed" }),
    );

    render(<App />);
    await screen.findByRole("heading", { name: "Start session" });
    fireEvent.change(screen.getByLabelText("Problem"), {
      target: { value: sampleFault.fault_id },
    });
    fireEvent.change(screen.getByLabelText("Equipment"), {
      target: { value: "Line 3" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Start session" }));

    await screen.findByRole("heading", { name: "Escalated" });
    expect(window.location.search).toBe(
      "?session=11111111-1111-1111-1111-111111111111",
    );

    fireEvent.click(screen.getByRole("button", { name: "New session" }));
    await screen.findByRole("heading", { name: "Start session" });
    expect(window.location.search).toBe("");
  });

  it("falls back to the start screen with an error when the session is gone", async () => {
    window.history.replaceState(null, "", "/?session=missing");
    vi.spyOn(api, "listFaults").mockResolvedValue([sampleFault]);
    vi.spyOn(api, "getSession").mockRejectedValue(
      new api.ApiError(404, "Not Found", "Session not found"),
    );

    render(<App />);

    expect(
      await screen.findByText("Could not reopen the session: Session not found"),
    ).toBeInTheDocument();
    expect(
      await screen.findByRole("heading", { name: "Start session" }),
    ).toBeInTheDocument();
    expect(window.location.search).toBe("");
  });
});
