export const JOB_STATUSES = [
  "QUEUED",
  "NOT_FOUND",
  "RUNNING",
  "COMPLETED",
  "FAILED",
  "NOT_STARTED",
  "UNKNOWN",
] as const;
export type JobStatus = (typeof JOB_STATUSES)[number];
export interface ParsingJob {
  job_id: string;
  document_id: string;
  filename: string | null;
  relative_path: string | null;
  submitted_at: string;
  status: JobStatus;
  started_at: string | null;
  finished_at: string | null;
  waiting_duration: number | null;
  execution_duration: number | null;
  error: string | null;
}
export function isJobsResponse(
  value: unknown,
): value is { jobs: ParsingJob[] } {
  if (
    !value ||
    typeof value !== "object" ||
    !("jobs" in value) ||
    !Array.isArray(value.jobs)
  )
    return false;
  return value.jobs.every((item: unknown) => {
    if (!item || typeof item !== "object") return false;
    const j = item as Record<string, unknown>;
    return (
      ["job_id", "document_id"].every((k) => typeof j[k] === "string") &&
      JOB_STATUSES.includes(j["status"] as JobStatus) &&
      typeof j["submitted_at"] === "string" &&
      Number.isFinite(Date.parse(j["submitted_at"])) &&
      ["started_at", "finished_at"].every(
        (k) =>
          j[k] === null ||
          (typeof j[k] === "string" && Number.isFinite(Date.parse(j[k]))),
      ) &&
      ["filename", "relative_path", "error"].every(
        (k) => j[k] === null || typeof j[k] === "string",
      ) &&
      ["waiting_duration", "execution_duration"].every(
        (k) =>
          j[k] === null || (typeof j[k] === "number" && Number.isFinite(j[k])),
      )
    );
  });
}
export function statusLabel(value: string): string {
  return value
    .toLowerCase()
    .replaceAll("_", " ")
    .replace(/^./, (c) => c.toUpperCase());
}
