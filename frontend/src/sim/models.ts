/** Modèles volontairement simples. Ils illustrent des tendances, ils ne reproduisent aucune mesure. */

export const L_BAND_WAVELENGTH_M = 0.2384; // bande L de NISAR, environ 24 cm

export const toDb = (linear: number) => 10 * Math.log10(linear);
export const fromDb = (db: number) => Math.pow(10, db / 10);

/** Visibilité relative d'un capteur optique : lumière du jour atténuée par les nuages. */
export function opticalVisibility(daylight: number, cloud: number): number {
  return clamp01(daylight) * (1 - clamp01(cloud));
}
/** Un radar en bande L émet son propre signal ; les nuages l'atténuent très peu. */
export function radarVisibility(cloud: number): number {
  return 1 - 0.03 * clamp01(cloud);
}

/** Tendance : surface lisse = réflexion spéculaire (faible retour), surface rugueuse = diffusion (retour fort). */
export function roughnessBackscatterDb(roughness: number, incidenceDeg: number): number {
  const r = clamp01(roughness);
  const theta = (clamp(incidenceDeg, 15, 70) * Math.PI) / 180;
  const specular = -32 + 24 * r; // plus rugueux, plus de retour
  const angleLoss = -12 * (1 - Math.cos(theta)) * (1 - 0.6 * r); // les surfaces rugueuses dépendent moins de l'angle
  return specular + angleLoss + 8 * r * r;
}

export type SurfaceKey = "water" | "dense_forest" | "sparse_veg" | "urban" | "bare_soil";
export const SURFACES: Record<SurfaceKey, { label: string; hh: number; hv: number; vv: number; why: string }> = {
  water: { label: "Eau calme", hh: -24, hv: -30, vv: -22, why: "Réflexion spéculaire : l'onde repart loin du radar." },
  dense_forest: { label: "Forêt dense", hh: -8, hv: -13, vv: -9, why: "Diffusion de volume dans la canopée : le canal croisé HV est fort." },
  sparse_veg: { label: "Végétation clairsemée", hh: -13, hv: -20, vv: -12, why: "Mélange de sol et de feuillage, retour intermédiaire." },
  urban: { label: "Zone bâtie", hh: -3, hv: -14, vv: -4, why: "Double rebond sol-mur : fort retour en co-polarisation." },
  bare_soil: { label: "Sol nu", hh: -15, hv: -24, vv: -14, why: "Surface rugueuse mais sans volume : retour moyen, HV faible." },
};

/** Eau : le vent la rend rugueuse, la végétation émergée crée un double rebond. */
export function floodBackscatterDb(wind: number, emergentVeg: boolean, flooded: boolean): number {
  if (!flooded) return -10;
  const base = -24 + 9 * clamp01(wind / 15);
  return emergentVeg ? Math.max(base, -6) : base;
}
export function classifyFlood(db: number, waterMax = -18): "eau probable" | "terre probable" {
  return db <= waterMax ? "eau probable" : "terre probable";
}

/** Phase mesurée pour un déplacement le long de la ligne de visée : 4π d / λ. */
export function insarPhase(displacementMm: number, wavelengthM = L_BAND_WAVELENGTH_M): number {
  return (4 * Math.PI * (displacementMm / 1000)) / wavelengthM;
}
export function wrapPhase(phase: number): number {
  const t = 2 * Math.PI;
  return ((((phase + Math.PI) % t) + t) % t) - Math.PI;
}
export const mmPerFringe = (wavelengthM = L_BAND_WAVELENGTH_M) => (wavelengthM / 2) * 1000;
export const fringeCount = (displacementMm: number) => Math.abs(displacementMm) / mmPerFringe();

function clamp(v: number, a: number, b: number) { return Math.min(b, Math.max(a, v)); }
function clamp01(v: number) { return clamp(v, 0, 1); }

/** Composite RVB (HH, HV, HH/HV) pour la polarimétrie, valeurs 0..1. */
export function rgbComposite(hh: number, hv: number): [number, number, number] {
  const n = (db: number, lo: number, hi: number) => clamp01((db - lo) / (hi - lo));
  return [n(hh, -25, 0), n(hv, -30, -5), n(hh - hv, 0, 20)];
}
