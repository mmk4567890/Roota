import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { sampleFault } from "../test/fixtures";
import { CurrentCheck } from "./CurrentCheck";

const check = {
  id: "check_fan_operation",
  instruction: "Observe the cooling fan.",
  reason: "Fan failure is common.",
  collects: ["fan_status"],
  source: {
    doc_id: "abb_acs580_fw",
    section: "Fault tracing: 4290 Cooling (printed p. 557)",
    page: 555,
    printed_page: 557,
  },
};

describe("CurrentCheck", () => {
  it("shows check progress, citation with printed page, and chips", () => {
    render(
      <CurrentCheck
        check={check}
        checkIndex={2}
        checkTotal={5}
        fields={sampleFault.fields}
        evidence={[
          {
            doc_id: "abb_acs580_fw",
            title: "ACS580 firmware manual",
            page: 555,
            section: "4290 Cooling",
            text: "Check air flow and fan operation.",
            kind: "cited",
          },
        ]}
        disabled={false}
        submitting={false}
        lastParse={null}
        lastMessage={null}
        onChip={vi.fn(async () => true)}
        onObserve={vi.fn(async () => true)}
      />,
    );

    expect(screen.getByText("[ CHECK 2 / 5 ]")).toBeInTheDocument();
    expect(screen.getByText("Observe the cooling fan.")).toBeInTheDocument();
    expect(
      screen.getByText(/ABB ACS580 firmware manual · 4290 Cooling · \[ P\. 557 \]/),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Normal" })).toBeInTheDocument();
    expect(screen.queryByText("fan_status")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "View passage" }));
    expect(
      screen.getByText(/3AXD50000016097 Rev J/),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Check air flow and fan operation."),
    ).toBeInTheDocument();
  });
});
