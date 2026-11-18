import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import * as api from "../api";
import { makeEscalatedSession, makeSummary, sampleFault } from "../test/fixtures";
import { SessionScreen } from "./SessionScreen";

beforeEach(() => {
  window.history.replaceState(null, "", "/?session=s1");
  vi.spyOn(api, "getSessionSummary").mockResolvedValue(makeSummary());
  vi.spyOn(api, "getSessionSummaryMarkdown").mockResolvedValue("# Report\n");
});

afterEach(() => {
  vi.restoreAllMocks();
});

function renderEscalated() {
  render(
    <SessionScreen
      session={makeEscalatedSession()}
      fault={sampleFault}
      onSessionChange={vi.fn()}
      onClosed={vi.fn()}
    />,
  );
}

async function openReport(): Promise<void> {
  fireEvent.click(screen.getByRole("button", { name: /View report/i }));
  expect(
    await screen.findByRole("button", { name: "Close report" }),
  ).toBeInTheDocument();
}

function reportShown(): boolean {
  return screen.queryByRole("button", { name: "Close report" }) !== null;
}

describe("report navigation", () => {
  it("pushes a history entry when the report opens", async () => {
    renderEscalated();
    const before = window.history.length;
    await openReport();
    expect(window.history.length).toBe(before + 1);
    expect(window.location.search).toBe("?session=s1");
  });

  it("closes the report on Escape and returns to the session", async () => {
    renderEscalated();
    await openReport();
    fireEvent.keyDown(window, { key: "Escape" });
    await waitFor(() => expect(reportShown()).toBe(false));
    expect(screen.getByRole("heading", { name: "ESCALATED" })).toBeInTheDocument();
  });

  it("closes the report on browser Back", async () => {
    renderEscalated();
    await openReport();
    window.history.back();
    await waitFor(() => expect(reportShown()).toBe(false));
    expect(screen.getByRole("heading", { name: "ESCALATED" })).toBeInTheDocument();
  });

  it("still closes with the Close button", async () => {
    renderEscalated();
    await openReport();
    fireEvent.click(screen.getByRole("button", { name: "Close report" }));
    await waitFor(() => expect(reportShown()).toBe(false));
  });

  it("can reopen the report after closing it", async () => {
    renderEscalated();
    await openReport();
    fireEvent.keyDown(window, { key: "Escape" });
    await waitFor(() => expect(reportShown()).toBe(false));
    await openReport();
  });
});
