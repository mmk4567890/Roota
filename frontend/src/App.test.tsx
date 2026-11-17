import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import * as api from "./api";
import { sampleFault } from "./test/fixtures";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("Roota page", () => {
  it("renders the start screen after loading faults", async () => {
    vi.spyOn(api, "listFaults").mockResolvedValue([sampleFault]);

    render(<App />);

    expect(screen.getByRole("heading", { name: "ROOTA" })).toBeInTheDocument();

    await waitFor(() => {
      expect(
        screen.getByRole("heading", { name: "Start session" }),
      ).toBeInTheDocument();
    });
    expect(screen.getByLabelText("Problem")).toBeInTheDocument();
    expect(screen.getByLabelText("Equipment")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Start session" }),
    ).toBeInTheDocument();
    expect(screen.queryByText("MVP")).toBeNull();
  });
});
