import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { makeAction, makeCause } from "../test/fixtures";
import { OutcomeView } from "./OutcomeView";

describe("OutcomeView", () => {
  it("shows root cause without a duplicate mono tag", () => {
    const onViewReport = vi.fn();
    const onCloseSession = vi.fn();
    render(
      <OutcomeView
        action={makeAction({
          type: "root_cause",
          message: "Replace the fan.",
          cause_id: "cooling_fan_failure",
          source: {
            doc_id: "abb_acs580_fw",
            section: "Fault tracing: A581 Fan (printed p. 543)",
            page: 541,
            printed_page: 543,
          },
        })}
        causes={[
          makeCause({
            cause_id: "cooling_fan_failure",
            name: "Cooling fan not operating",
            status: "confirmed",
          }),
        ]}
        onViewReport={onViewReport}
        onCloseSession={onCloseSession}
        closeBusy={false}
        closed={false}
      />,
    );

    expect(screen.getByRole("heading", { name: "ROOT CAUSE" })).toBeInTheDocument();
    expect(screen.queryByText("[ OUTCOME ]")).toBeNull();
    expect(screen.queryByText("[ ESCALATION ]")).toBeNull();
    expect(screen.getByText("Cooling fan not operating")).toBeInTheDocument();
    expect(screen.getByText("Replace the fan.")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /View report/i }));
    expect(onViewReport).toHaveBeenCalledTimes(1);
  });

  it("shows escalation with inconclusive causes and no duplicate tag", () => {
    render(
      <OutcomeView
        action={makeAction({
          type: "escalate",
          message:
            "All documented causes are ruled out or inconclusive; none confirmed. Inconclusive: Cooling fan not operating (Fan status: Noisy).",
          cause_id: "cooling_fan_failure",
        })}
        causes={[
          makeCause({
            cause_id: "cooling_fan_failure",
            name: "Cooling fan not operating",
            status: "inconclusive",
            because: ["fan_status"],
          }),
          makeCause({
            cause_id: "blocked_airflow",
            name: "Blocked airflow",
            status: "ruled_out",
          }),
        ]}
        onViewReport={vi.fn()}
        onCloseSession={vi.fn()}
        closeBusy={false}
        closed={false}
      />,
    );

    expect(screen.getByRole("heading", { name: "ESCALATED" })).toBeInTheDocument();
    expect(screen.queryByText("[ ESCALATION ]")).toBeNull();
    expect(
      screen.getByText("Escalate to a senior technician / OEM support"),
    ).toBeInTheDocument();
    expect(screen.getByText(/Fan status: Noisy/)).toBeInTheDocument();
    expect(screen.getByText("[ INCONCLUSIVE ]")).toBeInTheDocument();
    expect(screen.getByText("Cooling fan not operating")).toBeInTheDocument();
    expect(screen.queryByText("fan_status")).toBeNull();
  });
});
