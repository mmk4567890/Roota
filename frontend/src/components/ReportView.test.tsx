import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import * as api from "../api";
import { ReportView } from "./ReportView";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("ReportView", () => {
  it("renders labeled facts and cause badges without raw ids or [x] marks", async () => {
    vi.spyOn(api, "getSessionSummary").mockResolvedValue({
      session_id: "11111111-1111-1111-1111-111111111111",
      fault_id: "acs580_overtemperature",
      display_name: "Overtemperature — ABB ACS580",
      equipment_label: "Line 3",
      status: "closed",
      started_at: "2026-01-01T12:00:00Z",
      closed_at: "2026-01-01T12:10:00Z",
      causes: [
        {
          cause_id: "cooling_fan_failure",
          name: "Cooling fan not operating",
          status: "confirmed",
          because: ["Fan status"],
          promoted: false,
        },
      ],
      root_cause: {
        cause_id: "cooling_fan_failure",
        name: "Cooling fan not operating",
        corrective_action: "Replace the fan.",
        source: {
          doc_id: "abb_acs580_fw",
          section: "Fault tracing: A581 Fan (printed p. 543)",
          page: 541,
          printed_page: 543,
        },
      },
      escalation_reason: null,
      facts: [
        {
          field: "fan_status",
          field_label: "Fan status",
          value: "not_running",
          value_label: "Not running",
          reported_at: "2026-01-01T12:01:00Z",
          event_id: 1,
          how: "observation",
          text: "The cooling fan is not running.",
          undone: false,
        },
      ],
      citations: [
        {
          doc_id: "abb_acs580_fw",
          short_name: "ABB ACS580 firmware manual",
          full_title:
            "ABB ACS580 standard control program firmware manual, 3AXD50000016097 Rev J",
          section: "Fault tracing: A581 Fan (printed p. 543)",
          section_label: "A581 Fan",
          page: 543,
          used_for: "cause:cooling_fan_failure",
          passage: null,
        },
      ],
    });
    vi.spyOn(api, "getSessionSummaryMarkdown").mockResolvedValue(
      "# Session summary\n\nFan status: Not running\n",
    );

    render(
      <ReportView
        sessionId="11111111-1111-1111-1111-111111111111"
        onClose={vi.fn()}
      />,
    );

    await waitFor(() =>
      expect(
        screen.getAllByText("Cooling fan not operating").length,
      ).toBeGreaterThan(0),
    );
    expect(screen.getByText("Confirmed")).toBeInTheDocument();
    expect(screen.getByText(/Fan status: Not running/)).toBeInTheDocument();
    expect(screen.queryByText("[x]")).toBeNull();
    expect(screen.queryByText("fan_status")).toBeNull();
    expect(screen.queryByText("CONFIRMED")).toBeNull();
    expect(screen.getByRole("button", { name: "Copy" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Download" })).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Print / Save as PDF" }),
    ).toBeInTheDocument();
  });
});
