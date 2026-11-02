import { DriftReport } from "./components/DriftReport";
import { Header } from "./components/Header";
import { UploadPlaceholder } from "./components/UploadPlaceholder";

function App() {
  return (
    <div className="min-h-screen">
      <Header />
      <main className="mx-auto max-w-5xl px-4 py-8 sm:px-6 sm:py-10">
        <section className="mb-8">
          <h2 className="text-lg font-semibold text-ink-900">Compare documents</h2>
          <p className="mt-1 text-sm text-ink-500">
            Provide a reference SOP and the current process document to begin.
          </p>
          <div className="mt-5 grid gap-4 sm:grid-cols-2">
            <UploadPlaceholder
              title="Reference SOP"
              description="The approved standard operating procedure used as the baseline."
            />
            <UploadPlaceholder
              title="Current Process"
              description="The live or observed process documentation to compare against the SOP."
            />
          </div>
          <div className="mt-5">
            <button
              type="button"
              disabled
              className="w-full rounded-md bg-ink-300 px-4 py-2.5 text-sm font-semibold text-white sm:w-auto"
            >
              Analyze Drift
            </button>
            <p className="mt-2 text-xs text-ink-400">
              Analysis will be available in a future release.
            </p>
          </div>
        </section>

        <DriftReport />
      </main>
    </div>
  );
}

export default App;
