interface ErrorBannerProps {
  message: string;
  onDismiss?: () => void;
}

export function ErrorBanner({ message, onDismiss }: ErrorBannerProps) {
  return (
    <div
      role="alert"
      className="rounded-[4px] border border-hud-escalated/40 bg-hud-surface px-3 py-2 text-14 text-hud-text"
    >
      <div className="flex items-start justify-between gap-3">
        <p className="min-w-0 flex-1 break-words">{message}</p>
        {onDismiss ? (
          <button
            type="button"
            className="shrink-0 font-mono text-12 uppercase tracking-label text-hud-muted underline"
            onClick={onDismiss}
          >
            Dismiss
          </button>
        ) : null}
      </div>
    </div>
  );
}
