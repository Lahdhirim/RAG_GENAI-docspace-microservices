import {
  afterNextRender,
  Component,
  DestroyRef,
  ElementRef,
  inject,
  input,
  output,
  signal,
  viewChild,
} from "@angular/core";
import { HttpErrorResponse } from "@angular/common/http";
import { takeUntilDestroyed } from "@angular/core/rxjs-interop";
import { DomSanitizer, SafeResourceUrl } from "@angular/platform-browser";
import { Subscription } from "rxjs";
import { renderMarkdown } from "../../core/documents/markdown";
import { DocumentsService } from "../../core/documents/documents.service";
import { DocumentRecord } from "../../core/documents/document.model";
@Component({
  selector: "app-document-preview",
  template: `
    <dialog
      #dialog
      aria-labelledby="preview-title"
      class="preview-dialog"
      (close)="closed.emit()"
    >
      <div class="dialog-heading">
        <div>
          <p class="eyebrow">
            {{
              currentKind() === "original"
                ? "ORIGINAL DOCUMENT"
                : "MARKDOWN PREVIEW"
            }}
          </p>
          <h2 id="preview-title">{{ document().filename }}</h2>
        </div>
        <button class="button" (click)="close()" aria-label="Close preview">
          ✕
        </button>
      </div>
      <div style="display:flex;gap:10px;flex-wrap:wrap">
        <button
          class="button"
          [attr.aria-pressed]="currentKind() === 'original'"
          (click)="changeKind('original')"
        >
          Original</button
        ><button
          class="button"
          [attr.aria-pressed]="currentKind() === 'markdown'"
          (click)="changeKind('markdown')"
        >
          Markdown
        </button>
      </div>
      @if (loading()) {
        <div class="preview-state" role="status">Loading document preview…</div>
      } @else if (error()) {
        <div class="preview-state" role="status">
          <p>{{ error() }}</p>
          @if (retryable()) {
            <button class="button" (click)="load()">Try again</button>
          }
        </div>
      } @else if (pdfUrl()) {
        <iframe
          [src]="pdfUrl()"
          title="PDF document preview"
          referrerpolicy="no-referrer"
        ></iframe>
        <p class="preview-help">
          If your browser cannot display this PDF,
          <a [href]="objectUrl()" [download]="downloadName()"
            >download the document</a
          >
          to view it.
        </p>
      } @else if (kind() === "markdown") {
        <div style="display:flex;gap:10px">
          <button
            class="button"
            (click)="source.set(false)"
            [attr.aria-pressed]="!source()"
          >
            Rendered</button
          ><button
            class="button"
            (click)="source.set(true)"
            [attr.aria-pressed]="source()"
          >
            Source
          </button>
        </div>
        @if (source()) {
          <pre class="markdown-source">{{ text() }}</pre>
        } @else {
          <article class="markdown-preview" [innerHTML]="markdown()"></article>
        }
      }
    </dialog>
  `,
  styles: [
    `
      .preview-dialog {
        width: min(1100px, calc(100vw - 32px));
        max-width: 1100px;
        height: 85vh;
        display: flex;
        flex-direction: column;
        gap: 20px;
      }
      .preview-dialog:not([open]) {
        display: none;
      }
      .preview-dialog iframe {
        width: 100%;
        flex: 1;
        min-height: 200px;
        border: 1px solid #dce5e9;
        border-radius: 6px;
      }
      .preview-state {
        display: flex;
        align-items: center;
        justify-content: center;
        flex-direction: column;
        flex: 1;
        text-align: center;
        color: #607285;
        line-height: 1.7;
      }
      .markdown-source {
        flex: 1;
        overflow: auto;
        white-space: pre-wrap;
        overflow-wrap: anywhere;
        margin: 0;
        background: #f6f8fb;
        padding: 18px;
        border-radius: 6px;
        line-height: 1.6;
        font-size: 13px;
      }
      .markdown-preview {
        flex: 1;
        overflow: auto;
        line-height: 1.7;
        overflow-wrap: anywhere;
        padding: 18px;
        border: 1px solid #dce5e9;
        border-radius: 6px;
      }
      :host ::ng-deep .markdown-preview pre {
        white-space: pre-wrap;
        overflow-wrap: anywhere;
        background: #f6f8fb;
        padding: 12px;
        border-radius: 6px;
      }
      :host ::ng-deep .markdown-preview table {
        border-collapse: collapse;
        width: 100%;
      }
      :host ::ng-deep .markdown-preview th,
      :host ::ng-deep .markdown-preview td {
        border: 1px solid #dce5e9;
        padding: 8px;
        text-align: left;
      }
      .preview-help {
        margin: 0;
        font-size: 12px;
        line-height: 1.6;
        color: #607285;
      }
      .preview-help a {
        text-decoration: underline;
        color: #23705b;
      }
    `,
  ],
})
export class DocumentPreviewComponent {
  readonly document = input.required<DocumentRecord>();
  readonly initialKind = input<"original" | "markdown">("original");
  readonly jobId = input<string>();
  readonly currentKind = signal<"original" | "markdown">("original");
  readonly markdown = signal("");
  readonly source = signal(false);
  private request?: Subscription;
  private version = 0;
  readonly closed = output<void>();
  private readonly api = inject(DocumentsService);
  private readonly sanitizer = inject(DomSanitizer);
  private readonly destroyRef = inject(DestroyRef);
  private readonly dialog =
    viewChild.required<ElementRef<HTMLDialogElement>>("dialog");
  readonly loading = signal(false);
  readonly error = signal("");
  readonly retryable = signal(false);
  readonly objectUrl = signal("");
  readonly pdfUrl = signal<SafeResourceUrl | null>(null);
  readonly kind = signal("");
  readonly text = signal("");
  private disposed = false;
  constructor() {
    afterNextRender(() => {
      this.dialog().nativeElement.showModal();
      this.currentKind.set(this.initialKind());
      this.load();
    });
    this.destroyRef.onDestroy(() => {
      this.disposed = true;
      this.version++;
      this.releaseUrl();
    });
  }
  downloadName(): string {
    const doc = this.document();
    return doc.filename.toLowerCase().endsWith(doc.extension.toLowerCase())
      ? doc.filename
      : doc.filename + doc.extension;
  }
  changeKind(kind: "original" | "markdown"): void {
    if (this.currentKind() !== kind) {
      this.currentKind.set(kind);
      this.load();
    }
  }
  private unavailable(): string {
    return this.currentKind() === "original"
      ? "This document is currently unavailable."
      : "Markdown is not available for this document.";
  }
  /** Fetch the selected preview and update its loading and error state. */
  load(): void {
    const version = ++this.version;
    this.request?.unsubscribe();
    this.loading.set(false);
    this.source.set(false);
    this.markdown.set("");
    this.error.set("");
    this.retryable.set(false);
    this.releaseUrl();
    this.kind.set("");
    this.text.set("");
    if (this.currentKind() === "original" && !this.document().is_present) {
      this.error.set(this.unavailable());
      return;
    }
    this.loading.set(true);
    this.request = this.api
      .preview(
        this.document().id,
        this.currentKind(),
        this.currentKind() === "markdown" ? this.jobId() : undefined,
      )
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (blob) => {
          void this.show(blob, version);
        },
        error: (error: unknown) => {
          this.loading.set(false);
          if (
            error instanceof HttpErrorResponse &&
            [404, 410].includes(error.status)
          )
            this.error.set(this.unavailable());
          else if (error instanceof HttpErrorResponse && error.status === 415)
            this.error.set(
              "Only PDF originals and Markdown outputs can be previewed.",
            );
          else if (error instanceof HttpErrorResponse && error.status === 413)
            this.error.set(
              "This document is too large to preview (maximum 50 MiB).",
            );
          else {
            this.error.set("Unable to load the preview. Please try again.");
            this.retryable.set(true);
          }
        },
      });
  }
  /**
   * Display a PDF or decode Markdown for the current preview request.
   * @param blob - File returned by the preview API.
   * @param version - Load version used to ignore stale results.
   * @returns A promise resolved after processing the preview.
   */
  private async show(blob: Blob, version: number): Promise<void> {
    if (this.disposed || version !== this.version) return;
    if (blob.size > 50 * 1024 * 1024) {
      this.loading.set(false);
      this.error.set("This document is too large to preview (maximum 50 MiB).");
      return;
    }
    const type = blob.type.split(";")[0];
    if (
      this.currentKind() === "markdown" &&
      ["text/plain", "text/markdown"].includes(type)
    ) {
      try {
        const text = await blob.text();
        if (!this.disposed && version === this.version) {
          this.text.set(text);
          this.markdown.set(renderMarkdown(text));
          this.kind.set("markdown");
        }
      } catch {
        if (!this.disposed && version === this.version) this.renderError();
      }
    } else if (
      this.currentKind() === "original" &&
      type === "application/pdf"
    ) {
      const url = URL.createObjectURL(new Blob([blob], { type }));
      this.objectUrl.set(url);
      // Only trust an internally generated PDF blob URL.
      this.pdfUrl.set(this.sanitizer.bypassSecurityTrustResourceUrl(url));
    } else
      this.error.set(
        "Only PDF originals and Markdown outputs can be previewed.",
      );
    if (!this.disposed && version === this.version) this.loading.set(false);
  }
  renderError(): void {
    this.releaseUrl();
    this.kind.set("");
    this.error.set("Unable to display this document preview.");
  }
  close(): void {
    this.dialog().nativeElement.close();
  }
  private releaseUrl(): void {
    this.pdfUrl.set(null);
    if (this.objectUrl()) URL.revokeObjectURL(this.objectUrl());
    this.objectUrl.set("");
  }
}
