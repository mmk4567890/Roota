export function Header() {
  return (
    <header className="border-b border-ink-200 bg-white">
      <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-5 sm:px-6">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-ink-950 sm:text-3xl">
            Roota
          </h1>
          <p className="mt-1 max-w-xl text-sm text-ink-500 sm:text-base">
            Stateful fault isolation for industrial drives
          </p>
        </div>
        <span className="hidden rounded border border-ink-200 px-2.5 py-1 text-xs font-medium uppercase tracking-wide text-ink-400 sm:inline">
          MVP
        </span>
      </div>
    </header>
  );
}
