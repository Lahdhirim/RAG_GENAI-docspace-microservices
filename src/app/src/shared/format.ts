export function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 o";
  const unit = Math.max(
    0,
    Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), 3),
  );
  return `${new Intl.NumberFormat("fr-FR", { maximumFractionDigits: unit === 0 ? 0 : 1 }).format(bytes / 1024 ** unit)} ${["o", "Ko", "Mo", "Go"][unit]}`;
}
export function formatDate(value: string | null): string {
  if (!value) return "—";
  return new Intl.DateTimeFormat("fr-FR", { dateStyle: "medium" }).format(
    new Date(value),
  );
}
