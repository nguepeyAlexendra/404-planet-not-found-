import type { Map as MLMap } from "maplibre-gl";
import { useRef, useState } from "react";
import { MapView, type RasterSpec } from "./MapView";

interface Props {
  center: [number, number]; zoom: number; basemap: boolean;
  before: RasterSpec[]; after: RasterSpec[];
  beforeLabel: string; afterLabel: string;
  onMove?: (c: [number, number], z: number) => void;
}

/** Deux cartes synchronisées ; la carte « après » est découpée par un curseur. */
export function Swipe({ center, zoom, basemap, before, after, beforeLabel, afterLabel, onMove }: Props) {
  const [pos, setPos] = useState(50);
  const maps = useRef<{ a?: MLMap; b?: MLMap }>({});
  const lock = useRef(false);

  function link() {
    const { a, b } = maps.current;
    if (!a || !b) return;
    const follow = (from: MLMap, to: MLMap) => from.on("move", () => {
      if (lock.current) return;
      lock.current = true;
      to.jumpTo({ center: from.getCenter(), zoom: from.getZoom(), bearing: from.getBearing(), pitch: from.getPitch() });
      lock.current = false;
    });
    follow(a, b); follow(b, a);
  }
  return (
    <div className="relative h-full w-full" data-testid="swipe">
      <MapView center={center} zoom={zoom} rasters={before} basemap={basemap} onMove={onMove} label={`Carte avant, ${beforeLabel}`}
        onReady={(m) => { maps.current.a = m; link(); }} />
      <div className="absolute inset-0" style={{ clipPath: `inset(0 0 0 ${pos}%)` }}>
        <MapView center={center} zoom={zoom} rasters={after} basemap={basemap} label={`Carte après, ${afterLabel}`}
          onReady={(m) => { maps.current.b = m; link(); }} />
      </div>
      <div className="pointer-events-none absolute inset-y-0 w-0.5 bg-white/80" style={{ left: `${pos}%` }} />
      <span className="absolute left-2 top-2 rounded bg-ink-900/80 px-2 py-0.5 text-xs">Avant : {beforeLabel}</span>
      <span className="absolute right-12 top-2 rounded bg-ink-900/80 px-2 py-0.5 text-xs">Après : {afterLabel}</span>
      <input type="range" min={0} max={100} value={pos} onChange={(e) => setPos(+e.target.value)} aria-label="Position du curseur avant/après"
        className="absolute bottom-6 left-1/2 w-2/3 -translate-x-1/2" />
    </div>
  );
}
