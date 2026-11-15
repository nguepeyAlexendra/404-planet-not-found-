export const fmtDb = (v: number | null | undefined) => (v == null ? "non disponible" : `${v.toFixed(1)} dB`);
export const fmtKm2 = (v: number) => `${v.toLocaleString("fr-FR", { maximumFractionDigits: 2 })} km²`;
export const fmtDate = (iso: string) => new Date(iso + "T00:00:00Z").toLocaleDateString("fr-FR", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
export const MATURITY_LABEL: Record<string, string> = { beta: "Beta", provisional: "Provisoire", validated: "Validé", demo: "DÉMO simulée" };
export function nearest(dates: string[], target: string): string | null {
  if (!dates.length) return null;
  const t = Date.parse(target);
  return dates.reduce((b, d) => (Math.abs(Date.parse(d) - t) < Math.abs(Date.parse(b) - t) ? d : b));
}
