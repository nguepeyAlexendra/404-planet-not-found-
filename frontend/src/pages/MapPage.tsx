import { useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import type { Layer } from "../api/types";
import { Legend } from "../components/LegendPanel";
import { MapView, type RasterSpec } from "../components/MapView";
import { PixelPanel } from "../components/PixelPanel";
import { Swipe } from "../components/Swipe";
import { Timeline } from "../components/Timeline";
import { Empty, ErrorBox, Loading, MaturityBadge } from "../components/ui";
import { useAsync } from "../lib/async";
import { fmtDate, fmtKm2 } from "../lib/format";
import { tileUrl } from "../lib/tiles";
import { useApp } from "../store";

type Tool = "none" | "circle" | "rect";

export function MapPage() {
  const s = useApp();
  const layers = useAsync(() => api.layers(s.demo), [s.demo]);
  const [basemap, setBasemap] = useState(true);
  const [compare, setCompare] = useState(false);
  const [pixel, setPixel] = useState<{ lon: number; lat: number } | null>(null);
  const [tool, setTool] = useState<Tool>("none");
  const [radius, setRadius] = useState(3);
  const [rectStart, setRectStart] = useState<[number, number] | null>(null);
  const [draft, setDraft] = useState<GeoJSON.Geometry | null>(null);
  const [draftBbox, setDraftBbox] = useState<{ center?: [number, number]; bbox?: [number, number, number, number] } | null>(null);
  const [aoiMsg, setAoiMsg] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [searchMsg, setSearchMsg] = useState<string | null>(null);
  const [fit, setFit] = useState<[number, number, number, number] | null>(null);

  const list = layers.data ?? [];
  const active = s.activeLayers.map((k) => list.find((l) => l.key === k)).filter((l): l is Layer => !!l);
  const dates = useMemo(() => [...new Set(active.flatMap((l) => l.coverage?.dates ?? []))].sort(), [active]);
  const primary = active[0];
  const meta = useAsync(() => (primary ? api.layerMetadata(primary.key, s.demo) : Promise.resolve(null)), [primary?.key, s.demo]);

  useEffect(() => {
    if (!dates.length) { if (s.date) s.setDate(null); return; }
    if (!s.date || !dates.includes(s.date)) s.setDate(dates[dates.length - 1]);
    if (s.compareDate && !dates.includes(s.compareDate)) s.setCompareDate(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dates.join(",")]);

  useEffect(() => {
    const b = list.find((l) => l.coverage?.bounds)?.coverage?.bounds;
    if (b) setFit(b);
  }, [layers.data]);

  const rastersFor = (date: string | null): RasterSpec[] =>
    !date ? [] : active.filter((l) => l.coverage?.dates.includes(date)).map((l) => ({ id: `nv-${l.key}`, url: tileUrl(l.key, date, s.demo), opacity: s.opacity[l.key] ?? l.default_opacity }));
  const rasters = useMemo(() => rastersFor(s.date), [s.date, s.demo, s.opacity, active.map((l) => l.key).join(",")]);
  const afterRasters = useMemo(() => rastersFor(s.compareDate), [s.compareDate, s.demo, s.opacity, active.map((l) => l.key).join(",")]);
  const missing = s.date ? active.filter((l) => !l.coverage?.dates.includes(s.date!)) : [];
  const dataset = meta.data?.datasets.find((d) => d.date === s.date);

  function onMapClick(lon: number, lat: number) {
    setAoiMsg(null);
    if (tool === "circle") {
      setDraft(circle(lon, lat, radius)); setDraftBbox({ center: [lon, lat] });
    } else if (tool === "rect") {
      if (!rectStart) { setRectStart([lon, lat]); setDraft(null); }
      else {
        const bb: [number, number, number, number] = [Math.min(rectStart[0], lon), Math.min(rectStart[1], lat), Math.max(rectStart[0], lon), Math.max(rectStart[1], lat)];
        setDraft(bboxPoly(bb)); setDraftBbox({ bbox: bb }); setRectStart(null);
      }
    } else if (s.date) setPixel({ lon, lat });
  }
  useEffect(() => { if (tool === "circle" && draftBbox?.center) setDraft(circle(draftBbox.center[0], draftBbox.center[1], radius)); }, [radius]); // eslint-disable-line

  async function saveAoi() {
    if (!draftBbox) return;
    try {
      const a = await api.createAoi({ title: `Zone ${new Date().toLocaleTimeString("fr-FR")}`, ...(draftBbox.center ? { center: draftBbox.center, radius_km: radius } : { bbox: draftBbox.bbox }) });
      s.setAoi({ id: a.id, title: a.title, area_km2: a.area_km2 });
      setDraft(a.geometry); setTool("none"); setDraftBbox(null);
      setAoiMsg(`Zone créée (${fmtKm2(a.area_km2)}). Elle est utilisable dans le tableau de bord.`);
    } catch (e) { setAoiMsg((e as Error).message); }
  }

  async function doSearch(e: React.FormEvent) {
    e.preventDefault();
    setSearchMsg(null);
    const m = search.match(/^\s*(-?\d+(?:[.,]\d+)?)\s*[,; ]\s*(-?\d+(?:[.,]\d+)?)\s*$/);
    if (m) {
      const lat = parseFloat(m[1].replace(",", ".")), lon = parseFloat(m[2].replace(",", "."));
      if (Math.abs(lat) > 90 || Math.abs(lon) > 180) return setSearchMsg("Coordonnées hors limites.");
      s.setView([lon, lat], 11); return;
    }
    try {
      const r = await fetch(`https://nominatim.openstreetmap.org/search?format=json&limit=1&q=${encodeURIComponent(search)}`);
      const j = (await r.json()) as { lat: string; lon: string; display_name: string }[];
      if (!j.length) return setSearchMsg("Lieu introuvable.");
      s.setView([parseFloat(j[0].lon), parseFloat(j[0].lat)], 10); setSearchMsg(j[0].display_name);
    } catch { setSearchMsg("Recherche de lieu indisponible. Saisissez « latitude, longitude »."); }
  }

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex min-h-0 flex-1 flex-col md:flex-row">
        <aside className="w-full shrink-0 space-y-4 overflow-y-auto border-ink-600 bg-ink-800 p-3 md:w-72 md:border-r" aria-label="Panneau des couches">
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={s.demo} onChange={(e) => s.setDemo(e.target.checked)} />
            Afficher les données de démonstration simulées
          </label>
          <section aria-labelledby="h-layers">
            <h2 id="h-layers" className="mb-2 text-sm font-semibold">Couches</h2>
            {layers.loading && <Loading />}
            {layers.error && <ErrorBox message={layers.error} onRetry={layers.reload} />}
            <ul className="space-y-2">
              {list.map((l) => {
                const on = s.activeLayers.includes(l.key);
                const pos = s.activeLayers.indexOf(l.key);
                return (
                  <li key={l.key} className="rounded border border-ink-600 p-2 text-sm">
                    <label className="flex items-start gap-2">
                      <input type="checkbox" checked={on} onChange={() => s.toggleLayer(l.key)} disabled={!l.coverage?.available} />
                      <span>{l.label}<br /><span className="text-xs text-slate-400">{l.coverage?.available ? `${l.coverage.count} date(s) réelle(s)` : "Aucune donnée ingérée"}</span></span>
                    </label>
                    {on && (
                      <div className="mt-2 flex items-center gap-2">
                        <input type="range" min={0} max={1} step={0.05} value={s.opacity[l.key] ?? l.default_opacity} aria-label={`Opacité ${l.label}`} className="flex-1"
                          onChange={(e) => s.setOpacity(l.key, +e.target.value)} />
                        <button className="btn px-2" aria-label={`Monter ${l.label}`} disabled={pos === s.activeLayers.length - 1} onClick={() => s.moveLayer(l.key, 1)}>↑</button>
                        <button className="btn px-2" aria-label={`Descendre ${l.label}`} disabled={pos === 0} onClick={() => s.moveLayer(l.key, -1)}>↓</button>
                      </div>
                    )}
                  </li>
                );
              })}
            </ul>
          </section>
          {primary && <Legend layers={active} />}
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={basemap} onChange={(e) => setBasemap(e.target.checked)} />Fond de carte OSM (contexte)</label>
          <form onSubmit={doSearch} className="space-y-1" role="search">
            <label htmlFor="q" className="text-sm font-semibold">Rechercher un lieu</label>
            <div className="flex gap-1"><input id="q" className="field min-w-0 flex-1" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Douala ou 4.05, 9.70" /><button className="btn" type="submit">Aller</button></div>
            {searchMsg && <p className="text-xs text-slate-400" role="status">{searchMsg}</p>}
          </form>
          <section aria-labelledby="h-aoi" className="space-y-2">
            <h2 id="h-aoi" className="text-sm font-semibold">Zone d'intérêt</h2>
            <div className="flex gap-1">
              <button className="btn" aria-pressed={tool === "circle"} onClick={() => { setTool(tool === "circle" ? "none" : "circle"); setRectStart(null); }}>Cercle</button>
              <button className="btn" aria-pressed={tool === "rect"} onClick={() => { setTool(tool === "rect" ? "none" : "rect"); setRectStart(null); }}>Rectangle</button>
            </div>
            {tool === "circle" && <label className="block text-xs">Rayon : {radius} km<input type="range" min={1} max={25} value={radius} onChange={(e) => setRadius(+e.target.value)} className="w-full" /></label>}
            {tool !== "none" && <p className="text-xs text-slate-400">{tool === "circle" ? "Cliquez sur la carte pour placer le centre." : rectStart ? "Cliquez sur le coin opposé." : "Cliquez sur un premier coin."}</p>}
            {draftBbox && <button className="btn btn-primary" onClick={saveAoi}>Enregistrer la zone</button>}
            {s.aoi && <p className="text-xs text-slate-300">Zone active : {s.aoi.title}, {fmtKm2(s.aoi.area_km2)}</p>}
            {aoiMsg && <p className="text-xs text-slate-300" role="status">{aoiMsg}</p>}
          </section>
        </aside>
        <div className="relative min-h-[50vh] flex-1">
          {!layers.loading && !dates.length && (
            <div className="absolute inset-x-4 top-4 z-10 max-w-lg">
              <Empty>
                <p className="font-medium">Aucune acquisition NISAR n'est disponible dans le catalogue.</p>
                <p className="mt-1 text-slate-400">Ingérez des granules réels (voir le README, commande <code>ingest-remote</code>) ou cochez « données de démonstration simulées » pour essayer l'interface.</p>
              </Empty>
            </div>
          )}
          {compare && s.date && s.compareDate ? (
            <Swipe center={s.center} zoom={s.zoom} basemap={basemap} before={rasters} after={afterRasters}
              beforeLabel={fmtDate(s.date)} afterLabel={fmtDate(s.compareDate)} onMove={s.setView} />
          ) : (
            <MapView center={s.center} zoom={s.zoom} rasters={rasters} basemap={basemap} geojson={draft ?? undefined} fitBounds={fit}
              onClick={onMapClick} onMove={s.setView} marker={pixel ? [pixel.lon, pixel.lat] : null} label="Carte des observations NISAR" />
          )}
          {missing.length > 0 && <p className="absolute bottom-2 left-2 z-10 rounded bg-ink-900/90 px-2 py-1 text-xs text-warn" role="status">Pas d'acquisition à cette date pour : {missing.map((l) => l.label).join(", ")}.</p>}
          {pixel && s.date && !compare && (
            <div className="absolute right-2 top-2 z-10 max-h-[calc(100%-1rem)] overflow-y-auto">
              <PixelPanel lon={pixel.lon} lat={pixel.lat} date={s.date} demo={s.demo} layer={primary?.key} onClose={() => setPixel(null)} />
            </div>
          )}
        </div>
      </div>
      {dates.length > 0 && (
        <>
          <Timeline dates={dates} value={s.date} onChange={s.setDate} />
          <div className="flex flex-wrap items-center gap-3 border-t border-ink-600 bg-ink-800 px-3 py-2 text-xs">
            <label className="flex items-center gap-2"><input type="checkbox" checked={compare} disabled={dates.length < 2}
              onChange={(e) => { setCompare(e.target.checked); if (e.target.checked && !s.compareDate) s.setCompareDate(dates[0]); }} />Comparer avant / après</label>
            {compare && (
              <label className="flex items-center gap-1">Date « après »
                <select className="field" value={s.compareDate ?? ""} onChange={(e) => s.setCompareDate(e.target.value)}>
                  {dates.map((d) => <option key={d} value={d}>{fmtDate(d)}</option>)}
                </select>
              </label>
            )}
            {dataset && (
              <span className="flex flex-wrap items-center gap-2 text-slate-300">
                <MaturityBadge maturity={dataset.maturity} /> {dataset.source_id}
                {dataset.resolution_m ? ` · ${dataset.resolution_m} m` : ""} · {dataset.crs}
                {dataset.orbit_direction ? ` · ${dataset.orbit_direction}` : ""}{dataset.track != null ? ` · trace ${dataset.track}` : ""}
                {dataset.license ? ` · ${dataset.license}` : ""}
              </span>
            )}
          </div>
        </>
      )}
    </div>
  );
}

function circle(lon: number, lat: number, km: number): GeoJSON.Polygon {
  const pts: [number, number][] = [];
  for (let i = 0; i <= 64; i++) {
    const a = (i / 64) * 2 * Math.PI;
    pts.push([lon + (km / (111.32 * Math.cos((lat * Math.PI) / 180))) * Math.cos(a), lat + (km / 110.57) * Math.sin(a)]);
  }
  return { type: "Polygon", coordinates: [pts] };
}
function bboxPoly([w, s, e, n]: [number, number, number, number]): GeoJSON.Polygon {
  return { type: "Polygon", coordinates: [[[w, s], [e, s], [e, n], [w, n], [w, s]]] };
}
