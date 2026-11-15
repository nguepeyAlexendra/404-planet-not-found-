import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api/client";
import { useAsync } from "../lib/async";
import { fmtDate, fmtDb } from "../lib/format";
import { ErrorBox, Loading, MaturityBadge, Prototype } from "./ui";

interface Props { lon: number; lat: number; date: string; demo: boolean; layer?: string; onClose: () => void }

export function PixelPanel({ lon, lat, date, demo, layer, onClose }: Props) {
  const { data, error, loading, reload } = useAsync(() => api.pixel(lon, lat, date, demo, layer), [lon, lat, date, demo, layer]);
  return (
    <aside className="card w-80 max-w-full space-y-3 overflow-y-auto text-sm" aria-label="Valeurs du pixel">
      <div className="flex items-start justify-between">
        <h3 className="font-semibold">Pixel sélectionné</h3>
        <button className="btn" onClick={onClose} aria-label="Fermer le panneau du pixel">Fermer</button>
      </div>
      <p className="text-xs text-slate-400">{lat.toFixed(5)} N, {lon.toFixed(5)} E, {fmtDate(date)}</p>
      {loading && <Loading />}
      {error && <ErrorBox message={error} onRetry={reload} />}
      {data && (
        <>
          <div className="flex items-center gap-2"><MaturityBadge maturity={data.maturity} /><span className="text-xs text-slate-400">{data.source_id}</span></div>
          <table className="w-full text-left">
            <caption className="sr-only">Valeurs par bande</caption>
            <thead className="text-xs text-slate-400"><tr><th>Bande</th><th>Linéaire</th><th>Valeur</th></tr></thead>
            <tbody>
              {Object.entries(data.bands).map(([b, v]) => (
                <tr key={b}>
                  <td className="py-0.5">{b}</td>
                  <td>{v.linear == null ? "non disponible" : v.linear.toExponential(2)}</td>
                  <td>{v.status === "ok" ? fmtDb(v.db) : <span title={v.reason ?? ""}>non disponible</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="text-xs text-slate-400">Unité : {data.units}</p>
          {data.interpretation && (
            <div className="space-y-1">
              <p><strong>{data.interpretation.label}</strong> <span className="text-xs text-slate-400">(hypothèse probable)</span></p>
              <p className="text-slate-300">{data.interpretation.explanation}</p>
              <Prototype>{data.interpretation.caution} Règles : {data.interpretation.ruleset_version}.</Prototype>
            </div>
          )}
          {data.series.length > 1 && (
            <div className="h-36" aria-label="Évolution du signal HH sur les dates disponibles">
              <ResponsiveContainer>
                <LineChart data={data.series} margin={{ left: -10, right: 8, top: 4 }}>
                  <CartesianGrid stroke="#26345a" />
                  <XAxis dataKey="date" tick={{ fontSize: 10, fill: "#94a3b8" }} tickFormatter={(d: string) => d.slice(5)} />
                  <YAxis tick={{ fontSize: 10, fill: "#94a3b8" }} unit=" dB" domain={["auto", "auto"]} />
                  <Tooltip contentStyle={{ background: "#111a2e", border: "1px solid #26345a" }} />
                  <Line type="linear" dataKey="db" stroke="#4cc2ff" dot connectNulls={false} isAnimationActive={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
        </>
      )}
    </aside>
  );
}
