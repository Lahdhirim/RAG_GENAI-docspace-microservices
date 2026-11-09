import { TestBed } from "@angular/core/testing";
import { provideHttpClient } from "@angular/common/http";
import {
  HttpTestingController,
  provideHttpClientTesting,
} from "@angular/common/http/testing";
import { firstValueFrom } from "rxjs";
import { beforeEach, afterEach, describe, it, expect, vi } from "vitest";
import { JobsService } from "./jobs.service";
import { JOB_STATUSES, ParsingJob } from "./job.model";
const job: ParsingJob = {
  job_id: "job-1",
  document_id: "doc-1",
  filename: "Report.pdf",
  relative_path: "reports/Report.pdf",
  submitted_at: "2026-11-09T10:30:00",
  status: "QUEUED",
  started_at: null,
  finished_at: null,
  waiting_duration: 0,
  execution_duration: null,
  error: null,
};
describe("JobsService", () => {
  let api: JobsService;
  let http: HttpTestingController;
  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    api = TestBed.inject(JobsService);
    http = TestBed.inject(HttpTestingController);
  });
  afterEach(() => {
    http.verify();
    vi.useRealTimers();
  });
  it("reads all SQL job statuses through Document Manager", async () => {
    const result = firstValueFrom(api.list());
    const request = http.expectOne("/jobs");
    expect(request.request.method).toBe("GET");
    const jobs = JOB_STATUSES.map((status) => ({ ...job, status }));
    request.flush({ jobs });
    await expect(result).resolves.toEqual(jobs);
  });
  it("encodes the document filter as a query parameter", async () => {
    const result = firstValueFrom(api.list("doc & 1"));
    const request = http.expectOne(
      (r) => r.url === "/jobs" && r.params.get("document_id") === "doc & 1",
    );
    request.flush({ jobs: [] });
    await expect(result).resolves.toEqual([]);
  });
  it("accepts absent joined metadata and zero durations", async () => {
    const result = firstValueFrom(api.list());
    http
      .expectOne("/jobs")
      .flush({ jobs: [{ ...job, filename: null, relative_path: null }] });
    await expect(result).resolves.toMatchObject([
      { waiting_duration: 0, filename: null },
    ]);
  });
  it.each([
    {},
    { jobs: null },
    { jobs: [null] },
    { jobs: [{ ...job, status: "INVENTED" }] },
    { jobs: [{ ...job, submitted_at: "bad date" }] },
    { jobs: [{ ...job, execution_duration: "10" }] },
  ])("rejects invalid jobs response %j", async (payload) => {
    const result = firstValueFrom(api.list());
    http.expectOne("/jobs").flush(payload);
    await expect(result).rejects.toThrow(
      "The jobs response format is invalid.",
    );
  });
  it("propagates a backend failure", async () => {
    const result = firstValueFrom(api.list());
    http
      .expectOne("/jobs")
      .flush({}, { status: 503, statusText: "Unavailable" });
    await expect(result).rejects.toMatchObject({ status: 503 });
  });
  it("cancels a stalled job request after 15 seconds", async () => {
    vi.useFakeTimers();
    const result = firstValueFrom(api.list());
    const rejected = expect(result).rejects.toMatchObject({
      name: "TimeoutError",
    });
    const request = http.expectOne("/jobs");
    await vi.advanceTimersByTimeAsync(15000);
    await rejected;
    expect(request.cancelled).toBe(true);
  });
});
