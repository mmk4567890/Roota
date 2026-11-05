import { afterEach, describe, expect, it, vi } from "vitest";
import { formatApiDetail, listFaults, reportObservation } from "./api";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("formatApiDetail", () => {
  it("formats a string detail", () => {
    expect(formatApiDetail("Session is closed")).toBe("Session is closed");
  });

  it("formats FastAPI 422 validation error lists", () => {
    expect(
      formatApiDetail([
        { loc: ["body", "text"], msg: "Field required", type: "missing" },
      ]),
    ).toBe("body.text: Field required");
  });
});

describe("API client errors", () => {
  it("surfaces 422 detail from the backend", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 422,
        text: async () =>
          JSON.stringify({ detail: "Unknown fault_id 'nope'" }),
      }),
    );

    await expect(listFaults()).rejects.toMatchObject({
      name: "ApiError",
      status: 422,
      message: "Unknown fault_id 'nope'",
    });
  });

  it("surfaces 502 detail from the backend", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 502,
        text: async () =>
          JSON.stringify({
            detail: "no report_observation_fields tool call",
          }),
      }),
    );

    await expect(
      reportObservation("11111111-1111-1111-1111-111111111111", {
        text: "fan ok",
      }),
    ).rejects.toMatchObject({
      status: 502,
      message: "no report_observation_fields tool call",
    });
  });
});
