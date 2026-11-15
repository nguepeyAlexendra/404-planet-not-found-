import type { Layer } from "../api/types";
import { RampLegend } from "./Legend";

export function Legend({ layers }: { layers: Layer[] }) {
  return (
    <section aria-labelledby="h-legend" className="space-y-2">
      <h2 id="h-legend" className="text-sm font-semibold">Légende</h2>
      {layers.map((l) => (<div key={l.key}><p className="text-xs">{l.label}</p><RampLegend layer={l} /></div>))}
      <p className="text-xs text-slate-400">Valeurs en décibels (10·log10 de la puissance linéaire). Les pixels sans donnée sont transparents, jamais affichés comme 0.</p>
    </section>
  );
}
