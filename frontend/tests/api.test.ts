import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, api, clientId, pollJob } from "../src/api/client";

afterEach(() => { vi.restoreAllMocks(); vi.useRealTimers(); });

describe("client API", () => {
  it("envoie l'identifiant anonyme et décode les erreurs structurées", async () => {
    const f = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ error: { code: "not_found", message: "Introuvable.", request_id: "r1" } }), { status: 404 }));
    await expect(api.level(99)).rejects.toMatchObject({ status: 404, code: "not_found", message: "Introuvable.", requestId: "r1" });
    const headers = (f.mock.calls[0][1] as RequestInit).headers as Record<string, string>;
    expect(headers["X-Client-Id"]).toBe(clientId());
  });
  it("traduit un échec réseau en message lisible", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("fail"));
    const e = (await api.layers(false).then(() => null, (x: unknown) => x)) as ApiError;
    expect(e).toBeInstanceOf(ApiError);
    expect(e.code).toBe("network");
  });
  it("l'identifiant client est stable", () => { expect(clientId()).toBe(clientId()); });
  it("pollJob s'arrête sur un état final", async () => {
    vi.useFakeTimers();
    const mk = (status: string, progress: number) => ({ job_id: "j", kind: "k", status, progress, error_message: null, result: null, method_version: null }) as never;
    vi.spyOn(api, "job").mockResolvedValueOnce(mk("running", 0.5)).mockResolvedValueOnce(mk("succeeded", 1));
    const seen: number[] = [];
    const p = pollJob(mk("queued", 0), (x) => seen.push(x));
    await vi.advanceTimersByTimeAsync(10_000);
    const done = await p;
    expect(done.status).toBe("succeeded");
    expect(seen).toContain(1);
  });
});
