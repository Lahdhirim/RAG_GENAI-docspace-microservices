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
import { FormsModule } from "@angular/forms";
import { DocumentsService } from "../../core/documents/documents.service";
import { DocumentRecord } from "../../core/documents/document.model";
import { formatBytes, formatDate } from "../../shared/format";
@Component({
  selector: "app-documents",
  imports: [FormsModule],
  templateUrl: "./documents.component.html",
  styleUrl: "./documents.component.css",
})
export class DocumentsComponent {
  private readonly api = inject(DocumentsService);
  private readonly destroyRef = inject(DestroyRef);
  readonly documents = signal<DocumentRecord[]>([]);
  readonly loading = signal(false);
  readonly error = signal("");
  readonly loaded = signal(false);
  readonly refreshedAt = signal<string | null>(null);
  readonly query = signal("");
  readonly presence = signal("all");
  readonly type = signal("all");
  readonly sort = signal("name");
  readonly page = signal(1);
  readonly pageSize = 10;
  readonly selected = signal<DocumentRecord | null>(null);
  readonly dialog = viewChild<ElementRef<HTMLDialogElement>>("details");
  readonly bytes = formatBytes;
  readonly date = formatDate;
  readonly presentCount = computed(
    () => this.documents().filter((d) => d.is_present).length,
  );
  readonly totalBytes = computed(() =>
    this.documents().reduce((sum, d) => sum + d.size_bytes, 0),
  );
  readonly types = computed(() =>
    [...new Set(this.documents().map((d) => d.extension))].sort(),
  );
  readonly filtered = computed(() => {
    const query = this.query().trim().toLocaleLowerCase("en");
    return this.documents()
      .filter(
        (d) =>
          (!query ||
            `${d.filename} ${d.relative_path}`
              .toLocaleLowerCase("en")
              .includes(query)) &&
          (this.presence() === "all" ||
            d.is_present === (this.presence() === "present")) &&
          (this.type() === "all" || d.extension === this.type()),
      )
      .sort((a, b) => {
        if (this.sort() === "size")
          return b.size_bytes - a.size_bytes || a.id.localeCompare(b.id);
        if (this.sort() === "modified")
          return (
            (Date.parse(b.file_modified_at ?? "") || 0) -
              (Date.parse(a.file_modified_at ?? "") || 0) ||
            a.id.localeCompare(b.id)
          );
        return (
          a.filename.localeCompare(b.filename, "en", { numeric: true }) ||
          a.id.localeCompare(b.id)
        );
      });
  });
  readonly pageCount = computed(() =>
    Math.max(1, Math.ceil(this.filtered().length / this.pageSize)),
  );
  readonly visible = computed(() =>
    this.filtered().slice(
      (this.page() - 1) * this.pageSize,
      this.page() * this.pageSize,
    ),
  );
  readonly start = computed(() =>
    this.filtered().length ? (this.page() - 1) * this.pageSize + 1 : 0,
  );
  readonly end = computed(() =>
    Math.min(this.page() * this.pageSize, this.filtered().length),
  );
  constructor() {
    this.load();
  }
  load(): void {
    if (this.loading()) return;
    this.loading.set(true);
    this.error.set("");
    this.api
      .list()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (documents) => {
          this.documents.set(documents);
          this.page.set(1);
          this.loaded.set(true);
          if (this.type() !== "all" && !this.types().includes(this.type()))
            this.type.set("all");
          this.refreshedAt.set(
            new Intl.DateTimeFormat("en-US", { timeStyle: "short" }).format(
              new Date(),
            ),
          );
          this.loading.set(false);
        },
        error: (error: unknown) => {
          this.loading.set(false);
          this.error.set(
            error instanceof HttpErrorResponse
              ? error.status === 0
                ? "The document service is unreachable. Check its availability and try again."
                : `The document service returned an error (HTTP ${error.status}).`
              : error instanceof Error &&
                  error.message === "The response format is invalid."
                ? error.message
                : "The request timed out. Please try again shortly.",
          );
        },
      });
  }
  filter(field: "query" | "presence" | "type" | "sort", value: string): void {
    this[field].set(value);
    this.page.set(1);
  }
  reset(): void {
    this.query.set("");
    this.presence.set("all");
    this.type.set("all");
    this.page.set(1);
  }
  openDetails(document: DocumentRecord): void {
    this.selected.set(document);
    this.dialog()?.nativeElement.showModal();
  }
  closeDetails(): void {
    this.dialog()?.nativeElement.close();
    this.selected.set(null);
  }
}
