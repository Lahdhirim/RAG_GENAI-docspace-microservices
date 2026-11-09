import { test, expect } from "@playwright/test";
const base = {
  relative_path: "report.txt",
  extension: ".txt",
  content_hash: "hash",
  size_bytes: 100,
  is_parsed: false,
  submission_status: "NOT_SUBMITTED",
  file_created_at: null,
  file_modified_at: null,
  file_accessed_at: null,
  created_at: null,
  updated_at: null,
};
const documents = [
  { ...base, id: "present", filename: "present.txt", is_present: true },
  { ...base, id: "absent", filename: "absent.txt", is_present: false },
];
test.beforeEach(async ({ page }) => {
  await page.route("**/documents", async (route) => {
    if (route.request().resourceType() === "document") return route.continue();
    await route.fulfill({ json: { documents } });
  });
});
test("absent documents show the English unavailable message without fetching bytes", async ({
  page,
}) => {
  const calls: string[] = [];
  page.on("request", (r) => {
    if (r.url().includes("/preview")) calls.push(r.url());
  });
  await page.goto("/documents");
  await page
    .getByRole("button", { name: "Preview absent.txt", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toContainText(
    "This document is currently unavailable.",
  );
  expect(calls).toEqual([]);
  await page.getByRole("button", { name: "Close preview" }).click();
  await expect(page.getByRole("dialog")).not.toBeVisible();
});
test("text previews render content as text and support Escape and reopening", async ({
  page,
}) => {
  await page.route("**/documents/present/preview", (route) =>
    route.fulfill({
      contentType: "text/plain; charset=utf-8",
      body: '<script>throw Error("unsafe")</script>\nDocument content',
    }),
  );
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/documents");
  await page
    .getByRole("button", { name: "Preview present.txt", exact: true })
    .click();
  await expect(page.getByRole("dialog").locator("pre")).toContainText(
    "<script>",
  );
  await expect(page.getByRole("dialog")).toContainText("Document content");
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).not.toBeVisible();
  await page.getByRole("button", { name: "present.txt", exact: true }).click();
  await page
    .getByRole("button", { name: "Preview document", exact: true })
    .click();
  await expect(page.getByRole("dialog").locator("pre")).toContainText(
    "Document content",
  );
  expect(errors).toEqual([]);
  expect(
    await page.evaluate(
      () =>
        document.documentElement.scrollWidth <=
        document.documentElement.clientWidth,
    ),
  ).toBe(true);
});
test("PDF previews use a blob URL and release it on close", async ({
  page,
}) => {
  await page.route("**/documents/present/preview", (route) =>
    route.fulfill({ contentType: "application/pdf", body: "%PDF-1.4\n%%EOF" }),
  );
  await page.addInitScript(() => {
    const original = URL.revokeObjectURL.bind(URL);
    (window as unknown as { revoked: string[] }).revoked = [];
    URL.revokeObjectURL = (value) => {
      (window as unknown as { revoked: string[] }).revoked.push(value);
      original(value);
    };
  });
  await page.goto("/documents");
  await page
    .getByRole("button", { name: "Preview present.txt", exact: true })
    .click();
  const frame = page.getByTitle("PDF document preview");
  await expect(frame).toHaveAttribute("src", /^blob:/);
  const url = await frame.getAttribute("src");
  await expect(
    page.getByRole("link", { name: "download the document" }),
  ).toHaveAttribute("href", url!);
  await page.getByRole("button", { name: "Close preview" }).click();
  await expect
    .poll(() =>
      page.evaluate(() => (window as unknown as { revoked: string[] }).revoked),
    )
    .toContain(url);
});
test("image previews decode image bytes", async ({ page }) => {
  const png = Buffer.from(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=",
    "base64",
  );
  await page.route("**/documents/present/preview", (route) =>
    route.fulfill({ contentType: "image/png", body: png }),
  );
  await page.goto("/documents");
  await page
    .getByRole("button", { name: "Preview present.txt", exact: true })
    .click();
  await expect(
    page.getByRole("img", { name: "Preview of present.txt" }),
  ).toBeVisible();
  await expect
    .poll(() =>
      page
        .getByRole("img")
        .evaluate((image) => (image as HTMLImageElement).naturalWidth),
    )
    .toBe(1);
});
test("missing files, unsupported formats and retryable errors have clear messages", async ({
  page,
}) => {
  let status = 404;
  await page.route("**/documents/present/preview", (route) =>
    status === 200
      ? route.fulfill({ contentType: "text/plain", body: "Recovered document" })
      : route.fulfill({ status, json: { detail: "Server detail" } }),
  );
  await page.goto("/documents");
  const open = () =>
    page
      .getByRole("button", { name: "Preview present.txt", exact: true })
      .click();
  const close = () =>
    page.getByRole("button", { name: "Close preview" }).click();
  await open();
  await expect(page.getByRole("dialog")).toContainText(
    "This document is currently unavailable.",
  );
  await close();
  status = 415;
  await open();
  await expect(page.getByRole("dialog")).toContainText(
    "Preview is not supported for this file type.",
  );
  await close();
  status = 413;
  await open();
  await expect(page.getByRole("dialog")).toContainText(
    "This document is too large to preview",
  );
  await close();
  status = 503;
  await open();
  await expect(page.getByRole("dialog")).toContainText(
    "Unable to load the preview. Please try again.",
  );
  status = 200;
  await page.getByRole("button", { name: "Try again" }).click();
  await expect(page.getByRole("dialog")).toContainText("Recovered document");
});
