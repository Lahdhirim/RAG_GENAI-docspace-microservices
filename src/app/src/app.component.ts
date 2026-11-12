import { takeUntilDestroyed } from "@angular/core/rxjs-interop";
import { Component, inject, signal } from "@angular/core";
import {
  NavigationEnd,
  Router,
  RouterLink,
  RouterLinkActive,
  RouterOutlet,
} from "@angular/router";
@Component({
  selector: "app-root",
  imports: [RouterLink, RouterLinkActive, RouterOutlet],
  template: `
    <a class="skip-link" href="#main">Skip to content</a>
    <aside class="sidebar" aria-label="Main navigation">
      <a class="brand" routerLink="/documents"
        ><span class="brand-mark">d.</span> docspace<span class="brand-dot"
          >●</span
        ></a
      >
      <div class="workspace">
        <span class="workspace-icon">D</span>
        <div>Document workspace<small>Intelligent management</small></div>
      </div>
      <p class="nav-label">WORKSPACE</p>
      <nav>
        <a
          routerLink="/documents"
          routerLinkActive="active"
          ariaCurrentWhenActive="page"
          ><span aria-hidden="true">▤</span> Documents</a
        >
        <a
          routerLink="/parsing"
          routerLinkActive="active"
          ariaCurrentWhenActive="page"
          ><span aria-hidden="true">⇄</span> Parsing</a
        >
        @for (item of upcoming; track item.label) {
          <button disabled [attr.title]="item.label + ': coming soon'">
            <span aria-hidden="true">{{ item.icon }}</span
            >{{ item.label }}<small>Coming soon</small>
          </button>
        }
      </nav>
      <div class="sidebar-footer">
        <span class="status-dot"></span> Document platform<small
          >Document Manager · Read-only workspace</small
        >
      </div>
    </aside>
    <div class="main-shell">
      <header class="topbar">
        <span
          >Workspace <span class="breadcrumb">/</span>
          <strong>{{ pageTitle() }}</strong></span
        ><span class="avatar" aria-label="Document workspace">D</span>
      </header>
      <main id="main" tabindex="-1"><router-outlet /></main>
    </div>
  `,
})
export class AppComponent {
  readonly pageTitle = signal("Documents");
  private readonly router = inject(Router);
  constructor() {
    this.router.events.pipe(takeUntilDestroyed()).subscribe((event) => {
      if (event instanceof NavigationEnd) {
        this.pageTitle.set(
          event.urlAfterRedirects.split("?")[0] === "/parsing"
            ? "Parsing"
            : "Documents",
        );
        globalThis.document.title = `Docspace · ${this.pageTitle()}`;
      }
    });
  }
  readonly upcoming = [
    { label: "OpenSearch search", icon: "⌕" },
    { label: "AI agent", icon: "✧" },
  ];
}
