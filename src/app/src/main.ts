import { bootstrapApplication } from "@angular/platform-browser";
import { provideHttpClient } from "@angular/common/http";
import { provideRouter } from "@angular/router";
import { AppComponent } from "./app.component";
import { routes } from "./app.routes";
bootstrapApplication(AppComponent, {
  providers: [provideHttpClient(), provideRouter(routes)],
}).catch((error) => console.error("Unable to start the frontend", error));
