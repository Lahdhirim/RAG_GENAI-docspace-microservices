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
          <p class="eyebrow">DOCUMENT PREVIEW</p>
          <h2 id="preview-title">{{ document().filename }}</h2>
        </div>
        <button class="button" (click)="close()" aria-label="Close preview">
          ✕
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
      } @else if (kind() === "image") {
        <div class="image-preview">
          <img
            [src]="objectUrl()"
            [alt]="'Preview of ' + document().filename"
            (error)="renderError()"
          />
        </div>
      } @else if (kind() === "text") {
        <pre class="text-preview">{{ text() }}</pre>
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
      .image-preview {
        overflow: auto;
        flex: 1;
        text-align: center;
      }
      .image-preview img {
        max-width: 100%;
        max-height: 100%;
        object-fit: contain;
      }
      .text-preview {
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
      this.load();
    });
    this.destroyRef.onDestroy(() => {
      this.disposed = true;
      this.releaseUrl();
    });
  }
  downloadName(): string {
    const doc = this.document();
    return doc.filename.toLowerCase().endsWith(doc.extension.toLowerCase())
      ? doc.filename
      : doc.filename + doc.extension;
  }
  load(): void {
    if (this.loading()) return;
    this.error.set("");
    this.retryable.set(false);
    this.releaseUrl();
    this.kind.set("");
    this.text.set("");
    if (!this.document().is_present) {
      this.error.set("This document is currently unavailable.");
      return;
    }
    this.loading.set(true);
    this.api
      .preview(this.document().id)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (blob) => {
          void this.show(blob);
        },
        error: (error: unknown) => {
          this.loading.set(false);
          if (
            error instanceof HttpErrorResponse &&
            [404, 410].includes(error.status)
          )
            this.error.set("This document is currently unavailable.");
          else if (error instanceof HttpErrorResponse && error.status === 415)
            this.error.set("Preview is not supported for this file type.");
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
  private async show(blob: Blob): Promise<void> {
    if (blob.size > 50 * 1024 * 1024) {
      this.loading.set(false);
      this.error.set("This document is too large to preview (maximum 50 MiB).");
      return;
    }
    const type = blob.type.split(";")[0];
    if (type === "text/plain") {
      try {
        const text = await blob.text();
        if (!this.disposed) {
          this.text.set(text);
          this.kind.set("text");
        }
      } catch {
        if (!this.disposed) this.renderError();
      }
    } else if (
      type === "application/pdf" ||
      [
        "image/png",
        "image/jpeg",
        "image/gif",
        "image/webp",
        "image/bmp",
      ].includes(type)
    ) {
      const url = URL.createObjectURL(new Blob([blob], { type }));
      this.objectUrl.set(url);
      if (type === "application/pdf") {
        // Trust only an internally generated blob URL with an allowlisted PDF MIME type.
        this.pdfUrl.set(this.sanitizer.bypassSecurityTrustResourceUrl(url));
      } else this.kind.set("image");
    } else this.error.set("Preview is not supported for this file type.");
    if (!this.disposed) this.loading.set(false);
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
