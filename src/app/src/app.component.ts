import { Component } from "@angular/core";
import { RouterLink, RouterLinkActive, RouterOutlet } from "@angular/router";
@Component({
  selector: "app-root",
  imports: [RouterLink, RouterLinkActive, RouterOutlet],
  template: `
    <a class="skip-link" href="#main">Aller au contenu</a>
    <aside class="sidebar" aria-label="Navigation principale">
      <a class="brand" routerLink="/documents"
        ><span class="brand-mark">d.</span> docspace<span class="brand-dot"
          >●</span
        ></a
      >
      <div class="workspace">
        <span class="workspace-icon">D</span>
        <div>Espace documentaire<small>Gestion intelligente</small></div>
      </div>
      <p class="nav-label">ESPACE DE TRAVAIL</p>
      <nav>
        <a
          routerLink="/documents"
          routerLinkActive="active"
          ariaCurrentWhenActive="page"
          ><span aria-hidden="true">▤</span> Documents</a
        >
        @for (item of upcoming; track item.label) {
          <button
            disabled
            [attr.title]="item.label + ' : fonctionnalité à venir'"
          >
            <span aria-hidden="true">{{ item.icon }}</span
            >{{ item.label }}<small>À venir</small>
          </button>
        }
      </nav>
      <div class="sidebar-footer">
        <span class="status-dot"></span> Plateforme documentaire<small
          >Document Manager · Espace de consultation</small
        >
      </div>
    </aside>
    <div class="main-shell">
      <header class="topbar">
        <span
          >Espace de travail <span class="breadcrumb">/</span>
          <strong>Documents</strong></span
        ><span class="avatar" aria-label="Espace documentaire">D</span>
      </header>
      <main id="main" tabindex="-1"><router-outlet /></main>
    </div>
  `,
})
export class AppComponent {
  readonly upcoming = [
    { label: "Parsing", icon: "⇄" },
    { label: "Recherche OpenSearch", icon: "⌕" },
    { label: "Agent IA", icon: "✧" },
  ];
}
