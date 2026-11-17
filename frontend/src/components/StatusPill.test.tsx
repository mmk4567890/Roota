import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { sessionPhase, StatusPill } from "./StatusPill";

describe("StatusPill", () => {
  it("maps session phase from status and action type", () => {
    expect(sessionPhase("active", "check")).toBe("active");
    expect(sessionPhase("active", "root_cause")).toBe("root_cause");
    expect(sessionPhase("active", "escalate")).toBe("escalated");
    expect(sessionPhase("closed", "escalate")).toBe("closed");
  });

  it("renders each phase label", () => {
    const { rerender } = render(
      <StatusPill status="active" actionType="check" />,
    );
    expect(screen.getByText("ACTIVE")).toBeInTheDocument();

    rerender(<StatusPill status="active" actionType="root_cause" />);
    expect(screen.getByText("ROOT CAUSE FOUND")).toBeInTheDocument();

    rerender(<StatusPill status="active" actionType="escalate" />);
    expect(screen.getByText("ESCALATED")).toBeInTheDocument();

    rerender(<StatusPill status="closed" />);
    expect(screen.getByText("CLOSED")).toBeInTheDocument();
  });
});
