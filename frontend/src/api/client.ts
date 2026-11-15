import type {
  AOI, ChangeMatrixResult, Classification, GlossaryTerm, Job, Layer, LayerMetadata, LevelDetail, LevelSummary, PixelInfo,
  ProjectionResult, Ruleset, ChangeResult, AttemptResult, Progress, Story, StorySummary, TimeSeriesResult,
} from "./types";

const BASE = "/api/v1";

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string, public requestId?: string) { super(message); }
}

export function clientId(): string {
  try {
    let id = localStorage.getItem("nv_client_id");
    if (!id) { id = crypto.randomUUID(); localStorage.setItem("nv_client_id", id); }
    return id;
  } catch { return sessionId; }
}
const sessionId = typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : "00000000-0000-4000-8000-000000000000";

async function req<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = { "X-Client-Id": clientId(), ...(init.headers as Record<string, string> | undefined) };
  if (init.body) headers["Content-Type"] = "application/json";
  let r: Response;
  try { r = await fetch(BASE + path, { ...init, headers }); }
  catch { throw new ApiError(0, "network", "Le serveur ne répond pas. Vérifiez que l'API est démarrée."); }
  if (!r.ok) {
    let code = "http_" + r.status, message = "Erreur " + r.status, rid: string | undefined;
    try { const j = await r.json(); code = j.error?.code ?? code; message = j.error?.message ?? j.detail ?? message; rid = j.error?.request_id; } catch { /* corps non JSON */ }
    throw new ApiError(r.status, code, typeof message === "string" ? message : "Requête invalide", rid);
  }
  return r.json() as Promise<T>;
}
const post = <T,>(p: string, body: unknown, idem?: string) =>
  req<T>(p, { method: "POST", body: JSON.stringify(body), headers: idem ? { "Idempotency-Key": idem } : undefined });
const qs = (o: Record<string, string | number | boolean | undefined>) =>
  Object.entries(o).filter(([, v]) => v !== undefined).map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`).join("&");

export const api = {
  layers: (demo: boolean) => req<Layer[]>(`/layers?${qs({ include_demo: demo })}`),
  layerMetadata: (key: string, demo: boolean) => req<LayerMetadata>(`/layers/${key}/metadata?${qs({ include_demo: demo })}`),
  pixel: (lon: number, lat: number, date: string, demo: boolean, layer?: string) =>
    req<PixelInfo>(`/map/pixel?${qs({ lon, lat, date, include_demo: demo, layer })}`),
  ruleset: () => req<Ruleset>("/translator/ruleset"),
  classification: (datasetId: number, aoiId?: number) => req<Classification>(`/translator/classification?${qs({ dataset_id: datasetId, aoi_id: aoiId })}`),
  changes: (b: { before_dataset_id: number; after_dataset_id: number; band: string; threshold_db: number }) =>
    post<ChangeResult>("/translator/changes", b),
  stories: () => req<StorySummary[]>("/stories"),
  story: (slug: string) => req<Story>(`/stories/${slug}`),
  levels: () => req<LevelSummary[]>("/learning/levels"),
  level: (id: number) => req<LevelDetail>(`/learning/levels/${id}`),
  attempt: (quizId: number, answers: Record<number, number>) =>
    post<AttemptResult>(
      `/learning/quiz/${quizId}/attempts`, { answers }),
  progress: () => req<Progress>("/learning/progress"),
  glossary: (q?: string) => req<GlossaryTerm[]>(`/learning/glossary?${qs({ q: q || undefined })}`),
  certificate: (name: string) => post<{ code: string; holder_name: string; issued_at: string; verify_url: string }>("/learning/certificate", { name }),
  createAoi: (b: { title: string; center?: [number, number]; radius_km?: number; bbox?: [number, number, number, number]; geometry?: unknown }) =>
    post<AOI>("/analytics/aoi", b),
  timeSeries: (b: Record<string, unknown>) => post<Job<TimeSeriesResult>>("/analytics/time-series", b),
  changeMatrix: (b: Record<string, unknown>) => post<Job<ChangeMatrixResult>>("/analytics/change-matrix", b),
  projection: (b: Record<string, unknown>) => post<Job<ProjectionResult>>("/analytics/projection", b),
  job: <T,>(id: string) => req<Job<T>>(`/jobs/${id}`),
  cancelJob: (id: string) => post<Job>(`/jobs/${id}/cancel`, {}),
  createExport: (jobId: string, format: string) => post<Job<{ export_id: string; format: string; size_bytes: number; download_path: string; expires_at: string }>>("/exports", { job_id: jobId, format }),
  exportUrl: (id: string) => `${BASE}/exports/${id}/download`,
};

export async function pollJob<T>(job: Job<T>, onProgress?: (p: number) => void, signal?: AbortSignal): Promise<Job<T>> {
  let j = job, delay = 400;
  while (j.status === "queued" || j.status === "running") {
    if (signal?.aborted) throw new DOMException("annulé", "AbortError");
    onProgress?.(j.progress);
    await new Promise((r) => setTimeout(r, delay));
    delay = Math.min(delay * 1.5, 2500);
    j = await api.job<T>(j.job_id);
  }
  onProgress?.(j.progress);
  return j;
}
