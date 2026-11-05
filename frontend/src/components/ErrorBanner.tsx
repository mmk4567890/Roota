interface ErrorBannerProps {
  message: string;
  onDismiss?: () => void;
}

export function ErrorBanner({ message, onDismiss }: ErrorBannerProps) {
  return (
    <div
      role="alert"
      className="rounded-md border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-900"
    >
      <div className="flex items-start justify-between gap-3">
        <p className="min-w-0 flex-1 break-words">{message}</p>
        {onDismiss ? (
          <button
            type="button"
            className="shrink-0 text-xs font-medium uppercase tracking-wide text-red-700 underline"
            onClick={onDismiss}
          >
            Dismiss
          </button>
        ) : null}
      </div>
    </div>
  );
}
