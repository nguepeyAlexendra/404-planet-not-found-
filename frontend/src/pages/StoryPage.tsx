import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import type { Scene } from "../api/types";
import { MapView } from "../components/MapView";
import { Empty, ErrorBox, Loading, MaturityBadge } from "../components/ui";
import { useAsync } from "../lib/async";
import { fmtDate } from "../lib/format";
import { tileUrl } from "../lib/tiles";

export function StoryList() {
  const { data, error, loading, reload } = useAsync(() => api.stories(), []);
  return (
    <div className="mx-auto max-w-3xl space-y-4 p-4">
      <h1 className="text-xl font-semibold">Récits</h1>
      <p className="text-sm text-slate-400">Des histoires guidées par la carte. Chaque scène indique la provenance de ses données et ses limites.</p>
      {loading && <Loading />}
      {error && <ErrorBox message={error} onRetry={reload} />}
      {data?.length === 0 && <Empty>Aucun récit publié.</Empty>}
      <ul className="space-y-3">
        {data?.map((s) => (
          <li key={s.id} className="card">
            <p className="text-xs text-accent">{s.theme} · {s.duration_min} min · {s.scene_count} scènes {s.is_example && "· exemple"}</p>
            <h2 className="text-lg font-medium"><Link className="hover:underline" to={`/recits/${s.slug}`}>{s.title}</Link></h2>
            <p className="text-sm text-slate-300">{s.synopsis}</p>
          </li>
        ))}
      </ul>
    </div>
  );
}

const reduced = () => typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

export function StoryView() {
  const { slug = "" } = useParams();
  const story = useAsync(() => api.story(slug), [slug]);
  const [active, setActive] = useState(0);
  const refs = useRef<(HTMLElement | null)[]>([]);

  useEffect(() => {
    const io = new IntersectionObserver((entries) => {
      const vis = entries.filter((e) => e.isIntersecting).sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
      if (vis) setActive(Number((vis.target as HTMLElement).dataset.idx));
    }, { threshold: [0.3, 0.6, 0.9], rootMargin: "-20% 0px -30% 0px" });
    refs.current.forEach((r) => r && io.observe(r));
    return () => io.disconnect();
  }, [story.data]);

  if (story.loading) return <Loading />;
  if (story.error || !story.data) return <div className="p-4"><ErrorBox message={story.error ?? "Récit introuvable."} onRetry={story.reload} /></div>;
  const st = story.data;
  const scene = st.scenes[Math.min(active, st.scenes.length - 1)];
  return (
    <div className="flex min-h-full flex-col md:flex-row">
      <div className="order-2 w-full space-y-[60vh] px-4 pb-[40vh] pt-6 md:order-1 md:w-1/3">
        <header className="space-y-2">
          <Link to="/recits" className="text-xs text-accent hover:underline">← Tous les récits</Link>
          <h1 className="text-2xl font-semibold">{st.title}</h1>
          <p className="text-sm text-slate-300">{st.synopsis}</p>
        </header>
        {st.scenes.map((sc, i) => (
          <section key={sc.order} data-idx={i} ref={(el) => { refs.current[i] = el; }} aria-current={i === active ? "step" : undefined}
            className={`card space-y-2 transition-opacity ${i === active ? "opacity-100" : "opacity-60"}`}>
            <p className="text-xs text-slate-400">Scène {sc.order} sur {st.scenes.length}</p>
            <h2 className="text-lg font-medium">{sc.title}</h2>
            <p className="text-sm leading-relaxed">{sc.body}</p>
            {sc.figure && <p className="text-sm font-semibold text-accent">{sc.figure}</p>}
            {sc.annotation && <p className="text-xs italic text-slate-300">{sc.annotation}</p>}
            <p className="text-xs text-slate-400"><strong>Provenance :</strong> {sc.provenance}</p>
            <p className="text-xs text-warn"><strong>Limites :</strong> {sc.limits}</p>
          </section>
        ))}
        <footer className="text-xs text-slate-400">
          <h2 className="mb-1 font-semibold text-slate-300">Sources</h2>
          <ul>{st.sources.map((s) => <li key={s.label}>{s.url ? <a className="underline" href={s.url} target="_blank" rel="noreferrer">{s.label}</a> : s.label}</li>)}</ul>
        </footer>
      </div>
      <div className="order-1 h-[45vh] w-full md:sticky md:top-0 md:order-2 md:h-[calc(100vh-3rem)] md:w-2/3">
        <SceneMap scene={scene} />
      </div>
    </div>
  );
}

function SceneMap({ scene }: { scene: Scene }) {
  const key = scene.layers[0];
  const meta = useAsync(() => (key ? api.layerMetadata(key, true) : Promise.resolve(null)), [key]);
  const dates = useMemo(() => {
    const all = meta.data?.datasets.map((d) => d.date).sort() ?? [];
    return all.filter((d) => (!scene.date_start || d >= scene.date_start) && (!scene.date_end || d <= scene.date_end));
  }, [meta.data, scene.date_start, scene.date_end]);
  const [i, setI] = useState(0);
  useEffect(() => { setI(reduced() ? Math.max(dates.length - 1, 0) : 0); }, [dates.join(",")]); // eslint-disable-line
  useEffect(() => {
    if (dates.length < 2 || reduced()) return;
    const t = setInterval(() => setI((x) => (x + 1) % dates.length), 1400);
    return () => clearInterval(t);
  }, [dates.join(",")]); // eslint-disable-line
  const date = dates[Math.min(i, dates.length - 1)];
  const ds = meta.data?.datasets.find((d) => d.date === date);
  const rasters = date && key ? [{ id: "nv-story", url: tileUrl(key, date, !!ds?.is_demo), opacity: 0.9 }] : [];
  return (
    <div className="relative h-full w-full">
      <MapView center={scene.center} zoom={scene.zoom} rasters={rasters} basemap={true} label={`Carte de la scène : ${scene.title}`} />
      {ds?.is_demo && <div role="alert" className="absolute inset-x-0 top-0 z-10 bg-warn px-3 py-1 text-center text-xs font-semibold text-ink-900">DONNÉES SIMULÉES. Pas une observation NISAR.</div>}
      {!meta.loading && !date && <div className="absolute inset-x-4 bottom-4 z-10"><Empty>Aucune donnée NISAR n'est associée à cette scène pour le moment. Seul le texte et le fond de carte sont affichés.</Empty></div>}
      {ds && <div className="absolute bottom-2 left-2 z-10 flex items-center gap-2 rounded bg-ink-900/90 px-2 py-1 text-xs"><MaturityBadge maturity={ds.maturity} />{fmtDate(ds.date)}</div>}
    </div>
  );
}
