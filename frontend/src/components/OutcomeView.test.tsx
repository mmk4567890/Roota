import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { OutcomeView } from "./OutcomeView";

describe("OutcomeView", () => {
  it("shows the root cause as plain sentences", () => {
    const onViewReport = vi.fn();
    render(
      <OutcomeView
        kind="root_cause"
        paragraphs={[
          "Root cause found: Cooling fan not operating. Replace the fan. Source: ABB ACS580 firmware manual, A581 Fan, p. 543.",
          "The other three causes were not checked.",
        ]}
        onViewReport={onViewReport}
        onCloseSession={vi.fn()}
        closeBusy={false}
        closed={false}
      />,
    );

    expect(screen.getByRole("heading", { name: "ROOT CAUSE" })).toBeInTheDocument();
    expect(
      screen.getByText(/^Root cause found: Cooling fan not operating\./),
    ).toBeInTheDocument();
    expect(
      screen.getByText("The other three causes were not checked."),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /View report/i }));
    expect(onViewReport).toHaveBeenCalledTimes(1);
  });

  it("shows the escalation sentences without log-style lists", () => {
    render(
      <OutcomeView
        kind="escalate"
        paragraphs={[
          "None of the four documented causes could be confirmed. Three were ruled out by the checks.",
          "Escalate to a senior technician or OEM support, and recheck the air path through the cabinet first.",
        ]}
        onViewReport={vi.fn()}
        onCloseSession={vi.fn()}
        closeBusy={false}
        closed={false}
      />,
    );

    expect(screen.getByRole("heading", { name: "ESCALATED" })).toBeInTheDocument();
    expect(screen.getByText(/recheck the air path/)).toBeInTheDocument();
    expect(screen.queryByText("[ INCONCLUSIVE ]")).toBeNull();
    expect(screen.queryByText(/Inconclusive:/)).toBeNull();
  });
});
