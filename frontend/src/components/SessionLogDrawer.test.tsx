import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { Event } from "../api";
import { sampleFault } from "../test/fixtures";
import { SessionLogDrawer } from "./SessionLogDrawer";

const SESSION_ID = "11111111-1111-1111-1111-111111111111";

const events: Event[] = [
  {
    id: 1,
    session_id: SESSION_ID,
    seq: 1,
    type: "facts_reported",
    created_at: "2026-01-01T12:01:00Z",
    payload: {
      facts: { fan_status: "noisy" },
      check_id: "check_fan_operation",
    },
  },
  {
    id: 2,
    session_id: SESSION_ID,
    seq: 2,
    type: "observation",
    created_at: "2026-01-01T12:02:00Z",
    payload: {
      text: "Vents look clear",
      extracted: { airflow_obstruction: "none" },
      unclear_fields: [],
      rejected: [],
    },
  },
];

describe("SessionLogDrawer", () => {
  it("opens, lists labeled facts, and undoes an event", () => {
    const onUndo = vi.fn();
    const onClose = vi.fn();
    render(
      <SessionLogDrawer
        open
        events={events}
        fields={[
          ...sampleFault.fields,
          {
            name: "airflow_obstruction",
            label: "Airflow obstruction",
            type: "enum",
            values: ["none", "partial", "blocked", "unclear"],
            value_labels: {
              none: "None",
              partial: "Partial",
              blocked: "Blocked",
              unclear: "Not sure",
            },
            unit: null,
            description: "Air path",
            ask: "Any obstruction?",
          },
        ]}
        disabled={false}
        undoingEventId={null}
        onClose={onClose}
        onUndo={onUndo}
      />,
    );

    expect(
      screen.getByRole("dialog", { name: /session log/i }),
    ).toBeInTheDocument();
    expect(screen.getByText("Fan status: Noisy")).toBeInTheDocument();
    expect(screen.getByText("Airflow obstruction: None")).toBeInTheDocument();
    expect(screen.getByText(/Vents look clear/)).toBeInTheDocument();
    expect(screen.queryByText("fan_status")).toBeNull();

    const undoButtons = screen.getAllByRole("button", { name: /Undo/i });
    fireEvent.click(undoButtons[0]);
    expect(onUndo).toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "Close" }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("renders nothing when closed", () => {
    const { container } = render(
      <SessionLogDrawer
        open={false}
        events={events}
        fields={sampleFault.fields}
        disabled={false}
        undoingEventId={null}
        onClose={vi.fn()}
        onUndo={vi.fn()}
      />,
    );
    expect(container).toBeEmptyDOMElement();
  });
});
