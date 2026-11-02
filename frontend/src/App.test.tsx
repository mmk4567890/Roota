import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import App from "./App";

describe("Roota page", () => {
  it("renders the Roota landing page", () => {
    render(<App />);

    expect(screen.getByRole("heading", { name: "Roota" })).toBeInTheDocument();
    expect(
      screen.getByText("Stateful fault isolation for industrial drives"),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Session UI coming soon" }),
    ).toBeInTheDocument();
  });
});
