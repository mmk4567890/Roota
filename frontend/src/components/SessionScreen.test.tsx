import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import * as api from "../api";
import {
  makeObservationResponse,
  makeSession,
  sampleFault,
} from "../test/fixtures";
import { SessionScreen } from "./SessionScreen";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("SessionScreen", () => {
  it("submitting an observation calls the API and shows Understood", async () => {
    const response = makeObservationResponse({
      parse: {
        extracted: { fan_status: "noisy" },
        unclear_fields: ["heatsink_condition"],
        rejected: [],
        notes: "",
      },
    });
    const spy = vi
      .spyOn(api, "reportObservation")
      .mockResolvedValue(response);
    const onSessionChange = vi.fn();

    render(
      <SessionScreen
        session={makeSession()}
        fault={sampleFault}
        onSessionChange={onSessionChange}
        onClosed={vi.fn()}
      />,
    );

    fireEvent.change(screen.getByLabelText("Report what you observed"), {
      target: { value: "The fan is noisy" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Submit" }));

    await waitFor(() => {
      expect(spy).toHaveBeenCalledTimes(1);
    });
    expect(spy).toHaveBeenCalledWith(
      "11111111-1111-1111-1111-111111111111",
      expect.objectContaining({ text: "The fan is noisy" }),
    );
    expect(screen.getByText("fan_status = noisy")).toBeInTheDocument();
    expect(screen.getByText("Understood:")).toBeInTheDocument();
    expect(screen.getByText("heatsink_condition")).toBeInTheDocument();
    expect(screen.getByText("Unclear:")).toBeInTheDocument();
    expect(onSessionChange).toHaveBeenCalledWith(response);
  });

  it("shows the backend 422 message and never swallows it", async () => {
    vi.spyOn(api, "reportObservation").mockRejectedValue(
      new api.ApiError(422, "facts must not be empty", "facts must not be empty"),
    );

    render(
      <SessionScreen
        session={makeSession()}
        fault={sampleFault}
        onSessionChange={vi.fn()}
        onClosed={vi.fn()}
      />,
    );

    fireEvent.change(screen.getByLabelText("Report what you observed"), {
      target: { value: "unclear reading" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Submit" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "facts must not be empty",
    );
  });

  it("shows the backend 502 message from a parser failure", async () => {
    vi.spyOn(api, "reportObservation").mockRejectedValue(
      new api.ApiError(
        502,
        "no report_observation_fields tool call",
        "no report_observation_fields tool call",
      ),
    );

    render(
      <SessionScreen
        session={makeSession()}
        fault={sampleFault}
        onSessionChange={vi.fn()}
        onClosed={vi.fn()}
      />,
    );

    fireEvent.change(screen.getByLabelText("Report what you observed"), {
      target: { value: "something odd" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Submit" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "no report_observation_fields tool call",
    );
  });

  it("disables submit while a request is in flight (no double-submit)", async () => {
    const deferred: {
      resolve: (value: api.ObservationResponse) => void;
    } = {
      resolve: () => {
        throw new Error("resolve not set");
      },
    };
    const spy = vi.spyOn(api, "reportObservation").mockImplementation(
      () =>
        new Promise((resolve) => {
          deferred.resolve = resolve;
        }),
    );

    render(
      <SessionScreen
        session={makeSession()}
        fault={sampleFault}
        onSessionChange={vi.fn()}
        onClosed={vi.fn()}
      />,
    );

    fireEvent.change(screen.getByLabelText("Report what you observed"), {
      target: { value: "Fan sounds rough" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Submit" }));

    const busy = await screen.findByRole("button", { name: "Submitting…" });
    expect(busy).toBeDisabled();
    fireEvent.click(busy);
    expect(spy).toHaveBeenCalledTimes(1);

    deferred.resolve(makeObservationResponse());
    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: "Submit" }),
      ).toBeInTheDocument();
    });
  });
});

