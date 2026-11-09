import { test, expect } from "@playwright/test";
const statuses = [
  "QUEUED",
  "RUNNING",
  "COMPLETED",
  "FAILED",
  "NOT_STARTED",
  "NOT_FOUND",
  "UNKNOWN",
];
const jobs = Array.from({ length: 12 }, (_, i) => ({
  job_id: `job-${i + 1}`,
  document_id: `doc-${i + 1}`,
  filename: `Report ${i + 1}.pdf`,
  relative_path: `reports/Report ${i + 1}.pdf`,
  submitted_at: "2026-11-09T10:30:00",
  status: statuses[i % statuses.length],
  started_at: i ? "2026-11-09T10:30:01" : null,
  finished_at: i === 2 ? "2026-11-09T10:30:02" : null,
  waiting_duration: 0,
  execution_duration: i === 2 ? 1.25 : null,
  error:
    i === 3
      ? '<script>throw new Error("unsafe")</script>\nParser unavailable'
      : null,
}));
test("monitor jobs, filter all statuses, inspect errors and paginate without parser calls", async ({
  page,
}, testInfo) => {
  const calls: string[] = [];
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("request", (request) => {
    if (["xhr", "fetch"].includes(request.resourceType()))
      calls.push(`${request.method()} ${new URL(request.url()).pathname}`);
  });
  await page.route("**/jobs*", async (route) => {
    await route.fulfill({ json: { jobs } });
  });
  await page.goto("/parsing");
  await expect(
    page.getByRole("heading", { name: /Parsing jobs/ }),
  ).toBeVisible();
  await expect(page.locator(".topbar strong")).toHaveText("Parsing");
  await expect(page.locator("tbody tr")).toHaveCount(10);
  await expect(page.getByText("Page 1 / 2")).toBeVisible();
  await page.screenshot({
    path: testInfo.outputPath("parsing-jobs.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "Next page" }).click();
  await expect(page.locator("tbody tr")).toHaveCount(2);
  await page
    .getByRole("combobox", { name: "Job status" })
    .selectOption("FAILED");
  await expect(page.locator("tbody tr")).toHaveCount(2);
  await expect(page.getByText("Page 1 / 1")).toBeVisible();
  await page.getByRole("button", { name: "Report 4.pdf", exact: true }).click();
  await expect(page.getByRole("dialog")).toContainText("Parser unavailable");
  await expect(page.getByRole("dialog")).toContainText("<script>");
  await expect(page.getByRole("dialog")).toContainText("0 s");
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).not.toBeVisible();
  for (const status of statuses) {
    await page
      .getByRole("combobox", { name: "Job status" })
      .selectOption(status);
    await expect(page.locator("tbody tr")).toHaveCount(
      jobs.filter((j) => j.status === status).length,
    );
  }
  await page.getByRole("combobox", { name: "Job status" }).selectOption("all");
  await page.getByRole("searchbox", { name: "Filter jobs" }).fill("job-12");
  await expect(page.locator("tbody tr")).toHaveCount(1);
  await page.getByRole("searchbox").fill("not-a-document");
  await expect(page.getByText("No matching jobs")).toBeVisible();
  await page.getByRole("button", { name: "Reset filters" }).click();
  await expect(page.locator("tbody tr")).toHaveCount(10);
  expect(calls).toEqual(["GET /jobs"]);
  await page.getByRole("button", { name: "Refresh", exact: true }).click();
  await expect(page.locator("tbody tr")).toHaveCount(10);
  expect(calls).toEqual(["GET /jobs", "GET /jobs"]);
  expect(
    await page.evaluate(
      () =>
        document.documentElement.scrollWidth <=
        document.documentElement.clientWidth,
    ),
  ).toBe(true);
  expect(errors).toEqual([]);
});
test("document submission filters and job history navigation use Document Manager", async ({
  page,
}) => {
  const document = {
    id: "doc-4",
    filename: "Report 4.pdf",
    relative_path: "reports/Report 4.pdf",
    extension: ".pdf",
    content_hash: "hash",
    size_bytes: 1024,
    file_created_at: null,
    file_modified_at: null,
    file_accessed_at: null,
    created_at: null,
    updated_at: null,
    is_present: true,
    is_parsed: false,
    submission_status: "FAILED",
  };
  await page.route("**/documents", async (route) => {
    if (route.request().resourceType() === "document") return route.continue();
    await route.fulfill({ json: { documents: [document] } });
  });
  const requested: string[] = [];
  await page.route("**/jobs*", async (route) => {
    const id = new URL(route.request().url()).searchParams.get("document_id");
    requested.push(id ?? "all");
    await route.fulfill({ json: { jobs: id ? [jobs[3]] : jobs } });
  });
  await page.goto("/documents");
  await page
    .getByRole("combobox", { name: "Submission status" })
    .selectOption("NOT_SUBMITTED");
  await expect(page.getByText("No matching documents")).toBeVisible();
  await page.getByRole("button", { name: "Reset filters" }).click();
  await page.getByRole("button", { name: "Report 4.pdf", exact: true }).click();
  await expect(page.getByRole("dialog")).toContainText("Failed");
  await page.getByRole("link", { name: "View parsing jobs" }).click();
  await expect(page).toHaveURL(/\/parsing\?document=doc-4$/);
  await expect(page.locator("tbody tr")).toHaveCount(1);
  expect(requested).toEqual(["doc-4"]);
  await page.getByRole("link", { name: "Show all jobs" }).click();
  await expect(page.locator("tbody tr")).toHaveCount(10);
  expect(requested).toEqual(["doc-4", "all"]);
  await page.getByRole("link", { name: "Documents", exact: true }).click();
  await expect(page.locator(".topbar strong")).toHaveText("Documents");
});
test("loading, service failure, retry and empty scoped history", async ({
  page,
}) => {
  let finish!: () => void;
  const pending = new Promise<void>((resolve) => {
    finish = resolve;
  });
  let attempts = 0;
  await page.route("**/jobs*", async (route) => {
    if (++attempts === 1) {
      await pending;
      await route.fulfill({ status: 503, json: {} });
    } else await route.fulfill({ json: { jobs: [] } });
  });
  await page.goto("/parsing?document=doc-without-jobs");
  await expect(page.getByText("Loading parsing jobs")).toBeVisible();
  finish();
  await expect(page.getByRole("alert")).toContainText("HTTP 503");
  await page.getByRole("button", { name: "Try again" }).click();
  await expect(
    page.getByText("No jobs have been recorded for this document."),
  ).toBeVisible();
});
test("malformed job data is not presented as a successful empty history", async ({
  page,
}) => {
  await page.route("**/jobs*", (route) =>
    route.fulfill({ json: { jobs: [{ status: "made up" }] } }),
  );
  await page.goto("/parsing");
  await expect(page.getByRole("alert")).toContainText(
    "The jobs response format is invalid.",
  );
});
