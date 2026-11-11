/** Contract returned by FastAPI's Document model on feat/parser-service. */
export interface DocumentRecord {
  id: string;
  relative_path: string;
  filename: string;
  extension: string;
  content_hash: string;
  size_bytes: number;
  file_created_at: string | null;
  file_modified_at: string | null;
  file_accessed_at: string | null;
  is_present: boolean;
  is_parsed: boolean;
  submission_status?: "NOT_SUBMITTED" | "SUBMITTED" | "FAILED";
  submission_error?: string | null;
  created_at: string | null;
  updated_at: string | null;
}
export interface DocumentsResponse {
  documents: DocumentRecord[];
}
export function isDocumentsResponse(
  value: unknown,
): value is DocumentsResponse {
  if (
    !value ||
    typeof value !== "object" ||
    !("documents" in value) ||
    !Array.isArray(value.documents)
  )
    return false;
  return value.documents.every((doc: unknown) => {
    if (!doc || typeof doc !== "object") return false;
    const row = doc as Record<string, unknown>;
    const strings = [
      "id",
      "relative_path",
      "filename",
      "extension",
      "content_hash",
    ];
    const dates = [
      "file_created_at",
      "file_modified_at",
      "file_accessed_at",
      "created_at",
      "updated_at",
    ];
    return (
      strings.every((key) => typeof row[key] === "string") &&
      typeof row["size_bytes"] === "number" &&
      Number.isFinite(row["size_bytes"]) &&
      row["size_bytes"] >= 0 &&
      typeof row["is_present"] === "boolean" &&
      typeof row["is_parsed"] === "boolean" &&
      (row["submission_status"] === undefined ||
        ["NOT_SUBMITTED", "SUBMITTED", "FAILED"].includes(
          row["submission_status"] as string,
        )) &&
      (row["submission_error"] === undefined ||
        row["submission_error"] === null ||
        typeof row["submission_error"] === "string") &&
      dates.every(
        (key) =>
          row[key] === null ||
          (typeof row[key] === "string" &&
            Number.isFinite(Date.parse(row[key]))),
      )
    );
  });
}
