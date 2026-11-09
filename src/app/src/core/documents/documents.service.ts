import { HttpClient } from "@angular/common/http";
import { inject, Injectable } from "@angular/core";
import { map, timeout } from "rxjs";
import { isDocumentsResponse } from "./document.model";
@Injectable({ providedIn: "root" })
export class DocumentsService {
  private readonly http = inject(HttpClient);
  preview(documentId: string) {
    return this.http
      .get(`/documents/${encodeURIComponent(documentId)}/preview`, {
        responseType: "blob",
      })
      .pipe(timeout(30000));
  }
  list() {
    return this.http.get<unknown>("/documents").pipe(
      timeout(15000),
      map((response) => {
        if (!isDocumentsResponse(response))
          throw new Error("The response format is invalid.");
        return response.documents;
      }),
    );
  }
}
