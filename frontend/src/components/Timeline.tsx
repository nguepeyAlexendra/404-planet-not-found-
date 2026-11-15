import { useEffect, useRef, useState } from "react";
import { fmtDate } from "../lib/format";

interface Props { dates: string[]; value: string | null; onChange: (d: string) => void; label?: string }

/** Chronologie limitée aux dates réellement disponibles (jamais interpolées). */
export function Timeline({ dates, value, onChange, label = "Date d'acquisition" }: Props) {
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1200);
  const idx = value ? dates.indexOf(value) : -1;
  const ref = useRef({ idx, dates, onChange });
  ref.current = { idx, dates, onChange };

  useEffect(() => {
    if (!playing) return;
    const t = setInterval(() => {
      const { idx: i, dates: ds, onChange: cb } = ref.current;
      if (!ds.length) return;
      cb(ds[(i + 1) % ds.length]);
    }, speed);
    return () => clearInterval(t);
  }, [playing, speed]);

  if (!dates.length) return null;
  return (
    <div className="flex flex-wrap items-center gap-3 border-t border-ink-600 bg-ink-800 px-3 py-2 text-sm">
      <button className="btn" onClick={() => setPlaying((p) => !p)} aria-pressed={playing}>{playing ? "Pause" : "Lecture"}</button>
      <label className="flex items-center gap-1 text-xs text-slate-400">Vitesse
        <select className="field" value={speed} onChange={(e) => setSpeed(+e.target.value)} aria-label="Vitesse de lecture">
          <option value={2400}>lente</option><option value={1200}>normale</option><option value={500}>rapide</option>
        </select>
      </label>
      <input type="range" min={0} max={dates.length - 1} step={1} value={Math.max(idx, 0)} aria-label={label}
        aria-valuetext={value ? fmtDate(value) : undefined} className="min-w-40 flex-1"
        onChange={(e) => { setPlaying(false); onChange(dates[+e.target.value]); }} />
      <span className="min-w-28 text-right font-medium" data-testid="timeline-date">{value ? fmtDate(value) : "-"}</span>
      <span className="text-xs text-slate-400">{dates.length} date{dates.length > 1 ? "s" : ""} réelle{dates.length > 1 ? "s" : ""}</span>
    </div>
  );
}
