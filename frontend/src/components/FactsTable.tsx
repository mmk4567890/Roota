interface FactsTableProps {
  facts: Record<string, unknown>;
}

export function FactsTable({ facts }: FactsTableProps) {
  const entries = Object.entries(facts);

  return (
    <section
      aria-labelledby="facts-heading"
      className="rounded-md border border-ink-200 bg-white px-4 py-4"
    >
      <h2 id="facts-heading" className="text-sm font-semibold text-ink-900">
        Known facts
      </h2>
      {entries.length === 0 ? (
        <p className="mt-2 text-sm text-ink-400">No facts recorded yet.</p>
      ) : (
        <div className="mt-2 overflow-x-auto">
          <table className="w-full min-w-[16rem] text-left text-sm">
            <thead>
              <tr className="border-b border-ink-200 text-xs uppercase tracking-wide text-ink-500">
                <th scope="col" className="py-1.5 pr-3 font-semibold">
                  Field
                </th>
                <th scope="col" className="py-1.5 font-semibold">
                  Value
                </th>
              </tr>
            </thead>
            <tbody>
              {entries.map(([field, value]) => (
                <tr key={field} className="border-b border-ink-100">
                  <th scope="row" className="py-1.5 pr-3 font-medium text-ink-800">
                    {field}
                  </th>
                  <td className="py-1.5 text-ink-700">{formatValue(value)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function formatValue(value: unknown): string {
  if (typeof value === "boolean") {
    return value ? "true" : "false";
  }
  if (value === null || value === undefined) {
    return "—";
  }
  return String(value);
}
