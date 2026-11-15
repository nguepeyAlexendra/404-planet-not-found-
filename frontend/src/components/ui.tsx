import type { ReactNode } from "react";
import { MATURITY_LABEL } from "../lib/format";

export function Loading({ label = "Chargement…" }: { label?: string }) {
  return <p role="status" className="p-4 text-sm text-slate-400">{label}</p>;
}
export function ErrorBox({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="card border-red-500/50 text-sm">
      <p className="text-red-300">{message}</p>
      {onRetry && <button className="btn mt-2" onClick={onRetry}>Réessayer</button>}
    </div>
  );
}
export function Empty({ children }: { children: ReactNode }) {
  return <div className="card text-sm text-slate-300">{children}</div>;
}
export function MaturityBadge({ maturity }: { maturity: string }) {
  const demo = maturity === "demo";
  return (
    <span className={`rounded px-1.5 py-0.5 text-xs font-medium ${demo ? "bg-warn text-ink-900" : "bg-ink-600 text-accent"}`}>
      {MATURITY_LABEL[maturity] ?? maturity}
    </span>
  );
}
export function Prototype({ children }: { children: ReactNode }) {
  return <p className="rounded border border-warn/60 bg-warn/10 p-2 text-xs text-warn" role="note">{children}</p>;
}
