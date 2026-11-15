import { useState } from "react";
import {
  SURFACES, type SurfaceKey, classifyFlood, floodBackscatterDb, fringeCount, insarPhase, mmPerFringe, opticalVisibility,
  radarVisibility, rgbComposite, roughnessBackscatterDb, wrapPhase,
} from "./models";

function Shell({ title, children, note }: { title: string; children: React.ReactNode; note: string }) {
  return (
    <section className="card space-y-3" aria-label={`Simulateur : ${title}`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="font-semibold">{title}</h3>
        <span className="rounded bg-warn px-2 py-0.5 text-xs font-medium text-ink-900">Simulation conceptuelle</span>
      </div>
      {children}
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
function Slider({ id, label, value, min, max, step = 1, unit = "", onChange }: { id: string; label: string; value: number; min: number; max: number; step?: number; unit?: string; onChange: (v: number) => void }) {
  return (
    <label htmlFor={id} className="block text-sm">{label} : <strong>{value}{unit}</strong>
      <input id={id} type="range" className="w-full" min={min} max={max} step={step} value={value} onChange={(e) => onChange(+e.target.value)} />
    </label>
  );
}
function Bar({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="text-sm">
      <div className="flex justify-between"><span>{label}</span><span>{Math.round(value * 100)} %</span></div>
      <div className="h-3 w-full rounded bg-ink-700" role="img" aria-label={`${label} ${Math.round(value * 100)} %`}><div className="h-3 rounded" style={{ width: `${value * 100}%`, background: color }} /></div>
    </div>
  );
}

export function DayNight() {
  const [daylight, setDaylight] = useState(0);
  const [cloud, setCloud] = useState(80);
  return (
    <Shell title="Jour, nuit et nuages" note="Illustration qualitative : un capteur optique dépend de la lumière du Soleil, un radar apporte sa propre énergie. Les pourcentages sont indicatifs, pas des mesures.">
      <Slider id="dl" label="Lumière du jour" value={daylight} min={0} max={100} unit=" %" onChange={setDaylight} />
      <Slider id="cl" label="Couverture nuageuse" value={cloud} min={0} max={100} unit=" %" onChange={setCloud} />
      <Bar label="Capteur optique" value={opticalVisibility(daylight / 100, cloud / 100)} color="#f5b942" />
      <Bar label="Radar en bande L" value={radarVisibility(cloud / 100)} color="#4cc2ff" />
    </Shell>
  );
}

export function Roughness() {
  const [rough, setRough] = useState(0.2);
  const [inc, setInc] = useState(35);
  const db = roughnessBackscatterDb(rough, inc);
  const rays = 5;
  return (
    <Shell title="Rugosité et angle d'incidence" note="Modèle qualitatif : plus la surface est rugueuse, plus l'énergie est diffusée vers le radar. Les valeurs en dB montrent une tendance, pas un calcul physique complet.">
      <Slider id="rg" label="Rugosité de la surface" value={rough} min={0} max={1} step={0.05} onChange={setRough} />
      <Slider id="ia" label="Angle d'incidence" value={inc} min={15} max={70} unit="°" onChange={setInc} />
      <svg viewBox="0 0 300 130" className="w-full rounded bg-ink-900" role="img" aria-label={`Rétrodiffusion illustrée : ${db.toFixed(1)} dB`}>
        <path d={surface(rough)} stroke="#a67c52" strokeWidth="3" fill="none" />
        <line x1={150 - 90 * Math.sin((inc * Math.PI) / 180)} y1={100 - 90 * Math.cos((inc * Math.PI) / 180)} x2="150" y2="100" stroke="#4cc2ff" strokeWidth="2" />
        {Array.from({ length: rays }, (_, i) => {
          const spec = (inc * Math.PI) / 180;
          const spread = rough * 1.2;
          const a = spec + (i - (rays - 1) / 2) * spread * 0.6;
          return <line key={i} x1="150" y1="100" x2={150 + 70 * Math.sin(a)} y2={100 - 70 * Math.cos(a)} stroke="#f5b942" strokeWidth="1.5" opacity={0.4 + rough * 0.4} />;
        })}
        <line x1="150" y1="100" x2={150 - 70 * Math.sin((inc * Math.PI) / 180) * rough} y2={100 - 70 * Math.cos((inc * Math.PI) / 180) * rough} stroke="#d13b2f" strokeWidth={1 + rough * 3} />
      </svg>
      <p className="text-sm">Retour vers le radar (illustratif) : <strong>{db.toFixed(1)} dB</strong></p>
    </Shell>
  );
}
function surface(r: number) {
  const pts: string[] = [];
  for (let x = 20; x <= 280; x += 8) pts.push(`${x},${100 + Math.sin(x * 1.7) * 12 * r + Math.sin(x * 0.6) * 5 * r}`);
  return "M" + pts.join(" L");
}

export function Flood() {
  const [wind, setWind] = useState(2);
  const [veg, setVeg] = useState(false);
  const [flooded, setFlooded] = useState(true);
  const db = floodBackscatterDb(wind, veg, flooded);
  const verdict = classifyFlood(db);
  const truth = flooded ? "eau probable" : "terre probable";
  return (
    <Shell title="Détecter l'eau, et ses pièges" note="Seuil illustratif de -18 dB. Dans la réalité, il faut ajuster les seuils au capteur, à la zone et à la saison, puis valider.">
      <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={flooded} onChange={(e) => setFlooded(e.target.checked)} />La zone est inondée</label>
      <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={veg} onChange={(e) => setVeg(e.target.checked)} disabled={!flooded} />Végétation émergée dans l'eau</label>
      <Slider id="wd" label="Vent sur l'eau" value={wind} min={0} max={15} unit=" m/s" onChange={setWind} />
      <p className="text-sm">Signal : <strong>{db.toFixed(1)} dB</strong> → lecture par seuil : <strong>{verdict}</strong></p>
      {verdict !== truth && <p role="alert" className="rounded border border-warn/60 bg-warn/10 p-2 text-sm text-warn">Ici le seuil se trompe. {flooded ? (veg ? "La végétation émergée crée un double rebond qui fait ressembler l'eau à de la terre." : "Le vent rend la surface rugueuse et le signal remonte.") : ""}</p>}
    </Shell>
  );
}

export function Polarization() {
  const [surface, setSurface] = useState<SurfaceKey>("dense_forest");
  const s = SURFACES[surface];
  const [r, g, b] = rgbComposite(s.hh, s.hv);
  return (
    <Shell title="Polarimétrie HH, HV, VV" note="Valeurs typiques illustratives, choisies pour la pédagogie. Elles ne proviennent d'aucune mesure NISAR.">
      <div className="flex flex-wrap gap-1" role="group" aria-label="Type de surface">
        {(Object.keys(SURFACES) as SurfaceKey[]).map((k) => <button key={k} className={`btn ${k === surface ? "btn-primary" : ""}`} aria-pressed={k === surface} onClick={() => setSurface(k)}>{SURFACES[k].label}</button>)}
      </div>
      <table className="w-full text-left text-sm"><caption className="sr-only">Valeurs illustratives par canal</caption>
        <thead className="text-xs text-slate-400"><tr><th>Canal</th><th>dB (illustratif)</th></tr></thead>
        <tbody><tr><td>HH</td><td>{s.hh}</td></tr><tr><td>HV</td><td>{s.hv}</td></tr><tr><td>VV</td><td>{s.vv}</td></tr></tbody></table>
      <div className="flex items-center gap-3"><span className="inline-block h-10 w-10 rounded" style={{ background: `rgb(${Math.round(r * 255)},${Math.round(g * 255)},${Math.round(b * 255)})` }} aria-hidden /><span className="text-sm">Couleur du composite (R=HH, V=HV, B=HH/HV)</span></div>
      <p className="text-sm text-slate-300">{s.why}</p>
    </Shell>
  );
}

export function Insar() {
  const [d, setD] = useState(60);
  const phase = insarPhase(d);
  const w = wrapPhase(phase);
  return (
    <Shell title="InSAR : de la phase au déplacement" note={`Relation 4π·d/λ avec λ ≈ 23,8 cm (bande L). Une frange complète correspond à environ ${mmPerFringe().toFixed(0)} mm de déplacement le long de la ligne de visée. Simplification : on ignore l'atmosphère, la topographie et la décorrélation.`}>
      <Slider id="dp" label="Déplacement le long de la ligne de visée" value={d} min={-300} max={300} step={5} unit=" mm" onChange={setD} />
      <svg viewBox="0 0 300 40" className="w-full rounded" role="img" aria-label={`Franges d'interférence pour ${d} mm`}>
        {Array.from({ length: 150 }, (_, i) => {
          const x = i / 149;
          const ph = wrapPhase(insarPhase(d * x));
          return <rect key={i} x={i * 2} y="0" width="2" height="40" fill={`hsl(${((ph + Math.PI) / (2 * Math.PI)) * 360},80%,55%)`} />;
        })}
      </svg>
      <p className="text-sm">Phase déroulée : {phase.toFixed(2)} rad · phase enroulée : {w.toFixed(2)} rad · franges : {fringeCount(d).toFixed(2)}</p>
    </Shell>
  );
}

export const SIMULATORS: Record<string, () => JSX.Element> = { day_night: DayNight, roughness: Roughness, flood: Flood, polarization: Polarization, insar: Insar };
