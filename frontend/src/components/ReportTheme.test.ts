import { describe, expect, it } from "vitest";
import css from "../index.css?raw";
import reportSource from "./ReportView.tsx?raw";

function printBlock(source: string): string {
  const start = source.indexOf("@media print");
  expect(start).toBeGreaterThan(-1);
  return source.slice(start);
}

describe("report theme", () => {
  it("has a print stylesheet that turns the report black on white", () => {
    const print = printBlock(css);
    expect(print).toMatch(/\.report-overlay\s*\{[^}]*position:\s*static/);
    expect(print).toMatch(/\.report-overlay\s*\{[^}]*background:\s*white/);
    expect(print).toMatch(/\.session-report \*\s*\{[^}]*color:\s*black/);
    expect(print).toMatch(/\.no-print\s*\{[^}]*display:\s*none/);
    expect(print).toMatch(/\.session-report \.status-dot\s*\{[^}]*var\(--status-dot\)/);
  });

  it("keeps the report in the dark HUD style on screen", () => {
    expect(reportSource).toContain("report-overlay");
    expect(reportSource).toContain("bg-hud-bg");
    expect(reportSource).not.toMatch(/bg-white|text-black/);
  });
});
