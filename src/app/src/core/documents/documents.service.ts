import { HttpClient } from "@angular/common/http";
import { inject, Injectable } from "@angular/core";
import { map, timeout } from "rxjs";
import { isDocumentsResponse } from "./document.model";
@Injectable({ providedIn: "root" })
export class DocumentsService {
  private readonly http = inject(HttpClient);
  list() {
    return this.http.get<unknown>("/documents").pipe(
      timeout(15000),
      map((response) => {
        if (!isDocumentsResponse(response))
          throw new Error("Le format de la réponse est invalide.");
        return response.documents;
      }),
    );
  }
}
