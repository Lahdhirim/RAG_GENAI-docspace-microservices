import {
  Component,
  computed,
  DestroyRef,
  ElementRef,
  inject,
  signal,
  viewChild,
} from "@angular/core";
import { takeUntilDestroyed } from "@angular/core/rxjs-interop";
import { HttpErrorResponse } from "@angular/common/http";
import { ActivatedRoute, RouterLink } from "@angular/router";
import { FormsModule } from "@angular/forms";
import { Subject, catchError, of, switchMap, tap } from "rxjs";
import { JobsService } from "../../core/jobs/jobs.service";
import {
  JOB_STATUSES,
  ParsingJob,
  statusLabel,
} from "../../core/jobs/job.model";
@Component({
  selector: "app-jobs",
  imports: [FormsModule, RouterLink],
  templateUrl: "./jobs.component.html",
  styleUrls: ["../../shared/workspace.css", "./jobs.component.css"],
})
export class JobsComponent {
  private readonly api = inject(JobsService);
  private readonly route = inject(ActivatedRoute);
  private readonly destroyRef = inject(DestroyRef);
  private readonly refresh = new Subject<string | null>();
  readonly jobs = signal<ParsingJob[]>([]);
  readonly loading = signal(false);
  readonly loaded = signal(false);
  readonly error = signal("");
  readonly refreshedAt = signal("");
  readonly documentId = signal<string | null>(null);
  readonly query = signal("");
  readonly status = signal("all");
  readonly page = signal(1);
  readonly pageSize = 10;
  readonly statuses = JOB_STATUSES;
  readonly end = computed(() =>
    Math.min(this.page() * this.pageSize, this.filtered().length),
  );
  readonly label = statusLabel;
  readonly selected = signal<ParsingJob | null>(null);
  readonly dialog = viewChild<ElementRef<HTMLDialogElement>>("details");
  readonly active = computed(
    () =>
      this.jobs().filter((j) => ["QUEUED", "RUNNING"].includes(j.status))
        .length,
  );
  readonly completed = computed(
    () => this.jobs().filter((j) => j.status === "COMPLETED").length,
  );
  readonly attention = computed(
    () =>
      this.jobs().filter((j) =>
        ["FAILED", "NOT_FOUND", "UNKNOWN"].includes(j.status),
      ).length,
  );
  readonly filtered = computed(() =>
    this.jobs().filter(
      (j) =>
        (this.status() === "all" || j.status === this.status()) &&
        `${j.filename ?? ""} ${j.relative_path ?? ""} ${j.job_id} ${j.document_id}`
          .toLowerCase()
          .includes(this.query().trim().toLowerCase()),
    ),
  );
  readonly pageCount = computed(() =>
    Math.max(1, Math.ceil(this.filtered().length / this.pageSize)),
  );
  readonly visible = computed(() =>
    this.filtered().slice(
      (this.page() - 1) * this.pageSize,
      this.page() * this.pageSize,
    ),
  );
  constructor() {
    this.refresh
      .pipe(
        tap(() => {
          this.loading.set(true);
          this.error.set("");
        }),
        switchMap((id) =>
          this.api.list(id).pipe(
            tap((jobs) => {
              this.jobs.set(jobs);
              this.loaded.set(true);
              this.page.set(1);
              this.refreshedAt.set(
                new Intl.DateTimeFormat("en-US", { timeStyle: "short" }).format(
                  new Date(),
                ),
              );
            }),
            catchError((error: unknown) => {
              this.error.set(
                error instanceof HttpErrorResponse
                  ? error.status === 0
                    ? "Document Manager is unreachable. Check the service and try again."
                    : `Document Manager returned an error (HTTP ${error.status}).`
                  : error instanceof Error &&
                      error.message === "The jobs response format is invalid."
                    ? error.message
                    : "The request timed out. Please try again.",
              );
              return of(null);
            }),
          ),
        ),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe(() => this.loading.set(false));
    this.route.queryParamMap
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe((params) => {
        this.documentId.set(params.get("document"));
        this.page.set(1);
        this.jobs.set([]);
        this.loaded.set(false);
        this.refresh.next(this.documentId());
      });
  }
  load(): void {
    if (!this.loading()) this.refresh.next(this.documentId());
  }
  filter(field: "query" | "status", value: string): void {
    this[field].set(value);
    this.page.set(1);
  }
  reset(): void {
    this.query.set("");
    this.status.set("all");
    this.page.set(1);
  }
  timestamp(value: string | null): string {
    return value
      ? new Intl.DateTimeFormat("en-US", {
          dateStyle: "medium",
          timeStyle: "medium",
        }).format(new Date(value))
      : "—";
  }
  duration(value: number | null): string {
    return value === null
      ? "—"
      : `${new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 }).format(value)} s`;
  }
  openDetails(job: ParsingJob): void {
    this.selected.set(job);
    this.dialog()?.nativeElement.showModal();
  }
  closeDetails(): void {
    this.dialog()?.nativeElement.close();
    this.selected.set(null);
  }
}
