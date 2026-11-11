import { HttpClient } from "@angular/common/http";
import { inject, Injectable } from "@angular/core";
import { map, timeout } from "rxjs";
import { parseStatusesResponse } from "./job.model";
@Injectable({ providedIn: "root" })
export class JobsService {
  private readonly http = inject(HttpClient);
  list() {
    return this.http
      .get<unknown>("/parsing_statuses")
      .pipe(timeout(15000), map(parseStatusesResponse));
  }
}
