import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { makeAction, makeCause } from "../test/fixtures";
import { NextActionCard } from "./NextActionCard";

const causes = [
  makeCause({
    cause_id: "cooling_fan_failure",
    name: "Cooling fan failure",
    status: "confirmed",
  }),
];

describe("NextActionCard", () => {
  it("renders a check with instruction, reason, and cited source", () => {
    render(
      <NextActionCard
        causes={causes}
        action={makeAction({
          type: "check",
          message: "Observe the cooling fan.",
          check: {
            id: "check_fan_operation",
            instruction: "Observe the cooling fan while powered.",
            reason: "Fan failure is a common first cause.",
            collects: ["fan_status"],
            source: {
              doc_id: "TBD_MANUAL",
              section: "Cooling fan",
              page: 42,
            },
          },
        })}
      />,
    );

    expect(
      screen.getByRole("heading", { name: "Perform this check" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Observe the cooling fan while powered."),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Fan failure is a common first cause/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/TBD_MANUAL, §Cooling fan, p\.42/),
    ).toBeInTheDocument();
  });

  it("renders need_info as a distinct question panel", () => {
    render(
      <NextActionCard
        causes={causes}
        action={makeAction({
          type: "need_info",
          message: "What is the cooling fan doing — running normally?",
          fields: ["fan_status"],
        })}
      />,
    );

    expect(
      screen.getByRole("heading", { name: "Need more information" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("What is the cooling fan doing — running normally?"),
    ).toBeInTheDocument();
  });

  it("renders root_cause with cause name, corrective action, and source", () => {
    render(
      <NextActionCard
        causes={causes}
        action={makeAction({
          type: "root_cause",
          cause_id: "cooling_fan_failure",
          message: "Replace the cooling fan assembly.",
          source: {
            doc_id: "TBD_MANUAL",
            section: "Fan replacement",
            page: 90,
          },
        })}
      />,
    );

    expect(
      screen.getByRole("heading", { name: "Root cause identified" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/Cooling fan failure/)).toBeInTheDocument();
    expect(
      screen.getByText("Replace the cooling fan assembly."),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/TBD_MANUAL, §Fan replacement, p\.90/),
    ).toBeInTheDocument();
  });

  it("renders escalate as an unmistakable warning with API reason", () => {
    render(
      <NextActionCard
        causes={causes}
        action={makeAction({
          type: "escalate",
          message:
            "All documented causes for this fault have been ruled out.",
        })}
      />,
    );

    expect(screen.getByRole("heading", { name: "Escalate" })).toBeInTheDocument();
    expect(
      screen.getByText(
        "Stop — escalate to a senior technician / OEM support",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "All documented causes for this fault have been ruled out.",
      ),
    ).toBeInTheDocument();
  });
});
