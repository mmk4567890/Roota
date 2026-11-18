import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { sampleFault } from "../test/fixtures";
import { TopBar } from "./TopBar";

describe("TopBar", () => {
  it("shows brand alone before a session starts", () => {
    render(<TopBar />);
    expect(screen.getByRole("heading", { name: "ROOTA" })).toBeInTheDocument();
    expect(screen.queryByText("Session log")).toBeNull();
    expect(screen.queryByText("ACTIVE")).toBeNull();
  });

  it("shows the fault name, equipment, fault codes, status, and session log control", () => {
    const onOpenLog = vi.fn();
    render(
      <TopBar
        fault={sampleFault}
        equipmentLabel="Line 3 conveyor drive"
        status="active"
        actionType="check"
        showLog
        onOpenLog={onOpenLog}
      />,
    );

    expect(screen.getByText(sampleFault.display_name)).toBeInTheDocument();
    expect(screen.getByText("Line 3 conveyor drive")).toBeInTheDocument();
    expect(screen.getByText(/OH · OT · OH1/)).toBeInTheDocument();
    expect(screen.getByText("ACTIVE")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Session log" }));
    expect(onOpenLog).toHaveBeenCalledTimes(1);
  });
});
