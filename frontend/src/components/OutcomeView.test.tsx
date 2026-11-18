import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { OutcomeView } from "./OutcomeView";

describe("OutcomeView", () => {
  it("shows a root-cause headline, the action, and a muted mono source line", () => {
    const onViewReport = vi.fn();
    render(
      <OutcomeView
        kind="root_cause"
        outcome={{
          headline: "Root cause: Cooling fan not operating",
          paragraphs: ["Replace the fan.", "The other three causes were not checked."],
          source: "ABB ACS580 firmware manual · A581 Fan · p. 543",
        }}
        onViewReport={onViewReport}
        onCloseSession={vi.fn()}
        closeBusy={false}
        closed={false}
      />,
    );

    expect(
      screen.getByRole("heading", { name: "Root cause: Cooling fan not operating" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Replace the fan.")).toBeInTheDocument();
    expect(
      screen.getByText("The other three causes were not checked."),
    ).toBeInTheDocument();
    const source = screen.getByText(
      "Source: ABB ACS580 firmware manual · A581 Fan · p. 543",
    );
    expect(source).toHaveClass("font-mono", "text-hud-muted");
    fireEvent.click(screen.getByRole("button", { name: /View report/i }));
    expect(onViewReport).toHaveBeenCalledTimes(1);
  });

  it("shows the escalation headline and sentences without a source line", () => {
    render(
      <OutcomeView
        kind="escalate"
        outcome={{
          headline: "Escalated",
          paragraphs: [
            "None of the four documented causes could be confirmed. Three were ruled out by the checks.",
            "Escalate to a senior technician or OEM support, and recheck the air path through the cabinet first.",
          ],
          source: null,
        }}
        onViewReport={vi.fn()}
        onCloseSession={vi.fn()}
        closeBusy={false}
        closed={false}
      />,
    );

    expect(screen.getByRole("heading", { name: "Escalated" })).toBeInTheDocument();
    expect(screen.getByText(/recheck the air path/)).toBeInTheDocument();
    expect(screen.queryByText(/^Source:/)).toBeNull();
    expect(screen.queryByText(/Inconclusive:/)).toBeNull();
  });
});
