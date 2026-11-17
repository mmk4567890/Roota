import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { makeCause } from "../test/fixtures";
import { CausesPanel } from "./CausesPanel";

describe("CausesPanel", () => {
  it("groups causes into confirmed, still relevant, inconclusive, and ruled out", () => {
    render(
      <CausesPanel
        causes={[
          makeCause({
            cause_id: "blocked_airflow",
            name: "Blocked airflow",
            status: "ruled_out",
            because: ["airflow_obstruction"],
          }),
          makeCause({
            cause_id: "cooling_fan_failure",
            name: "Cooling fan failure",
            status: "confirmed",
          }),
          makeCause({
            cause_id: "noisy_fan",
            name: "Noisy cooling fan",
            status: "inconclusive",
            because: ["fan_status"],
          }),
          makeCause({
            cause_id: "excessive_load",
            name: "Excessive load",
            status: "open",
            promoted: true,
          }),
          makeCause({
            cause_id: "high_ambient",
            name: "High ambient temperature",
            status: "open",
          }),
        ]}
      />,
    );

    expect(
      screen.getByRole("heading", { name: "Confirmed" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Still relevant" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Inconclusive" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Ruled out" }),
    ).toBeInTheDocument();

    expect(screen.getByText("Cooling fan failure")).toBeInTheDocument();
    expect(screen.getByText("Excessive load")).toBeInTheDocument();
    expect(screen.getByText("High ambient temperature")).toBeInTheDocument();
    expect(screen.getByText("Blocked airflow")).toBeInTheDocument();
    expect(screen.getByText("Noisy cooling fan")).toBeInTheDocument();
    expect(screen.getByText("Promoted")).toBeInTheDocument();
    expect(screen.getAllByText("Inconclusive").length).toBeGreaterThanOrEqual(1);
    expect(
      screen.getByText(/Left unresolved by: fan_status/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Ruled out by: airflow_obstruction/),
    ).toBeInTheDocument();
  });

  it("preserves API investigation order within still relevant", () => {
    render(
      <CausesPanel
        causes={[
          makeCause({
            cause_id: "second",
            name: "Second open",
            status: "open",
          }),
          makeCause({
            cause_id: "first",
            name: "First open",
            status: "open",
            promoted: true,
          }),
        ]}
      />,
    );

    const items = screen.getAllByRole("listitem");
    // Still-relevant items appear after empty Confirmed empty-state text;
    // filter to cause names.
    const names = items.map((item) => item.textContent ?? "");
    const secondIdx = names.findIndex((text) => text.includes("Second open"));
    const firstIdx = names.findIndex((text) => text.includes("First open"));
    expect(secondIdx).toBeGreaterThanOrEqual(0);
    expect(firstIdx).toBeGreaterThan(secondIdx);
  });
});
