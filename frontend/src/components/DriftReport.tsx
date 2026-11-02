export function DriftReport() {
  return (
    <section className="rounded-md border border-ink-200 bg-white">
      <div className="border-b border-ink-100 px-5 py-4">
        <h2 className="text-lg font-semibold text-ink-900">Drift Report</h2>
        <p className="mt-0.5 text-sm text-ink-500">
          Analysis results will appear here after you run a comparison.
        </p>
      </div>
      <div className="px-5 py-10 text-center text-sm text-ink-400">
        No drift analysis has been run yet.
      </div>
    </section>
  );
}
