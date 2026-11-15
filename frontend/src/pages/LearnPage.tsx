import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import type { AttemptResult, LevelDetail } from "../api/types";
import { Empty, ErrorBox, Loading } from "../components/ui";
import { useAsync } from "../lib/async";
import { SIMULATORS } from "../sim/Simulators";

export function LearnHome() {
  const levels = useAsync(() => api.levels(), []);
  const progress = useAsync(() => api.progress(), []);
  return (
    <div className="mx-auto max-w-4xl space-y-6 p-4">
      <header className="space-y-1">
        <h1 className="text-xl font-semibold">Apprendre le radar</h1>
        <p className="text-sm text-slate-400">Cinq niveaux, des simulateurs conceptuels et un quiz par niveau. Le score et les récompenses sont calculés par le serveur.</p>
      </header>
      {progress.data && (
        <div className="card flex flex-wrap items-center gap-4 text-sm" aria-label="Progression">
          <span><strong>{progress.data.xp}</strong> XP</span>
          <span>{progress.data.completed_levels.length} niveau(x) sur {progress.data.total_levels}</span>
          <span className="flex flex-wrap gap-1">{progress.data.badges.map((b) => <span key={b.key} title={b.description} className="rounded bg-ink-600 px-2 py-0.5 text-xs text-accent">{b.label}</span>)}</span>
          {progress.data.certificate_eligible && <Link className="btn btn-primary" to="/apprendre/certificat">Obtenir mon certificat</Link>}
        </div>
      )}
      {levels.loading && <Loading />}
      {levels.error && <ErrorBox message={levels.error} onRetry={levels.reload} />}
      <ol className="grid gap-3 md:grid-cols-2">
        {levels.data?.map((l) => (
          <li key={l.id} className={`card ${l.unlocked ? "" : "opacity-60"}`}>
            <p className="text-xs text-accent">Niveau {l.number} · {l.xp} XP {l.completed && "· terminé"}</p>
            <h2 className="font-medium">{l.title}</h2>
            <p className="text-sm text-slate-300">{l.summary}</p>
            {l.unlocked
              ? <Link className="btn mt-2" to={`/apprendre/niveau/${l.id}`}>{l.completed ? "Revoir" : "Commencer"}</Link>
              : <p className="mt-2 text-xs text-slate-400">Terminez le niveau précédent pour le débloquer.</p>}
          </li>
        ))}
      </ol>
      <Link className="text-sm text-accent underline" to="/apprendre/glossaire">Glossaire des termes</Link>
    </div>
  );
}

export function LevelPage() {
  const { id = "" } = useParams();
  const level = useAsync(() => api.level(Number(id)), [id]);
  if (level.loading) return <Loading />;
  if (level.error || !level.data) return <div className="p-4"><ErrorBox message={level.error ?? "Niveau introuvable."} onRetry={level.reload} /></div>;
  return <LevelBody level={level.data} />;
}

function LevelBody({ level }: { level: LevelDetail }) {
  const Sim = SIMULATORS[level.simulator];
  const [answers, setAnswers] = useState<Record<number, number>>({});
  const [result, setResult] = useState<AttemptResult | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const all = level.quiz.questions.every((q) => answers[q.id] != null);

  async function submit() {
    setBusy(true); setErr(null);
    try { setResult(await api.attempt(level.quiz.id, answers)); } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  }
  return (
    <div className="mx-auto max-w-3xl space-y-6 p-4">
      <Link to="/apprendre" className="text-xs text-accent hover:underline">← Niveaux</Link>
      <h1 className="text-xl font-semibold">Niveau {level.number} : {level.title}</h1>
      {level.lessons.map((l) => (
        <article key={l.order} className="card space-y-1"><h2 className="font-medium">{l.title}</h2><p className="text-sm leading-relaxed">{l.content}</p></article>
      ))}
      {Sim && <Sim />}
      <section className="space-y-4" aria-labelledby="quiz-h">
        <h2 id="quiz-h" className="text-lg font-semibold">Quiz</h2>
        <p className="text-xs text-slate-400">Il faut au moins {Math.round(level.quiz.pass_ratio * 100)} % de bonnes réponses pour valider le niveau.</p>
        {level.quiz.questions.map((q) => {
          const r = result?.results.find((x) => x.question_id === q.id);
          return (
            <fieldset key={q.id} className="card space-y-1" disabled={!!result}>
              <legend className="px-1 text-sm font-medium">{q.order}. {q.text}</legend>
              {q.options.map((o) => (
                <label key={o.id} className={`flex items-center gap-2 text-sm ${r && o.id === r.correct_option_id ? "text-green-300" : r && o.id === r.chosen && !r.is_correct ? "text-red-300" : ""}`}>
                  <input type="radio" name={`q${q.id}`} checked={answers[q.id] === o.id} onChange={() => setAnswers((a) => ({ ...a, [q.id]: o.id }))} />{o.text}
                </label>
              ))}
              {r && <p className="text-xs text-slate-300" role="status">{r.is_correct ? "Bonne réponse. " : "Réponse incorrecte. "}{r.explanation}</p>}
            </fieldset>
          );
        })}
        {err && <ErrorBox message={err} />}
        {!result && <button className="btn btn-primary" disabled={!all || busy} onClick={submit}>{busy ? "Envoi…" : "Valider mes réponses"}</button>}
        {result && (
          <div className="card space-y-2" role="status">
            <p className="font-medium">{result.correct} bonne(s) réponse(s) sur {result.total} ({Math.round(result.score * 100)} %). {result.passed ? "Niveau validé." : "Niveau non validé, vous pouvez réessayer."}</p>
            {result.xp_awarded > 0 && <p className="text-sm text-accent">+{result.xp_awarded} XP</p>}
            {result.new_badge && <p className="text-sm text-accent">Nouveau badge obtenu.</p>}
            {!result.passed && <button className="btn" onClick={() => { setResult(null); setAnswers({}); }}>Réessayer</button>}
            {result.passed && <Link className="btn btn-primary" to="/apprendre">Retour aux niveaux</Link>}
          </div>
        )}
      </section>
    </div>
  );
}

export function Glossary() {
  const [q, setQ] = useState("");
  const g = useAsync(() => api.glossary(q.trim() || undefined), [q]);
  return (
    <div className="mx-auto max-w-3xl space-y-4 p-4">
      <Link to="/apprendre" className="text-xs text-accent hover:underline">← Niveaux</Link>
      <h1 className="text-xl font-semibold">Glossaire</h1>
      <label className="block text-sm">Rechercher un terme<input className="field ml-2" value={q} onChange={(e) => setQ(e.target.value)} /></label>
      {g.loading && <Loading />}
      {g.error && <ErrorBox message={g.error} onRetry={g.reload} />}
      {g.data?.length === 0 && <Empty>Aucun terme ne correspond à « {q} ».</Empty>}
      <dl className="space-y-3">
        {g.data?.map((t) => (<div key={t.term} className="card"><dt className="font-medium">{t.term}</dt><dd className="text-sm text-slate-300">{t.definition}{t.example && <span className="block text-xs text-slate-400">Exemple : {t.example}</span>}</dd></div>))}
      </dl>
    </div>
  );
}

export function CertificatePage() {
  const progress = useAsync(() => api.progress(), []);
  const [name, setName] = useState("");
  const [cert, setCert] = useState<{ code: string } | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const code = cert?.code ?? progress.data?.certificate_code ?? null;
  async function issue(e: React.FormEvent) {
    e.preventDefault(); setErr(null);
    try { setCert(await api.certificate(name)); } catch (x) { setErr((x as Error).message); }
  }
  return (
    <div className="mx-auto max-w-xl space-y-4 p-4">
      <Link to="/apprendre" className="text-xs text-accent hover:underline">← Niveaux</Link>
      <h1 className="text-xl font-semibold">Certificat</h1>
      {progress.loading && <Loading />}
      {progress.error && <ErrorBox message={progress.error} onRetry={progress.reload} />}
      {progress.data && !progress.data.certificate_eligible && !code && <Empty>Le certificat est délivré après la validation des cinq niveaux ({progress.data.completed_levels.length} sur {progress.data.total_levels} pour l'instant).</Empty>}
      {progress.data?.certificate_eligible && !code && (
        <form onSubmit={issue} className="card space-y-2">
          <label className="block text-sm">Nom à inscrire<input className="field ml-2" value={name} onChange={(e) => setName(e.target.value)} minLength={2} maxLength={80} required /></label>
          <button className="btn btn-primary" type="submit">Délivrer le certificat</button>
        </form>
      )}
      {err && <ErrorBox message={err} />}
      {code && (
        <div className="card space-y-2" role="status">
          <p>Code du certificat : <strong>{code}</strong></p>
          <a className="btn btn-primary" href={`/api/v1/learning/certificate/${code}/pdf`} target="_blank" rel="noreferrer">Télécharger le PDF</a>
          <p className="text-xs text-slate-400">Ce certificat atteste d'avoir terminé le parcours pédagogique de NISAR Vision. Ce n'est pas une certification officielle de la NASA ni d'aucun organisme.</p>
        </div>
      )}
    </div>
  );
}
