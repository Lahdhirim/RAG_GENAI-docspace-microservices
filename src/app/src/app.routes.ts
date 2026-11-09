import { Routes } from "@angular/router";
export const routes: Routes = [
  {
    path: "documents",
    loadComponent: () =>
      import("./features/documents/documents.component").then(
        (m) => m.DocumentsComponent,
      ),
  },
  {
    path: "parsing",
    loadComponent: () =>
      import("./features/jobs/jobs.component").then((m) => m.JobsComponent),
  },
  { path: "", pathMatch: "full", redirectTo: "documents" },
  { path: "**", redirectTo: "documents" },
];
