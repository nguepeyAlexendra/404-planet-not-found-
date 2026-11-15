import { useCallback, useRef, useState } from "react";
import { api, pollJob } from "../api/client";
import type { Job } from "../api/types";

export interface JobState<T> { job: Job<T> | null; running: boolean; progress: number; error: string | null }

export function useJob<T>() {
  const [state, setState] = useState<JobState<T>>({ job: null, running: false, progress: 0, error: null });
  const ctl = useRef<AbortController | null>(null);
  const current = useRef<string | null>(null);

  const run = useCallback(async (start: () => Promise<Job<T>>) => {
    ctl.current?.abort();
    const c = new AbortController();
    ctl.current = c;
    setState({ job: null, running: true, progress: 0, error: null });
    try {
      const first = await start();
      current.current = first.job_id;
      const done = await pollJob(first, (p) => setState((s) => ({ ...s, progress: p })), c.signal);
      if (done.status === "succeeded") setState({ job: done, running: false, progress: 1, error: null });
      else setState({ job: done, running: false, progress: done.progress, error: done.status === "cancelled" ? "Analyse annulée." : done.error_message ?? "L'analyse a échoué." });
    } catch (e) {
      if ((e as Error).name === "AbortError") return;
      setState({ job: null, running: false, progress: 0, error: (e as Error).message });
    }
  }, []);

  const cancel = useCallback(async () => {
    ctl.current?.abort();
    const id = current.current;
    setState((s) => ({ ...s, running: false, error: "Analyse annulée." }));
    if (id) { try { await api.cancelJob(id); } catch { /* le job est peut-être déjà terminé */ } }
  }, []);

  return { ...state, run, cancel };
}

export async function downloadExport(exportId: string, filename: string) {
  const { clientId } = await import("../api/client");
  const r = await fetch(api.exportUrl(exportId), { headers: { "X-Client-Id": clientId() } });
  if (!r.ok) throw new Error(r.status === 404 ? "Export introuvable ou expiré." : `Téléchargement impossible (${r.status}).`);
  const url = URL.createObjectURL(await r.blob());
  const a = document.createElement("a");
  a.href = url; a.download = filename; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}
