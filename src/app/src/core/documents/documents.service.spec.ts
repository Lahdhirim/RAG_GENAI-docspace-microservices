import { TestBed } from "@angular/core/testing";
import { provideHttpClient } from "@angular/common/http";
import {
  HttpTestingController,
  provideHttpClientTesting,
} from "@angular/common/http/testing";
import { firstValueFrom } from "rxjs";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { DocumentsService } from "./documents.service";
import { DocumentRecord } from "./document.model";
const document: DocumentRecord = {
  id: "abc",
  filename: "Rapport.pdf",
  relative_path: "reports/Rapport.pdf",
  extension: ".pdf",
  content_hash: "def",
  size_bytes: 1024,
  is_present: false,
  is_parsed: true,
  file_created_at: null,
  file_modified_at: "2026-07-11T12:00:00",
  file_accessed_at: null,
  created_at: null,
  updated_at: null,
};
describe("DocumentsService API contract", () => {
  let api: DocumentsService;
  let http: HttpTestingController;
  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    api = TestBed.inject(DocumentsService);
    http = TestBed.inject(HttpTestingController);
  });
  afterEach(() => {
    http.verify();
    vi.useRealTimers();
  });
  it("uses only GET /documents and preserves the FastAPI fields", async () => {
    const result = firstValueFrom(api.list());
    const request = http.expectOne("/documents");
    expect(request.request.method).toBe("GET");
    request.flush({ documents: [document] });
    await expect(result).resolves.toEqual([document]);
  });
  it("accepts an empty library", async () => {
    const result = firstValueFrom(api.list());
    http.expectOne("/documents").flush({ documents: [] });
    await expect(result).resolves.toEqual([]);
  });
  it.each([
    {},
    { documents: null },
    { documents: [null] },
    { documents: [{ ...document, size_bytes: -1 }] },
    { documents: [{ ...document, is_present: 1 }] },
    { documents: [{ ...document, file_modified_at: "invalid" }] },
  ])("rejects malformed response %j", async (payload) => {
    const result = firstValueFrom(api.list());
    http.expectOne("/documents").flush(payload);
    await expect(result).rejects.toThrow(
      "Le format de la réponse est invalide.",
    );
  });
  it("propagates backend errors", async () => {
    const result = firstValueFrom(api.list());
    http
      .expectOne("/documents")
      .flush({}, { status: 500, statusText: "Error" });
    await expect(result).rejects.toMatchObject({ status: 500 });
  });
  it("times out and cancels a stalled request after 15 seconds", async () => {
    vi.useFakeTimers();
    const result = firstValueFrom(api.list());
    const rejected = expect(result).rejects.toMatchObject({
      name: "TimeoutError",
    });
    const request = http.expectOne("/documents");
    await vi.advanceTimersByTimeAsync(15000);
    await rejected;
    expect(request.cancelled).toBe(true);
  });
});
