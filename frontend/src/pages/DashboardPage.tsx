import { useEffect, useMemo, useState } from "react";
import { Area, AreaChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, pollJob } from "../api/client";
import type { ChangeMatrixResult, ProjectionResult, TimeSeriesResult } from "../api/types";
import { Empty, ErrorBox, Loading, Prototype } from "../components/ui";
import { useAsync } from "../lib/async";
import { fmtDate, fmtKm2 } from "../lib/format";
import { downloadExport, useJob } from "../lib/useJob";
import { useApp } from "../store";

const CLASS_COLORS: Record<string, string> = { water: "#1f6fd1", dense_vegetation: "#0b5d1e", sparse_vegetation: "#7cc576", urban: "#d13b2f", bare_soil: "#a67c52", indeterminate: "#9aa0a6" };
const CLASS_LABELS: Record<string, string> = { water: "Eau libre", dense_vegetation: "Végétation dense", sparse_vegetation: "Végétation clairsemée", urban: "Zone bâtie", bare_soil: "Sol nu", indeterminate: "Indéterminé" };
const SCENARIO_LABELS: Record<string, string> = { business_as_usual: "Tendance actuelle", protection_renforcee: "Protection renforcée", acceleration: "Accélération" };
const SCENARIO_COLORS: Record<string, string> = { business_as_usual: "#4cc2ff", protection_renforcee: "#7cc576", acceleration: "#d13b2f" };

export function DashboardPage() {
  const s = useApp();
  const layers = useAsync(() => api.layers(s.demo), [s.demo]);
  const dates = useMemo(() => [...new Set((layers.data ?? []).flatMap((l) => l.coverage?.dates ?? []))].sort(), [layers.data]);
  const [start, setStart] = useState(""); const [end, setEnd] = useState("");
  const [freq, setFreq] = useState<"day" | "week" | "month">("month");
  const [lon, setLon] = useState("9.70"); const [lat, setLat] = useState("4.05"); const [rad, setRad] = useState(3);
  const [aoiErr, setAoiErr] = useState<string | null>(null);
  const [da, setDa] = useState(""); const [db, setDb] = useState("");
  const [horizon, setHorizon] = useState(3);
  const [scenarios, setScenarios] = useState<string[]>(["business_as_usual"]);
  const [exportMsg, setExportMsg] = useState<string | null>(null);

  useEffect(() => {
    if (!dates.length) return;
    setStart(dates[0]); setEnd(dates[dates.length - 1]); setDa(dates[0]); setDb(dates[dates.length - 1]);
  }, [dates.join(",")]); // eslint-disable-line

  const ts = useJob<TimeSeriesResult>();
  const cm = useJob<ChangeMatrixResult>();
  const pr = useJob<ProjectionResult>();

  async function createAoi(e: React.FormEvent) {
    e.preventDefault(); setAoiErr(null);
    const lo = parseFloat(lon.replace(",", ".")), la = parseFloat(lat.replace(",", "."));
    if (!isFinite(lo) || !isFinite(la) || Math.abs(lo) > 180 || Math.abs(la) > 90) return setAoiErr("Coordonnées invalides.");
    try { const a = await api.createAoi({ title: `Zone ${la.toFixed(2)}, ${lo.toFixed(2)}`, center: [lo, la], radius_km: rad }); s.setAoi({ id: a.id, title: a.title, area_km2: a.area_km2 }); }
    catch (x) { setAoiErr((x as Error).message); }
  }
  const base = () => ({ aoi_id: s.aoi!.id, date_start: start, date_end: end, include_demo: s.demo, frequency: freq });
  const demoActive = s.demo;

  async function doExport(job: string, fmt: string) {
    setExportMsg("Préparation de l'export…");
    try {
      const j = await api.createExport(job, fmt);
      const done = await pollJob(j);
      if (done.status !== "succeeded" || !done.result) throw new Error(done.error_message ?? "Export impossible.");
      await downloadExport(done.result.export_id, `nisar-vision-${fmt === "geojson" ? "analyse.geojson" : "analyse." + fmt}`);
      setExportMsg(`Export ${fmt.toUpperCase()} téléchargé.`);
    } catch (e) { setExportMsg((e as Error).message); }
  }

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-4">
      <header className="space-y-1">
        <h1 className="text-xl font-semibold">Tableau de bord analytique</h1>
        <p className="text-sm text-slate-400">Analysez une zone sur une période. Les calculs se font sur les valeurs linéaires, puis sont convertis en dB.</p>
      </header>
      <section className="card grid gap-4 md:grid-cols-2" aria-label="Paramètres de l'analyse">
        <div className="space-y-2">
          <h2 className="font-medium">1. Zone d'intérêt</h2>
          {s.aoi ? <p className="text-sm">Zone active : <strong>{s.aoi.title}</strong>, {fmtKm2(s.aoi.area_km2)}. <button className="btn ml-2" onClick={() => s.setAoi(null)}>Changer</button></p> : (
            <form onSubmit={createAoi} className="space-y-2 text-sm">
              <p className="text-xs text-slate-400">Vous pouvez aussi dessiner une zone sur la carte.</p>
              <div className="flex flex-wrap gap-2">
                <label>Longitude<input className="field ml-1 w-24" value={lon} onChange={(e) => setLon(e.target.value)} inputMode="decimal" /></label>
                <label>Latitude<input className="field ml-1 w-24" value={lat} onChange={(e) => setLat(e.target.value)} inputMode="decimal" /></label>
                <label>Rayon (km)<input className="field ml-1 w-16" type="number" min={1} max={50} value={rad} onChange={(e) => setRad(+e.target.value)} /></label>
              </div>
              <button className="btn btn-primary" type="submit">Créer la zone</button>
              {aoiErr && <p role="alert" className="text-xs text-red-300">{aoiErr}</p>}
            </form>
          )}
        </div>
        <div className="space-y-2 text-sm">
          <h2 className="font-medium">2. Période et données</h2>
          <label className="flex items-center gap-2"><input type="checkbox" checked={s.demo} onChange={(e) => s.setDemo(e.target.checked)} />Inclure les données de démonstration simulées</label>
          {layers.loading ? <Loading /> : dates.length === 0 ? <Empty>Aucune acquisition disponible. Ingérez des données NISAR ou activez la démonstration simulée.</Empty> : (
            <div className="flex flex-wrap gap-2">
              <label>Début<input type="date" className="field ml-1" value={start} min={dates[0]} max={dates[dates.length - 1]} onChange={(e) => setStart(e.target.value)} /></label>
              <label>Fin<input type="date" className="field ml-1" value={end} min={dates[0]} max={dates[dates.length - 1]} onChange={(e) => setEnd(e.target.value)} /></label>
              <label>Pas<select className="field ml-1" value={freq} onChange={(e) => setFreq(e.target.value as "day" | "week" | "month")}><option value="day">jour</option><option value="week">semaine</option><option value="month">mois</option></select></label>
            </div>
          )}
        </div>
      </section>
      {demoActive && <div role="alert" className="rounded bg-warn px-3 py-2 text-sm font-semibold text-ink-900">Les résultats ci-dessous peuvent inclure des données SIMULÉES. Ils ne décrivent aucune observation NISAR réelle.</div>}
      {!s.aoi && <Empty>Définissez d'abord une zone d'intérêt pour lancer une analyse.</Empty>}

      <Block title="Série temporelle" job={ts} disabled={!s.aoi || !start || !end} onRun={() => ts.run(() => api.timeSeries({ ...base(), variables: ["HHHH", "HVHV", "classes"] }))} onExport={(f) => ts.job && doExport(ts.job.job_id, f)}>
        {ts.job?.result && <TimeSeriesCharts r={ts.job.result} />}
      </Block>

      <Block title="Matrice de transition entre deux dates" job={cm} disabled={!s.aoi || !da || !db || da === db}
        onRun={() => cm.run(() => api.changeMatrix({ aoi_id: s.aoi!.id, date_a: da, date_b: db, include_demo: s.demo }))} onExport={(f) => cm.job && doExport(cm.job.job_id, f)}
        controls={dates.length > 0 && (
          <div className="flex flex-wrap gap-2 text-sm">
            <label>Date A<select className="field ml-1" value={da} onChange={(e) => setDa(e.target.value)}>{dates.map((d) => <option key={d} value={d}>{fmtDate(d)}</option>)}</select></label>
            <label>Date B<select className="field ml-1" value={db} onChange={(e) => setDb(e.target.value)}>{dates.map((d) => <option key={d} value={d}>{fmtDate(d)}</option>)}</select></label>
            {da === db && <span className="text-xs text-warn">Choisissez deux dates différentes.</span>}
          </div>)}>
        {cm.job?.result && <Matrix r={cm.job.result} />}
      </Block>

      <Block title="Projection exploratoire (what-if)" job={pr} disabled={!s.aoi || !start || !end}
        onRun={() => pr.run(() => api.projection({ ...base(), variable: "HH", horizon_months: horizon }))} onExport={(f) => pr.job && doExport(pr.job.job_id, f)}
        controls={
          <div className="flex flex-wrap items-center gap-3 text-sm">
            <label>Horizon : {horizon} mois<input type="range" min={1} max={12} value={horizon} onChange={(e) => setHorizon(+e.target.value)} className="ml-2 align-middle" /></label>
            {Object.keys(SCENARIO_LABELS).map((k) => (
              <label key={k} className="flex items-center gap-1"><input type="checkbox" checked={scenarios.includes(k)} onChange={(e) => setScenarios((v) => e.target.checked ? [...v, k] : v.filter((x) => x !== k))} />{SCENARIO_LABELS[k]}</label>
            ))}
          </div>}>
        {pr.job?.result && <Projection r={pr.job.result} show={scenarios} />}
      </Block>
      {exportMsg && <p role="status" className="text-sm text-slate-300">{exportMsg}</p>}
    </div>
  );
}

function Block<T>({ title, job, disabled, onRun, onExport, controls, children }: {
  title: string; job: ReturnType<typeof useJob<T>>; disabled: boolean; onRun: () => void; onExport: (fmt: string) => void; controls?: React.ReactNode; children: React.ReactNode;
}) {
  return (
    <section className="card space-y-3" aria-label={title}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="font-medium">{title}</h2>
        <div className="flex items-center gap-2">
          {job.running ? <button className="btn" onClick={job.cancel}>Annuler</button> : <button className="btn btn-primary" disabled={disabled} onClick={onRun}>Lancer l'analyse</button>}
        </div>
      </div>
      {controls}
      {job.running && <div role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(job.progress * 100)} className="h-2 w-full rounded bg-ink-700"><div className="h-2 rounded bg-accent transition-all" style={{ width: `${Math.max(job.progress * 100, 5)}%` }} /></div>}
      {job.error && <ErrorBox message={job.error} />}
      {children}
      {job.job?.status === "succeeded" && (
        <div className="flex flex-wrap items-center gap-2 border-t border-ink-600 pt-2 text-sm">
          <span className="text-xs text-slate-400">Exporter :</span>
          {["csv", "geojson", "svg", "pdf"].map((f) => <button key={f} className="btn" onClick={() => onExport(f)}>{f.toUpperCase()}</button>)}
          {job.job.method_version && <span className="ml-auto text-xs text-slate-500">méthode {job.job.method_version}</span>}
        </div>
      )}
    </section>
  );
}

function Warnings({ items }: { items?: string[] }) {
  return items?.length ? <ul className="space-y-1">{items.map((w) => <li key={w}><Prototype>{w}</Prototype></li>)}</ul> : null;
}

function TimeSeriesCharts({ r }: { r: TimeSeriesResult }) {
  if (!r.series.length) return <Empty>Aucune acquisition ne tombe dans cette période pour cette zone.</Empty>;
  const rows = r.series.map((p) => ({ period: p.period, HH: p.bands.HH?.mean_db, HV: p.bands.HV?.mean_db, ...p.classes_pct }));
  const keys = Object.keys(CLASS_COLORS).filter((k) => rows.some((x) => ((x as unknown as Record<string, number>)[k] ?? 0) > 0));
  const axis = { tick: { fontSize: 11, fill: "#94a3b8" } };
  return (
    <div className="space-y-4">
      <Warnings items={r.warnings} />
      <div className="h-64" role="img" aria-label="Moyenne du signal HH et HV par période, en dB">
        <ResponsiveContainer><LineChart data={rows}><CartesianGrid stroke="#26345a" /><XAxis dataKey="period" {...axis} /><YAxis {...axis} unit=" dB" domain={["auto", "auto"]} /><Tooltip contentStyle={{ background: "#111a2e", border: "1px solid #26345a" }} /><Legend />
          <Line dataKey="HH" stroke="#4cc2ff" dot isAnimationActive={false} connectNulls={false} /><Line dataKey="HV" stroke="#7cc576" dot isAnimationActive={false} connectNulls={false} /></LineChart></ResponsiveContainer>
      </div>
      {keys.length > 0 && (
        <div className="h-64" role="img" aria-label="Part de chaque classe par période, en pourcentage">
          <ResponsiveContainer><AreaChart data={rows}><CartesianGrid stroke="#26345a" /><XAxis dataKey="period" {...axis} /><YAxis {...axis} unit=" %" domain={[0, 100]} /><Tooltip contentStyle={{ background: "#111a2e", border: "1px solid #26345a" }} /><Legend />
            {keys.map((k) => <Area key={k} type="linear" dataKey={k} name={CLASS_LABELS[k]} stackId="1" stroke={CLASS_COLORS[k]} fill={CLASS_COLORS[k]} isAnimationActive={false} />)}</AreaChart></ResponsiveContainer>
        </div>
      )}
      <details className="text-xs text-slate-300"><summary className="cursor-pointer">Données en tableau</summary>
        <table className="mt-2 w-full text-left"><thead><tr><th>Période</th><th>Obs.</th><th>HH (dB)</th><th>HV (dB)</th></tr></thead>
          <tbody>{r.series.map((p) => <tr key={p.period}><td>{p.period}</td><td>{p.n_observations}</td><td>{p.bands.HH?.mean_db ?? "non disponible"}</td><td>{p.bands.HV?.mean_db ?? "non disponible"}</td></tr>)}</tbody></table></details>
    </div>
  );
}

function Matrix({ r }: { r: ChangeMatrixResult }) {
  const max = Math.max(1, ...r.matrix.area_km2.flat());
  const used = r.matrix.class_ids.filter((_, i) => r.matrix.area_km2[i].some((v) => v > 0) || r.matrix.area_km2.some((row) => row[i] > 0));
  return (
    <div className="space-y-3">
      <p className="text-sm">{r.summary_text}</p>
      <Warnings items={r.warnings} />
      <div className="overflow-x-auto">
        <table className="text-sm"><caption className="mb-1 text-left text-xs text-slate-400">Surface en km². Lignes : classe à la date A ({fmtDate(r.date_a)}). Colonnes : classe à la date B ({fmtDate(r.date_b)}).</caption>
          <thead><tr><th className="p-1" />{used.map((c) => <th key={c} className="p-1 text-xs font-normal">{r.labels[c]}</th>)}</tr></thead>
          <tbody>{used.map((i) => (
            <tr key={i}><th scope="row" className="p-1 text-left text-xs font-normal">{r.labels[i]}</th>
              {used.map((j) => { const v = r.matrix.area_km2[i][j]; return <td key={j} className="p-2 text-center" style={{ background: `rgba(76,194,255,${(v / max) * 0.8})` }}>{v ? v.toFixed(2) : "0"}</td>; })}</tr>))}</tbody></table>
      </div>
      <ul className="grid gap-1 text-xs text-slate-300 md:grid-cols-2">{used.map((i) => <li key={i}>{r.labels[i]} : {r.matrix.net_km2[i] >= 0 ? "+" : ""}{r.matrix.net_km2[i].toFixed(2)} km² net</li>)}</ul>
    </div>
  );
}

function Projection({ r, show }: { r: ProjectionResult; show: string[] }) {
  const rows = useMemo(() => {
    const m = new Map<number, Record<string, number | string>>();
    r.history.forEach((h) => m.set(h.day, { day: h.day, label: h.period, history: h.value }));
    Object.entries(r.scenarios).filter(([k]) => show.includes(k)).forEach(([k, sc]) => sc.points.forEach((p) => {
      const row = m.get(p.day) ?? { day: p.day, label: `J+${Math.round(p.day)}` }; row[k] = p.value; row[k + "_lo"] = p.low; row[k + "_hi"] = p.high; m.set(p.day, row);
    }));
    return [...m.values()].sort((a, b) => (a.day as number) - (b.day as number));
  }, [r, show]);
  const axis = { tick: { fontSize: 11, fill: "#94a3b8" } };
  return (
    <div className="space-y-3">
      <Prototype>Projection exploratoire : extrapolation linéaire de la tendance observée, avec un intervalle de prédiction à 95 %. Ce n'est pas une prévision. Les scénarios multiplient simplement la pente observée.</Prototype>
      <Warnings items={r.warnings} />
      <div className="h-72" role="img" aria-label="Historique et projection du signal HH en dB avec intervalle">
        <ResponsiveContainer><LineChart data={rows}><CartesianGrid stroke="#26345a" /><XAxis dataKey="day" {...axis} tickFormatter={(d) => `J${Math.round(d)}`} /><YAxis {...axis} unit=" dB" domain={["auto", "auto"]} /><Tooltip contentStyle={{ background: "#111a2e", border: "1px solid #26345a" }} /><Legend />
          <Line dataKey="history" name="Observé" stroke="#e2e8f0" dot isAnimationActive={false} connectNulls />
          {Object.keys(r.scenarios).filter((k) => show.includes(k)).flatMap((k) => [
            <Line key={k} dataKey={k} name={SCENARIO_LABELS[k]} stroke={SCENARIO_COLORS[k]} strokeDasharray="6 4" dot isAnimationActive={false} connectNulls />,
            <Line key={k + "lo"} dataKey={k + "_lo"} legendType="none" stroke={SCENARIO_COLORS[k]} strokeOpacity={0.35} dot={false} isAnimationActive={false} connectNulls />,
            <Line key={k + "hi"} dataKey={k + "_hi"} legendType="none" stroke={SCENARIO_COLORS[k]} strokeOpacity={0.35} dot={false} isAnimationActive={false} connectNulls />])}
        </LineChart></ResponsiveContainer>
      </div>
      <ul className="text-xs text-slate-300">{Object.entries(r.scenarios).filter(([k]) => show.includes(k)).map(([k, sc]) => <li key={k}>{SCENARIO_LABELS[k]} : pente {sc.slope_per_day.toFixed(4)} dB/jour, R² {sc.r2.toFixed(2)} sur {sc.n} points</li>)}</ul>
    </div>
  );
}
