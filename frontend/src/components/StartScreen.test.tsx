import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import * as api from "../api";
import {
  makeObservationResponse,
  makeSession,
  sampleFault,
} from "../test/fixtures";
import { StartScreen } from "./StartScreen";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("StartScreen", () => {
  it("sends initial notes as the first observation", async () => {
    vi.spyOn(api, "listFaults").mockResolvedValue([sampleFault]);
    vi.spyOn(api, "createSession").mockResolvedValue(makeSession());
    const observed = makeObservationResponse({
      state: {
        ...makeSession().state,
        facts: { fan_status: "not_running" },
      },
      parse: {
        extracted: { fan_status: "not_running" },
        unclear_fields: [],
        rejected: [],
        notes: "",
      },
    });
    const observe = vi.spyOn(api, "reportObservation").mockResolvedValue(observed);
    const onStarted = vi.fn();
    render(<StartScreen onStarted={onStarted} />);

    await screen.findByLabelText("Equipment");
    fireEvent.change(screen.getByLabelText("Equipment"), {
      target: { value: "Bay 4" },
    });
    fireEvent.change(screen.getByLabelText("Initial notes (optional)"), {
      target: { value: "The cooling fan is not running." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Start session" }));

    await waitFor(() => expect(onStarted).toHaveBeenCalledTimes(1));
    expect(api.createSession).toHaveBeenCalledWith({
      fault_id: sampleFault.fault_id,
      equipment_label: "Bay 4",
    });
    expect(observe).toHaveBeenCalledWith(makeSession().id, {
      text: "The cooling fan is not running.",
    });
    const [session, fault, initial] = onStarted.mock.calls[0];
    expect(session).toBe(observed);
    expect(fault.fault_id).toBe(sampleFault.fault_id);
    expect(initial.observation).toBe(observed);
    expect(initial.error).toBeNull();
  });
});
