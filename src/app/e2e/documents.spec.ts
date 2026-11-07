import { test, expect } from "@playwright/test";
const records = Array.from({ length: 12 }, (_, i) => ({
  id: `document-${i}`,
  filename: `Document ${i + 1}.pdf`,
  relative_path: `reports/Document ${i + 1}.pdf`,
  extension: i === 11 ? ".txt" : ".pdf",
  content_hash: "a".repeat(64),
  size_bytes: (i + 1) * 1024,
  is_present: i !== 11,
  is_parsed: i === 0,
  file_created_at: null,
  file_modified_at: i ? "2026-07-11T12:00:00" : null,
  file_accessed_at: null,
  created_at: "2026-07-11T12:00:00",
  updated_at: "2026-07-11T12:00:00",
}));
test("documents, local filters, sorting, pagination, metadata and responsive layout", async ({
  page,
}, testInfo) => {
  const calls: string[] = [];
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.route("**/documents", async (route) => {
    if (
      route.request().resourceType() !== "xhr" &&
      route.request().resourceType() !== "fetch"
    )
      return route.continue();
    calls.push(route.request().method());
    await route.fulfill({ json: { documents: records } });
  });
  await page.goto("/documents");
  await expect(
    page.getByRole("heading", { name: /Document library/ }),
  ).toBeVisible();
  await expect(page.locator("tbody tr")).toHaveCount(10);
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  await expect(page.locator("tbody tr").first()).toContainText("1 KiB");
  await expect(page.locator("tbody tr").nth(1)).toContainText("Jul 11, 2026");
  await page.screenshot({
    path: testInfo.outputPath("library.png"),
    fullPage: true,
  });
  await expect(page.getByText("Page 1 / 2")).toBeVisible();
  await page.getByRole("button", { name: "Next page" }).click();
  await expect(page.locator("tbody tr")).toHaveCount(2);
  await page.getByRole("searchbox").fill("Document 12");
  await expect(page.locator("tbody tr")).toHaveCount(1);
  await expect(page.getByText("Page 1 / 1")).toBeVisible();
  await page.getByRole("searchbox").fill("");
  await page
    .getByRole("combobox", { name: "Availability", exact: true })
    .selectOption("absent");
  await expect(page.locator("tbody tr")).toHaveCount(1);
  await page
    .getByRole("button", { name: "Document 12.pdf", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(
    page.getByRole("dialog").getByText("a".repeat(64)),
  ).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).not.toBeVisible();
  await page
    .getByRole("combobox", { name: "Availability", exact: true })
    .selectOption("all");
  await page
    .getByRole("combobox", { name: "File type", exact: true })
    .selectOption(".txt");
  await expect(page.locator("tbody tr")).toHaveCount(1);
  await page
    .getByRole("combobox", { name: "File type", exact: true })
    .selectOption("all");
  await page
    .getByRole("combobox", { name: "Sort documents", exact: true })
    .selectOption("size");
  await expect(page.locator("tbody tr").first()).toContainText(
    "Document 12.pdf",
  );
  await page.getByRole("searchbox").fill("introuvable");
  await expect(page.getByText("No matching documents")).toBeVisible();
  await page.getByRole("button", { name: "Reset filters" }).click();
  await expect(page.locator("tbody tr")).toHaveCount(10);
  expect(calls).toEqual(["GET"]);
  await page.getByRole("button", { name: "Refresh", exact: true }).click();
  await expect(page.locator("tbody tr")).toHaveCount(10);
  expect(calls).toEqual(["GET", "GET"]);
  await expect(page.getByRole("button", { name: /OpenSearch/ })).toBeDisabled();
  expect(
    await page.evaluate(
      () =>
        document.documentElement.scrollWidth <=
        document.documentElement.clientWidth,
    ),
  ).toBe(true);
  expect(errors).toEqual([]);
});
test("loading, HTTP failure and retry to empty state", async ({ page }) => {
  let finish!: () => void;
  const pending = new Promise<void>((resolve) => {
    finish = resolve;
  });
  let attempt = 0;
  await page.route("**/documents", async (route) => {
    if (!["xhr", "fetch"].includes(route.request().resourceType()))
      return route.continue();
    if (++attempt === 1) {
      await pending;
      await route.fulfill({ status: 503, json: { detail: "Unavailable" } });
    } else await route.fulfill({ json: { documents: [] } });
  });
  await page.goto("/documents");
  await expect(page.getByText("Loading your library")).toBeVisible();
  finish();
  await expect(page.getByRole("alert")).toContainText("HTTP 503");
  await page.getByRole("button", { name: "Try again" }).click();
  await expect(page.getByText("Your library is empty")).toBeVisible();
});
test("invalid API payload is reported instead of silently showing an empty library", async ({
  page,
}) => {
  await page.route("**/documents", async (route) => {
    if (!["xhr", "fetch"].includes(route.request().resourceType()))
      return route.continue();
    await route.fulfill({
      json: { documents: [{ file_name: "wrong contract" }] },
    });
  });
  await page.goto("/documents");
  await expect(page.getByRole("alert")).toContainText(
    "The response format is invalid.",
  );
});
