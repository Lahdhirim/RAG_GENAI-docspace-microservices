export function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const unit = Math.max(
    0,
    Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), 3),
  );
  return `${new Intl.NumberFormat("en-US", { maximumFractionDigits: unit === 0 ? 0 : 1 }).format(bytes / 1024 ** unit)} ${["B", "KiB", "MiB", "GiB"][unit]}`;
}
export function formatDate(value: string | null): string {
  if (!value) return "—";
  return new Intl.DateTimeFormat("en-US", { dateStyle: "medium" }).format(
    new Date(value),
  );
}
