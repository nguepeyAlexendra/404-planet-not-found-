import maplibregl, { type Map as MLMap } from "maplibre-gl";
import { useEffect, useRef } from "react";

export interface RasterSpec { id: string; url: string; opacity: number }

interface Props {
  center: [number, number];
  zoom: number;
  rasters: RasterSpec[];
  basemap: boolean;
  geojson?: GeoJSON.Geometry | null;
  onClick?: (lon: number, lat: number) => void;
  onMove?: (center: [number, number], zoom: number) => void;
  onReady?: (map: MLMap) => void;
  marker?: [number, number] | null;
  label: string;
  fitBounds?: [number, number, number, number] | null;
}

const abs = (u: string) => (u.startsWith("http") ? u : window.location.origin + u);

function style(basemap: boolean): maplibregl.StyleSpecification {
  return {
    version: 8,
    sources: basemap
      ? { osm: { type: "raster", tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"], tileSize: 256, attribution: "© OpenStreetMap (contexte)", maxzoom: 19 } }
      : {},
    layers: [
      { id: "bg", type: "background", paint: { "background-color": "#0b1220" } },
      ...(basemap ? [{ id: "osm", type: "raster" as const, source: "osm", paint: { "raster-opacity": 0.55, "raster-saturation": -0.6 } }] : []),
    ],
  };
}

export function MapView({ center, zoom, rasters, basemap, geojson, onClick, onMove, onReady, marker, label, fitBounds }: Props) {
  const el = useRef<HTMLDivElement>(null);
  const map = useRef<MLMap | null>(null);
  const markerRef = useRef<maplibregl.Marker | null>(null);
  const cb = useRef({ onClick, onMove });
  cb.current = { onClick, onMove };
  const ready = useRef(false);
  const latest = useRef({ rasters, geojson });
  latest.current = { rasters, geojson };

  useEffect(() => {
    if (!el.current) return;
    const m = new maplibregl.Map({ container: el.current, style: style(basemap), center, zoom, attributionControl: { compact: true } });
    map.current = m;
    m.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    m.addControl(new maplibregl.ScaleControl({ unit: "metric" }), "bottom-left");
    m.on("click", (e) => cb.current.onClick?.(e.lngLat.lng, e.lngLat.lat));
    m.on("moveend", () => { const c = m.getCenter(); cb.current.onMove?.([c.lng, c.lat], m.getZoom()); });
    m.on("load", () => { ready.current = true; sync(); onReady?.(m); });
    return () => { ready.current = false; m.remove(); map.current = null; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [basemap]);

  function sync() {
    const m = map.current;
    if (!m || !ready.current) return;
    const { rasters: rs, geojson: g } = latest.current;
    const wanted = new Set(rs.map((r) => r.id));
    (m.getStyle().layers ?? []).forEach((l) => {
      if (l.id.startsWith("nv-") && l.id !== "nv-aoi-fill" && l.id !== "nv-aoi-line" && !wanted.has(l.id)) { m.removeLayer(l.id); if (m.getSource(l.id)) m.removeSource(l.id); }
    });
    rs.forEach((r, i) => {
      const src = m.getSource(r.id) as maplibregl.RasterTileSource | undefined;
      const tiles = [abs(r.url)];
      if (src && (src as unknown as { tiles: string[] }).tiles?.[0] !== tiles[0]) { m.removeLayer(r.id); m.removeSource(r.id); }
      if (!m.getSource(r.id)) {
        m.addSource(r.id, { type: "raster", tiles, tileSize: 256 });
        m.addLayer({ id: r.id, type: "raster", source: r.id, paint: { "raster-opacity": r.opacity, "raster-fade-duration": 0 } }, m.getLayer("nv-aoi-fill") ? "nv-aoi-fill" : undefined);
      } else m.setPaintProperty(r.id, "raster-opacity", r.opacity);
      void i;
    });
    // l'ordre du panneau : le premier de la liste est dessous
    let prev: string | undefined;
    [...rs].reverse().forEach((r) => { if (m.getLayer(r.id)) { if (prev) m.moveLayer(r.id, prev); prev = r.id; } });
    if (g) {
      const data = { type: "Feature" as const, properties: {}, geometry: g };
      const s = m.getSource("nv-aoi") as maplibregl.GeoJSONSource | undefined;
      if (s) s.setData(data);
      else {
        m.addSource("nv-aoi", { type: "geojson", data });
        m.addLayer({ id: "nv-aoi-fill", type: "fill", source: "nv-aoi", paint: { "fill-color": "#4cc2ff", "fill-opacity": 0.12 } });
        m.addLayer({ id: "nv-aoi-line", type: "line", source: "nv-aoi", paint: { "line-color": "#4cc2ff", "line-width": 2 } });
      }
    } else if (m.getSource("nv-aoi")) { m.removeLayer("nv-aoi-fill"); m.removeLayer("nv-aoi-line"); m.removeSource("nv-aoi"); }
  }

  useEffect(sync, [rasters, geojson]);

  useEffect(() => {
    const m = map.current;
    if (!m) return;
    const c = m.getCenter();
    if (Math.abs(c.lng - center[0]) > 1e-6 || Math.abs(c.lat - center[1]) > 1e-6 || Math.abs(m.getZoom() - zoom) > 0.01) {
      m.easeTo({ center, zoom, duration: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : 900 });
    }
  }, [center, zoom]);

  useEffect(() => {
    const m = map.current;
    if (m && fitBounds) m.fitBounds([[fitBounds[0], fitBounds[1]], [fitBounds[2], fitBounds[3]]], { padding: 40, duration: 0 });
  }, [fitBounds]);

  useEffect(() => {
    const m = map.current;
    if (!m) return;
    markerRef.current?.remove();
    markerRef.current = marker ? new maplibregl.Marker({ color: "#f5b942" }).setLngLat(marker).addTo(m) : null;
  }, [marker]);

  return <div ref={el} className="h-full w-full" role="application" aria-label={label} data-testid="map" />;
}
