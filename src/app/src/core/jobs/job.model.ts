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
  filename: string;
  status: JobStatus;
  submitted_at: string;
  started_at: string | null;
  finished_at: string | null;
  waiting_duration: number | null;
  execution_duration: number | null;
  error: string | null;
  silver_relative_path: string | null;
}
/**
 * Validate and map the positional /parsing_statuses SQL projection.
 * Accept the original ten columns and the added eleventh Markdown-path column.
 */
export function parseStatusesResponse(value: unknown): ParsingJob[] {
  if (
    !value ||
    typeof value !== "object" ||
    !("statuses" in value) ||
    !Array.isArray(value.statuses)
  )
    throw new Error("The parsing statuses response format is invalid.");
  return value.statuses.map((row: unknown) => {
    if (
      !Array.isArray(row) ||
      ![10, 11].includes(row.length) ||
      ![0, 1, 2].every((i) => typeof row[i] === "string") ||
      !JOB_STATUSES.includes(row[3]) ||
      typeof row[4] !== "string" ||
      !Number.isFinite(Date.parse(row[4])) ||
      ![5, 6].every(
        (i) =>
          row[i] === null ||
          (typeof row[i] === "string" && Number.isFinite(Date.parse(row[i]))),
      ) ||
      ![7, 8].every(
        (i) =>
          row[i] === null ||
          (typeof row[i] === "number" && Number.isFinite(row[i])),
      ) ||
      !(row[9] === null || typeof row[9] === "string") ||
      !(
        row[10] === undefined ||
        row[10] === null ||
        typeof row[10] === "string"
      )
    )
      throw new Error("The parsing statuses response format is invalid.");
    return {
      job_id: row[0],
      document_id: row[1],
      filename: row[2],
      status: row[3],
      submitted_at: row[4],
      started_at: row[5],
      finished_at: row[6],
      waiting_duration: row[7],
      execution_duration: row[8],
      error: row[9],
      silver_relative_path: row[10] ?? null,
    };
  });
}
export function statusLabel(value: string): string {
  return value
    .toLowerCase()
    .replaceAll("_", " ")
    .replace(/^./, (c) => c.toUpperCase());
}
