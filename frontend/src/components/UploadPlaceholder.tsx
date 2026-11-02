type UploadPlaceholderProps = {
  title: string;
  description: string;
};

export function UploadPlaceholder({ title, description }: UploadPlaceholderProps) {
  return (
    <div className="flex min-h-[160px] flex-col justify-between rounded-md border border-dashed border-ink-300 bg-white p-5">
      <div>
        <h3 className="text-base font-semibold text-ink-900">{title}</h3>
        <p className="mt-1 text-sm text-ink-500">{description}</p>
      </div>
      <div className="mt-6">
        <button
          type="button"
          disabled
          className="rounded border border-ink-200 bg-ink-50 px-3 py-1.5 text-sm font-medium text-ink-400"
        >
          Upload coming soon
        </button>
      </div>
    </div>
  );
}
