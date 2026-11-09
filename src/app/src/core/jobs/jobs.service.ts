import { HttpClient, HttpParams } from "@angular/common/http";
import { inject, Injectable } from "@angular/core";
import { map, timeout } from "rxjs";
import { isJobsResponse } from "./job.model";
@Injectable({ providedIn: "root" })
export class JobsService {
  private readonly http = inject(HttpClient);
  list(documentId: string | null = null) {
    const params = documentId
      ? new HttpParams().set("document_id", documentId)
      : new HttpParams();
    return this.http.get<unknown>("/jobs", { params }).pipe(
      timeout(15000),
      map((response) => {
        if (!isJobsResponse(response))
          throw new Error("The jobs response format is invalid.");
        return response.jobs;
      }),
    );
  }
}
