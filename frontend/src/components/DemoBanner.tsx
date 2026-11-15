import { useApp } from "../store";

export function DemoBanner() {
  const demo = useApp((s) => s.demo);
  if (!demo) return null;
  return (
    <div role="alert" className="bg-warn px-4 py-1.5 text-center text-sm font-semibold text-ink-900">
      DONNÉES DE DÉMONSTRATION SIMULÉES. Ces images ne sont pas des observations NISAR.
    </div>
  );
}
