import { create } from "zustand";

export interface Aoi { id: number; title: string; area_km2: number }

interface State {
  demo: boolean;                      // afficher les données simulées
  setDemo: (v: boolean) => void;
  center: [number, number];
  zoom: number;
  setView: (center: [number, number], zoom: number) => void;
  date: string | null;                // date réellement disponible
  setDate: (d: string | null) => void;
  compareDate: string | null;
  setCompareDate: (d: string | null) => void;
  activeLayers: string[];
  toggleLayer: (key: string, on?: boolean) => void;
  moveLayer: (key: string, dir: -1 | 1) => void;
  opacity: Record<string, number>;
  setOpacity: (key: string, v: number) => void;
  aoi: Aoi | null;
  setAoi: (a: Aoi | null) => void;
}

export const useApp = create<State>((set) => ({
  demo: false,
  setDemo: (demo) => set({ demo, date: null, compareDate: null }),
  center: [9.7, 4.05],
  zoom: 9,
  setView: (center, zoom) => set({ center, zoom }),
  date: null,
  setDate: (date) => set({ date }),
  compareDate: null,
  setCompareDate: (compareDate) => set({ compareDate }),
  activeLayers: ["nisar-gcov-hh"],
  toggleLayer: (key, on) => set((s) => {
    const has = s.activeLayers.includes(key);
    const want = on ?? !has;
    if (want === has) return s;
    return { activeLayers: want ? [...s.activeLayers, key] : s.activeLayers.filter((k) => k !== key) };
  }),
  moveLayer: (key, dir) => set((s) => {
    const a = [...s.activeLayers], i = a.indexOf(key), j = i + dir;
    if (i < 0 || j < 0 || j >= a.length) return s;
    [a[i], a[j]] = [a[j], a[i]];
    return { activeLayers: a };
  }),
  opacity: {},
  setOpacity: (key, v) => set((s) => ({ opacity: { ...s.opacity, [key]: v } })),
  aoi: null,
  setAoi: (aoi) => set({ aoi }),
}));
