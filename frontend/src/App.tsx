import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { DemoBanner } from "./components/DemoBanner";
import { DashboardPage } from "./pages/DashboardPage";
import { CertificatePage, Glossary, LearnHome, LevelPage } from "./pages/LearnPage";
import { MapPage } from "./pages/MapPage";
import { StoryList, StoryView } from "./pages/StoryPage";
import { TranslatorPage } from "./pages/TranslatorPage";

const NAV = [
  { to: "/carte", label: "Carte" },
  { to: "/traducteur", label: "Traducteur radar" },
  { to: "/recits", label: "Récits" },
  { to: "/apprendre", label: "Apprendre" },
  { to: "/tableau-de-bord", label: "Tableau de bord" },
];

export function App() {
  return (
    <div className="flex h-full flex-col">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:bg-ink-700 focus:p-2">Aller au contenu</a>
      <DemoBanner />
      <header className="flex h-12 shrink-0 items-center gap-6 border-b border-ink-600 bg-ink-800 px-4">
        <span className="font-semibold tracking-wide text-accent">NISAR Vision</span>
        <nav aria-label="Principale" className="flex gap-1 overflow-x-auto">
          {NAV.map((n) => (
            <NavLink key={n.to} to={n.to} className={({ isActive }) => `rounded px-3 py-1 text-sm ${isActive ? "bg-ink-600 text-white" : "text-slate-300 hover:bg-ink-700"}`}>{n.label}</NavLink>
          ))}
        </nav>
      </header>
      <main id="main" className="min-h-0 flex-1 overflow-y-auto">
        <Routes>
          <Route path="/" element={<Navigate to="/carte" replace />} />
          <Route path="/carte" element={<MapPage />} />
          <Route path="/traducteur" element={<TranslatorPage />} />
          <Route path="/recits" element={<StoryList />} />
          <Route path="/recits/:slug" element={<StoryView />} />
          <Route path="/apprendre" element={<LearnHome />} />
          <Route path="/apprendre/niveau/:id" element={<LevelPage />} />
          <Route path="/apprendre/glossaire" element={<Glossary />} />
          <Route path="/apprendre/certificat" element={<CertificatePage />} />
          <Route path="/tableau-de-bord" element={<DashboardPage />} />
          <Route path="*" element={<div className="p-6">Page introuvable. <NavLink className="text-accent underline" to="/carte">Retour à la carte</NavLink></div>} />
        </Routes>
      </main>
    </div>
  );
}
