import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import App from "./App";

describe("Routa page", () => {
  it("renders the Routa landing page", () => {
    render(<App />);

    expect(screen.getByRole("heading", { name: "Routa" })).toBeInTheDocument();
    expect(
      screen.getByText("Detect operational drift before it becomes operational risk."),
    ).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Drift Report" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Analyze Drift" })).toBeDisabled();
  });
});
