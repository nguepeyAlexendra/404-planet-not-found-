import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../src/api/client";
import { DemoBanner } from "../src/components/DemoBanner";
import { PixelPanel } from "../src/components/PixelPanel";
import { Timeline } from "../src/components/Timeline";
import { LearnHome } from "../src/pages/LearnPage";
import { DayNight, Flood } from "../src/sim/Simulators";
import { useApp } from "../src/store";

vi.mock("recharts", async () => {
  const React = await import("react");
  const Pass = ({ children }: { children?: React.ReactNode }) => React.createElement("div", null, children);
  return { ResponsiveContainer: Pass, LineChart: Pass, Line: Pass, CartesianGrid: Pass, XAxis: Pass, YAxis: Pass, Tooltip: Pass, Legend: Pass, AreaChart: Pass, Area: Pass };
});

beforeEach(() => { useApp.setState(useApp.getInitialState(), true); vi.restoreAllMocks(); });

describe("bandeau de démonstration", () => {
  it("n'apparaît que lorsque les données simulées sont actives", () => {
    const { rerender } = render(<DemoBanner />);
    expect(screen.queryByRole("alert")).toBeNull();
    act(() => useApp.getState().setDemo(true));
    rerender(<DemoBanner />);
    expect(screen.getByRole("alert")).toHaveTextContent(/pas des observations NISAR/i);
  });
});

describe("chronologie", () => {
  it("ne propose que des dates réelles et appelle onChange", () => {
    const onChange = vi.fn();
    render(<Timeline dates={["2026-03-04", "2026-04-05"]} value="2026-03-04" onChange={onChange} />);
    expect(screen.getByText(/2 dates réelles/)).toBeInTheDocument();
    const slider = screen.getByRole("slider", { name: /date d'acquisition/i });
    expect(slider).toHaveAttribute("max", "1");
    fireEvent.change(slider, { target: { value: "1" } });
    expect(onChange).toHaveBeenCalledWith("2026-04-05");
  });
  it("ne rend rien sans date", () => {
    const { container } = render(<Timeline dates={[]} value={null} onChange={() => {}} />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe("panneau pixel", () => {
  const base = {
    lon: 9.7, lat: 4.05, date: "2026-03-04", dataset_id: 1, source_id: "S", sensor: "X", product_type: "GCOV", maturity: "demo" as const, is_demo: true,
    units: "dB", series: [],
  };
  it("affiche « non disponible » pour une bande sans valeur, jamais 0", async () => {
    vi.spyOn(api, "pixel").mockResolvedValue({ ...base, bands: { HH: { linear: 0.19, db: -7.2, status: "ok", reason: null }, HV: { linear: null, db: null, status: "nodata", reason: "nodata" } }, interpretation: null });
    render(<PixelPanel lon={9.7} lat={4.05} date="2026-03-04" demo onClose={() => {}} />);
    await waitFor(() => expect(screen.getByText("-7.2 dB")).toBeInTheDocument());
    expect(screen.getAllByText("non disponible").length).toBeGreaterThanOrEqual(1);
    expect(screen.queryByText("0.0 dB")).toBeNull();
  });
  it("montre l'avertissement prototype avec l'interprétation", async () => {
    vi.spyOn(api, "pixel").mockResolvedValue({
      ...base, bands: { HH: { linear: 0.19, db: -7.2, status: "ok", reason: null } },
      interpretation: { class_id: 2, class_key: "dense_vegetation", label: "Végétation dense", hh_db: -7.2, hv_db: -11, ratio_db: 3.8, explanation: "Diffusion de volume.", ruleset_version: "v0", caution: "Prototype non validé." },
    });
    render(<PixelPanel lon={9.7} lat={4.05} date="2026-03-04" demo onClose={() => {}} />);
    await waitFor(() => expect(screen.getByText(/Prototype non validé/)).toBeInTheDocument());
    expect(screen.getByText(/hypothèse probable/)).toBeInTheDocument();
  });
  it("affiche une erreur claire et un bouton réessayer", async () => {
    vi.spyOn(api, "pixel").mockRejectedValue(new Error("Le serveur ne répond pas."));
    render(<PixelPanel lon={9.7} lat={4.05} date="2026-03-04" demo onClose={() => {}} />);
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Le serveur ne répond pas."));
    expect(screen.getByRole("button", { name: "Réessayer" })).toBeInTheDocument();
  });
});

describe("simulateurs", () => {
  it("sont toujours étiquetés conceptuels", () => {
    render(<><DayNight /><Flood /></>);
    expect(screen.getAllByText("Simulation conceptuelle")).toHaveLength(2);
  });
  it("le simulateur d'eau signale quand le seuil se trompe", async () => {
    render(<Flood />);
    expect(screen.queryByRole("alert")).toBeNull();
    await userEvent.click(screen.getByLabelText(/Végétation émergée/));
    expect(screen.getByRole("alert")).toHaveTextContent(/double rebond/);
  });
});

describe("apprentissage", () => {
  it("les niveaux verrouillés n'ont pas de lien d'accès", async () => {
    vi.spyOn(api, "levels").mockResolvedValue([
      { id: 1, number: 1, title: "N1", summary: "s", xp: 100, badge_key: "b1", simulator: "day_night", unlocked: true, completed: false },
      { id: 2, number: 2, title: "N2", summary: "s", xp: 200, badge_key: "b2", simulator: "roughness", unlocked: false, completed: false },
    ]);
    vi.spyOn(api, "progress").mockResolvedValue({ xp: 0, completed_levels: [], total_levels: 2, badges: [], certificate_eligible: false, certificate_code: null });
    render(<MemoryRouter><LearnHome /></MemoryRouter>);
    await waitFor(() => expect(screen.getByText("N1")).toBeInTheDocument());
    expect(screen.getAllByRole("link", { name: "Commencer" })).toHaveLength(1);
    expect(screen.getByText(/Terminez le niveau précédent/)).toBeInTheDocument();
  });
});
