import type { Layer, RulesetClass } from "../api/types";

export function RampLegend({ layer }: { layer: Layer }) {
  const [lo, hi] = layer.style.rescale ?? [0, 1];
  return (
    <div className="text-xs" aria-label={`Légende ${layer.label}`}>
      <div className="h-2 w-full rounded" style={{ background: "linear-gradient(to right,#000,#fff)" }} />
      <div className="flex justify-between text-slate-400"><span>{lo} {layer.unit}</span><span>{hi} {layer.unit}</span></div>
    </div>
  );
}

export function ClassLegend({ classes }: { classes: Record<string, RulesetClass> }) {
  return (
    <ul className="space-y-1 text-xs" aria-label="Légende des classes">
      {Object.entries(classes).map(([id, c]) => (
        <li key={id} className="flex items-center gap-2"><span className="inline-block h-3 w-3 rounded-sm" style={{ background: c.color }} />{c.label}</li>
      ))}
    </ul>
  );
}

export function ChangeLegend({ threshold }: { threshold: number }) {
  return (
    <ul className="space-y-1 text-xs" aria-label="Légende des changements">
      <li className="flex items-center gap-2"><span className="inline-block h-3 w-3 rounded-sm bg-red-500" />Hausse du signal supérieure à {threshold} dB</li>
      <li className="flex items-center gap-2"><span className="inline-block h-3 w-3 rounded-sm bg-blue-500" />Baisse du signal supérieure à {threshold} dB</li>
      <li className="flex items-center gap-2"><span className="inline-block h-3 w-3 rounded-sm border border-slate-500" />Transparent : pas de changement notable</li>
    </ul>
  );
}
