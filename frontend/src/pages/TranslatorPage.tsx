import { useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import type { ChangeResult } from "../api/types";
import { ChangeLegend, ClassLegend, RampLegend } from "../components/Legend";
import { MapView, type RasterSpec } from "../components/MapView";
import { PixelPanel } from "../components/PixelPanel";
import { Timeline } from "../components/Timeline";
import { Empty, ErrorBox, Loading, MaturityBadge, Prototype } from "../components/ui";
import { useAsync } from "../lib/async";
import { fmtDate, fmtKm2 } from "../lib/format";
import { changeTileUrl, tileUrl } from "../lib/tiles";
import { useApp } from "../store";

type Mode = "raw" | "semantic" | "change";
const MODES: { id: Mode; label: string; hint: string }[] = [
  { id: "raw", label: "Signal brut", hint: "Rétrodiffusion en dB, sans interprétation." },
  { id: "semantic", label: "Lecture sémantique", hint: "Classes déduites par des règles simples (prototype non validé)." },
  { id: "change", label: "Changements", hint: "Différence de signal en dB entre deux dates." },
];

export function TranslatorPage() {
  const s = useApp();
  const [mode, setMode] = useState<Mode>("semantic");
  const [band, setBand] = useState<"HHHH" | "HVHV">("HHHH");
  const [threshold, setThreshold] = useState(3);
  const [pixel, setPixel] = useState<{ lon: number; lat: number } | null>(null);
  const [chg, setChg] = useState<{ result: ChangeResult | null; error: string | null; loading: boolean }>({ result: null, error: null, loading: false });
  const layers = useAsync(() => api.layers(s.demo), [s.demo]);
  const ruleset = useAsync(() => api.ruleset(), []);
  const hh = layers.data?.find((l) => l.band === "HHHH");
  const hv = layers.data?.find((l) => l.band === "HVHV");
  const layer = band === "HHHH" ? hh : hv;
  const both = (hh?.coverage?.dates ?? []).filter((d) => hv?.coverage?.dates.includes(d));
  const dates = mode === "semantic" ? both : layer?.coverage?.dates ?? [];
  const meta = useAsync(() => (hh ? api.layerMetadata(hh.key, s.demo) : Promise.resolve(null)), [hh?.key, s.demo]);
  const metaHv = useAsync(() => (hv ? api.layerMetadata(hv.key, s.demo) : Promise.resolve(null)), [hv?.key, s.demo]);
  const dsFor = (date: string | null, m = meta.data) => m?.datasets.find((d) => d.date === date);
  const ds = dsFor(s.date);
  const after = s.compareDate;

  useEffect(() => {
    if (!dates.length) return;
    if (!s.date || !dates.includes(s.date)) s.setDate(dates[dates.length - 1]);
    if (mode === "change" && (!after || !dates.includes(after) || after === s.date)) s.setCompareDate(dates.length > 1 ? dates[0] : null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dates.join(","), mode]);

  const cls = useAsync(() => (mode === "semantic" && ds ? api.classification(ds.id, s.aoi?.id) : Promise.resolve(null)), [mode, ds?.id, s.aoi?.id]);

  const changePair = useMemo(() => {
    if (mode !== "change" || !s.date || !after || s.date === after || !layer) return null;
    const [a, b] = [after, s.date].sort();
    const m = band === "HHHH" ? meta.data : metaHv.data;
    const da = dsFor(a, m), db = dsFor(b, m);
    return da && db ? { a: da, b: db, ad: a, bd: b } : null;
  }, [mode, s.date, after, band, meta.data, metaHv.data, layer]);

  useEffect(() => {
    if (!changePair) { setChg({ result: null, error: null, loading: false }); return; }
    let alive = true;
    setChg({ result: null, error: null, loading: true });
    api.changes({ before_dataset_id: changePair.a.id, after_dataset_id: changePair.b.id, band, threshold_db: threshold })
      .then((r) => alive && setChg({ result: r, error: null, loading: false }), (e: Error) => alive && setChg({ result: null, error: e.message, loading: false }));
    return () => { alive = false; };
  }, [changePair?.a.id, changePair?.b.id, band, threshold]); // eslint-disable-line

  const rasters: RasterSpec[] = useMemo(() => {
    if (!s.date || !layer) return [];
    if (mode === "raw") return [{ id: "nv-raw", url: tileUrl(layer.key, s.date, s.demo), opacity: 0.9 }];
    if (mode === "semantic" && hh) return [{ id: "nv-cls", url: tileUrl(hh.key, s.date, s.demo, "classes"), opacity: 0.85 }];
    if (mode === "change" && changePair) return [
      { id: "nv-base", url: tileUrl(layer.key, changePair.ad, s.demo), opacity: 0.6 },
      { id: "nv-chg", url: changeTileUrl(layer.key, changePair.ad, changePair.bd, s.demo, threshold), opacity: 0.9 }];
    return [];
  }, [mode, s.date, s.demo, layer?.key, hh?.key, changePair?.a.id, changePair?.b.id, threshold]);

  const missingBand = mode === "semantic" && layers.data && (!hh?.coverage?.available || !hv?.coverage?.available);
  const sameMaturity = !chg.result || !changePair || changePair.a.maturity === changePair.b.maturity;

  return (
    <div className="flex h-full min-h-0 flex-col md:flex-row">
      <aside className="w-full shrink-0 space-y-4 overflow-y-auto border-ink-600 bg-ink-800 p-3 md:w-80 md:border-r" aria-label="Réglages du traducteur">
        <h1 className="text-lg font-semibold">Traducteur radar</h1>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={s.demo} onChange={(e) => s.setDemo(e.target.checked)} />Données de démonstration simulées</label>
        <div role="tablist" aria-label="Mode d'affichage" className="flex flex-col gap-1">
          {MODES.map((m) => (
            <button key={m.id} role="tab" aria-selected={mode === m.id} className={`btn justify-start ${mode === m.id ? "btn-primary" : ""}`} onClick={() => setMode(m.id)}>{m.label}</button>
          ))}
        </div>
        <p className="text-xs text-slate-400">{MODES.find((m) => m.id === mode)?.hint}</p>
        {mode !== "semantic" && (
          <label className="block text-sm">Polarisation
            <select className="field ml-2" value={band} onChange={(e) => setBand(e.target.value as "HHHH" | "HVHV")}>
              <option value="HHHH">HH</option><option value="HVHV">HV</option>
            </select>
          </label>
        )}
        {mode === "change" && (
          <div className="space-y-2 text-sm">
            <label className="block">Seuil de changement : {threshold} dB<input type="range" min={1} max={10} step={0.5} value={threshold} onChange={(e) => setThreshold(+e.target.value)} className="w-full" /></label>
            <label className="block">Date de comparaison
              <select className="field ml-2" value={after ?? ""} onChange={(e) => s.setCompareDate(e.target.value)}>
                {dates.filter((d) => d !== s.date).map((d) => <option key={d} value={d}>{fmtDate(d)}</option>)}
              </select>
            </label>
          </div>
        )}
        {layers.loading && <Loading />}
        {layers.error && <ErrorBox message={layers.error} onRetry={layers.reload} />}
        {missingBand && <Empty>La lecture sémantique demande les bandes HH et HV. Au moins une bande est non disponible : l'analyse est impossible.</Empty>}
        {mode === "raw" && layer && <RampLegend layer={layer} />}
        {mode === "semantic" && ruleset.data && <ClassLegend classes={ruleset.data.config.classes} />}
        {mode === "change" && <ChangeLegend threshold={threshold} />}
        {mode === "semantic" && (
          <section aria-label="Proportions par classe" className="space-y-1 text-sm">
            <h2 className="font-semibold">Répartition {s.aoi ? `dans « ${s.aoi.title} »` : "sur l'emprise du produit"}</h2>
            {cls.loading && <Loading />}
            {cls.error && <ErrorBox message={cls.error} onRetry={cls.reload} />}
            {cls.data && (
              <ul>
                {cls.data.classes.filter((c) => c.pixels > 0).map((c) => (
                  <li key={c.class_id} className="flex justify-between gap-2"><span><span className="mr-1 inline-block h-2 w-2 rounded-sm" style={{ background: c.color }} />{c.label}</span><span>{c.pct.toFixed(1)} % · {fmtKm2(c.area_km2)}</span></li>
                ))}
              </ul>
            )}
          </section>
        )}
        {mode === "change" && (
          <section aria-label="Résumé des changements" className="space-y-1 text-sm">
            {chg.loading && <Loading />}
            {chg.error && <ErrorBox message={chg.error} />}
            {!sameMaturity && <ErrorBox message="Les deux produits n'ont pas le même niveau de maturité. La comparaison est affichée à titre indicatif seulement." />}
            {chg.result && (
              <>
                <p>Entre {fmtDate(chg.result.before.date)} et {fmtDate(chg.result.after.date)} :</p>
                <ul className="list-inside list-disc text-slate-300">
                  <li>Baisse du signal : {chg.result.summary.decrease_pct} %</li>
                  <li>Hausse du signal : {chg.result.summary.increase_pct} %</li>
                  <li>Stable : {chg.result.summary.stable_pct} %</li>
                  <li>Surface modifiée : {fmtKm2(chg.result.summary.changed_area_km2)} sur {fmtKm2(chg.result.summary.valid_area_km2)} valides</li>
                </ul>
                {chg.result.limits.map((l) => <p key={l} className="text-xs text-slate-400">{l}</p>)}
              </>
            )}
          </section>
        )}
        {ruleset.data && (
          <details className="text-xs text-slate-300">
            <summary className="cursor-pointer">Règles utilisées ({ruleset.data.version})</summary>
            <ul className="mt-1 space-y-0.5">{Object.entries(ruleset.data.config.thresholds_db).map(([k, v]) => <li key={k}>{k} : {v} dB</li>)}</ul>
          </details>
        )}
        {(mode === "semantic" || mode === "change") && <Prototype>{ruleset.data?.notes ?? "Règles de prototype non validées."} Résultat indicatif, aucune mesure de précision n'est affichée car aucune n'a été établie.</Prototype>}
      </aside>
      <div className="flex min-h-[50vh] flex-1 flex-col">
        <div className="relative flex-1">
          {dates.length === 0 && !layers.loading && (
            <div className="absolute inset-x-4 top-4 z-10 max-w-lg"><Empty>Aucune acquisition disponible pour ce mode. Ingérez des données NISAR ou activez la démonstration simulée.</Empty></div>
          )}
          <MapView center={s.center} zoom={s.zoom} rasters={rasters} basemap={true} fitBounds={layer?.coverage?.bounds ?? null}
            onClick={(lon, lat) => s.date && setPixel({ lon, lat })} onMove={s.setView} marker={pixel ? [pixel.lon, pixel.lat] : null} label="Carte du traducteur radar" />
          {ds && <span className="absolute bottom-2 left-2 z-10 flex items-center gap-2 rounded bg-ink-900/90 px-2 py-1 text-xs"><MaturityBadge maturity={ds.maturity} />{ds.source_id}</span>}
          {pixel && s.date && (
            <div className="absolute right-2 top-2 z-10 max-h-[calc(100%-1rem)] overflow-y-auto">
              <PixelPanel lon={pixel.lon} lat={pixel.lat} date={s.date} demo={s.demo} layer={hh?.key} onClose={() => setPixel(null)} />
            </div>
          )}
        </div>
        <Timeline dates={dates} value={s.date} onChange={s.setDate} label={mode === "change" ? "Date la plus récente de la comparaison" : "Date d'acquisition"} />
      </div>
    </div>
  );
}
