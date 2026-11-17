import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { SessionSummary } from "../api";
import { SummaryPanel } from "./SummaryPanel";

const summaryFixture: SessionSummary = {
  session_id: "sess-1",
  fault_id: "acs580_overtemperature",
  display_name: "ABB ACS580 drive overtemperature",
  equipment_label: "Line 3",
  status: "active",
  started_at: "2026-11-17T12:00:00Z",
  closed_at: null,
  causes: [
    {
      cause_id: "cooling_fan_failure",
      name: "Cooling fan not operating",
      status: "confirmed",
      because: ["fan_status"],
      promoted: false,
    },
    {
      cause_id: "blocked_airflow",
      name: "Obstructed cooling air flow or dusty heatsink",
      status: "open",
      because: [],
      promoted: false,
    },
  ],
  root_cause: {
    cause_id: "cooling_fan_failure",
    name: "Cooling fan not operating",
    corrective_action: "Replace the fan if faulty.",
    source: {
      doc_id: "abb_acs580_fw",
      section: "Fault tracing: A581 Fan",
      page: 541,
    },
  },
  escalation_reason: null,
  facts: [
    {
      field: "fan_status",
      value: "not_running",
      reported_at: "2026-11-17T12:01:00Z",
      event_id: 1,
      how: "observation",
      text: "The cooling fan is not running.",
      undone: false,
    },
  ],
  citations: [
    {
      doc_id: "abb_acs580_fw",
      section: "Fault tracing: A581 Fan",
      page: 541,
      used_for: "cause:cooling_fan_failure",
      passage: "Check fan operation and connection. Replace fan if faulty.",
    },
  ],
};

const escalateFixture: SessionSummary = {
  ...summaryFixture,
  root_cause: null,
  escalation_reason:
    "All documented causes are ruled out or inconclusive; none confirmed. Inconclusive: Cooling fan not operating (fan_status='noisy').",
  causes: [
    {
      cause_id: "cooling_fan_failure",
      name: "Cooling fan not operating",
      status: "inconclusive",
      because: ["fan_status"],
      promoted: false,
    },
  ],
  facts: [
    {
      field: "fan_status",
      value: "noisy",
      reported_at: "2026-11-17T12:01:00Z",
      event_id: 1,
      how: "form",
      text: null,
      undone: false,
    },
  ],
  citations: [],
};

vi.mock("../api", async () => {
  const actual = await vi.importActual<typeof import("../api")>("../api");
  return {
    ...actual,
    getSessionSummary: vi.fn(),
    getSessionSummaryMarkdown: vi.fn(),
  };
});

import { getSessionSummary, getSessionSummaryMarkdown } from "../api";

const getSummaryMock = vi.mocked(getSessionSummary);
const getMarkdownMock = vi.mocked(getSessionSummaryMarkdown);

afterEach(() => {
  vi.clearAllMocks();
});

describe("SummaryPanel", () => {
  it("shows a green root-cause banner, causes, facts, citations, and print control", async () => {
    getSummaryMock.mockResolvedValue(summaryFixture);
    getMarkdownMock.mockResolvedValue("# markdown");

    render(<SummaryPanel sessionId="sess-1" />);
    fireEvent.click(screen.getByRole("button", { name: "Show summary" }));

    await waitFor(() => {
      expect(screen.getByText("Root cause found")).toBeInTheDocument();
    });
    expect(
      screen.getAllByText("Cooling fan not operating").length,
    ).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Facts timeline")).toBeInTheDocument();
    expect(
      screen.getByText(/The cooling fan is not running/),
    ).toBeInTheDocument();
    expect(screen.getByText(/typed observation/)).toBeInTheDocument();
    expect(
      screen.getByText(/Check fan operation and connection/),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Print / Save as PDF" }),
    ).toBeInTheDocument();
  });

  it("shows an amber escalate banner naming inconclusive causes", async () => {
    getSummaryMock.mockResolvedValue(escalateFixture);
    getMarkdownMock.mockResolvedValue("# markdown");

    render(<SummaryPanel sessionId="sess-2" />);
    fireEvent.click(screen.getByRole("button", { name: "Show summary" }));

    await waitFor(() => {
      expect(screen.getByText("Escalate")).toBeInTheDocument();
    });
    expect(
      screen.getByText(/Inconclusive causes: Cooling fan not operating/),
    ).toBeInTheDocument();
  });

  it("auto-loads when autoOpen is set", async () => {
    getSummaryMock.mockResolvedValue(summaryFixture);
    getMarkdownMock.mockResolvedValue("# markdown");

    render(
      <SummaryPanel
        sessionId="sess-3"
        autoOpen
        outcomeKey="active:root_cause:cooling_fan_failure"
      />,
    );

    await waitFor(() => {
      expect(screen.getByText("Root cause found")).toBeInTheDocument();
    });
    expect(getSummaryMock).toHaveBeenCalledWith("sess-3");
  });
});
