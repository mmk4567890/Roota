import { Header } from "./components/Header";

function App() {
  return (
    <div className="min-h-screen">
      <Header />
      <main className="mx-auto max-w-5xl px-4 py-8 sm:px-6 sm:py-10">
        <section className="rounded-md border border-ink-200 bg-white px-5 py-10 text-center">
          <h2 className="text-lg font-semibold text-ink-900">Session UI coming soon</h2>
          <p className="mt-2 text-sm text-ink-500">
            Troubleshooting sessions will appear here once the diagnostic workflow is connected.
          </p>
        </section>
      </main>
    </div>
  );
}

export default App;
