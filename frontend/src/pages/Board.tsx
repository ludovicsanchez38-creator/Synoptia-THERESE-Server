import { useEffect, useState, useCallback, useRef } from "react";
import ReactMarkdown from "react-markdown";
import NavBar from "../components/NavBar";
import { Button, Spinner } from "../components/ui";
import {
  fetchAdvisors,
  startDeliberation,
  fetchDecisions,
  fetchDecision,
  deleteDecision,
  type AdvisorInfo,
  type BoardSSEChunk,
  type BoardDecisionSummary,
  type BoardDecisionFull,
  type BoardSynthesis,
} from "../services/api/boardService";
import { useToastStore } from "../stores/toastStore";

// SVG icons pour les conseillers du Board
const ADVISOR_SVGS: Record<string, React.ReactNode> = {
  analyst: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#22D3EE" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="18" y1="20" x2="18" y2="10" /><line x1="12" y1="20" x2="12" y2="4" /><line x1="6" y1="20" x2="6" y2="14" />
    </svg>
  ),
  strategist: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#A855F7" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" /><circle cx="12" cy="12" r="6" /><circle cx="12" cy="12" r="2" />
    </svg>
  ),
  devil: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#EF4444" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 2L2 7l10 5 10-5-10-5z" /><path d="M2 17l10 5 10-5" /><path d="M2 12l10 5 10-5" />
    </svg>
  ),
  pragmatic: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#F59E0B" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14.7 6.3a1 1 0 000 1.4l1.6 1.6a1 1 0 001.4 0l3.77-3.77a6 6 0 01-7.94 7.94l-6.91 6.91a2.12 2.12 0 01-3-3l6.91-6.91a6 6 0 017.94-7.94l-3.76 3.76z" />
    </svg>
  ),
  visionary: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#E11D8D" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 00-2.91-.09z" />
      <path d="M12 15l-3-3a22 22 0 012-3.95A12.88 12.88 0 0122 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 01-4 2z" />
    </svg>
  ),
};

type Tab = "deliberation" | "history";

interface AdvisorState {
  role: string;
  name: string;
  emoji: string;
  color: string;
  content: string;
  status: "idle" | "loading" | "done";
  provider?: string;
}

export default function BoardPage() {
  const [tab, setTab] = useState<Tab>("deliberation");
  const [advisors, setAdvisors] = useState<AdvisorInfo[]>([]);
  const [question, setQuestion] = useState("");
  const [context, setContext] = useState("");
  const [mode, setMode] = useState<"cloud" | "sovereign">("cloud");
  const [deliberating, setDeliberating] = useState(false);
  const [advisorStates, setAdvisorStates] = useState<Map<string, AdvisorState>>(new Map());
  const [synthesis, setSynthesis] = useState<BoardSynthesis | null>(null);
  const synthesisRawRef = useRef("");
  const [synthesisLoading, setSynthesisLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Historique
  const [decisions, setDecisions] = useState<BoardDecisionSummary[]>([]);
  const [selectedDecision, setSelectedDecision] = useState<BoardDecisionFull | null>(null);
  const [historyLoading, setHistoryLoading] = useState(false);

  const abortRef = useRef<(() => void) | null>(null);
  const synthesisRef = useRef<HTMLDivElement>(null);

  // Charger les advisors au mount
  useEffect(() => {
    document.title = "Board - Therese";
    fetchAdvisors()
      .then(setAdvisors)
      .catch((err) => setError(err.message));
  }, []);

  // Initialiser les states des advisors
  useEffect(() => {
    if (advisors.length > 0 && advisorStates.size === 0) {
      const map = new Map<string, AdvisorState>();
      for (const a of advisors) {
        map.set(a.role, {
          role: a.role,
          name: a.name,
          emoji: a.emoji,
          color: a.color,
          content: "",
          status: "idle",
        });
      }
      setAdvisorStates(map);
    }
  }, [advisors, advisorStates.size]);

  // Charger historique quand on change d'onglet
  useEffect(() => {
    if (tab === "history") {
      loadHistory();
    }
  }, [tab]);

  const loadHistory = async () => {
    try {
      setHistoryLoading(true);
      const data = await fetchDecisions();
      setDecisions(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erreur chargement historique");
    } finally {
      setHistoryLoading(false);
    }
  };

  const handleDeliberate = useCallback(async () => {
    if (!question.trim() || deliberating) return;

    setDeliberating(true);
    setError(null);
    setSynthesis(null);
    synthesisRawRef.current = "";
    setSynthesisLoading(false);

    // Reset advisor states
    setAdvisorStates((prev) => {
      const newMap = new Map(prev);
      for (const [key, val] of newMap) {
        newMap.set(key, { ...val, content: "", status: "idle", provider: undefined });
      }
      return newMap;
    });

    try {
      const { stream, abort } = await startDeliberation(
        question.trim(),
        context.trim() || undefined,
        mode,
      );
      abortRef.current = abort;

      const reader = stream.getReader();
      let reading = true;

      while (reading) {
        const { done, value } = await reader.read();
        if (done) {
          reading = false;
          break;
        }

        const chunk = value as BoardSSEChunk;

        switch (chunk.type) {
          case "advisor_start":
            if (chunk.role) {
              setAdvisorStates((prev) => {
                const newMap = new Map(prev);
                const existing = newMap.get(chunk.role!);
                if (existing) {
                  newMap.set(chunk.role!, {
                    ...existing,
                    status: "loading",
                    content: "",
                    provider: chunk.provider,
                  });
                }
                return newMap;
              });
            }
            break;

          case "advisor_chunk":
            if (chunk.role) {
              setAdvisorStates((prev) => {
                const newMap = new Map(prev);
                const existing = newMap.get(chunk.role!);
                if (existing) {
                  newMap.set(chunk.role!, {
                    ...existing,
                    content: existing.content + chunk.content,
                  });
                }
                return newMap;
              });
            }
            break;

          case "advisor_done":
            if (chunk.role) {
              setAdvisorStates((prev) => {
                const newMap = new Map(prev);
                const existing = newMap.get(chunk.role!);
                if (existing) {
                  newMap.set(chunk.role!, { ...existing, status: "done" });
                }
                return newMap;
              });
            }
            break;

          case "synthesis_start":
            setSynthesisLoading(true);
            break;

          case "synthesis_chunk": {
            synthesisRawRef.current += chunk.content;
            // Tenter de parser le JSON de synthese au fur et a mesure
            try {
              const parsed = JSON.parse(synthesisRawRef.current) as BoardSynthesis;
              setSynthesis(parsed);
              setSynthesisLoading(false);
            } catch {
              // pas encore un JSON complet
            }
            break;
          }

          case "done":
            setSynthesisLoading(false);
            break;

          case "error":
            setError(chunk.content);
            break;
        }
      }
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        setError(err instanceof Error ? err.message : "Erreur de deliberation");
      }
    } finally {
      setDeliberating(false);
      abortRef.current = null;
    }
  }, [question, context, mode, deliberating]);

  const handleCancel = () => {
    if (abortRef.current) {
      abortRef.current();
      abortRef.current = null;
      setDeliberating(false);
    }
  };

  const handleDeleteDecision = async (id: string) => {
    try {
      await deleteDecision(id);
      setDecisions((prev) => prev.filter((d) => d.id !== id));
      if (selectedDecision?.id === id) {
        setSelectedDecision(null);
      }
      useToastStore.getState().addToast("success", "Decision supprimee");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erreur de suppression");
    }
  };

  const handleViewDecision = async (id: string) => {
    try {
      const full = await fetchDecision(id);
      setSelectedDecision(full);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erreur chargement decision");
    }
  };

  const confidenceColors: Record<string, string> = {
    high: "text-emerald-400",
    medium: "text-yellow-400",
    low: "text-red-400",
  };

  const confidenceLabels: Record<string, string> = {
    high: "Haute",
    medium: "Moyenne",
    low: "Basse",
  };

  // Scroll vers la synthese quand elle apparait
  useEffect(() => {
    if (synthesis && synthesisRef.current) {
      synthesisRef.current.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [synthesis]);

  return (
    <div className="min-h-screen flex flex-col" data-testid="board-page">
      <NavBar />

      <main id="main-content" className="flex-1 p-4 md:p-6 max-w-6xl mx-auto w-full">
        {/* Titre + onglets */}
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-xl font-bold text-[var(--color-text)]">
            Board de Decision
          </h2>
          <div className="flex gap-1">
            <button
              onClick={() => setTab("deliberation")}
              className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
                tab === "deliberation"
                  ? "bg-slate-800 text-[var(--color-cyan)]"
                  : "text-[var(--color-muted)] hover:text-[var(--color-text)] hover:bg-slate-800/50"
              }`}
            >
              Deliberation
            </button>
            <button
              onClick={() => setTab("history")}
              className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
                tab === "history"
                  ? "bg-slate-800 text-[var(--color-cyan)]"
                  : "text-[var(--color-muted)] hover:text-[var(--color-text)] hover:bg-slate-800/50"
              }`}
            >
              Historique
            </button>
          </div>
        </div>

        {/* Erreur */}
        {error && (
          <div role="alert" className="mb-4 p-3 bg-red-900/30 border border-red-700 rounded-lg text-red-400 text-sm">
            {error}
            <button onClick={() => setError(null)} className="ml-2 underline">
              Fermer
            </button>
          </div>
        )}

        {/* Tab: Deliberation */}
        {tab === "deliberation" && (
          <>
            {/* Formulaire question */}
            <div className="mb-6 p-4 bg-slate-800/30 border border-slate-700 rounded-xl space-y-3" data-testid="board-panel">
              <div>
                <label className="block text-sm text-[var(--color-muted)] mb-1">
                  Question strategique *
                </label>
                <textarea
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-800 border border-slate-600 rounded-lg text-[var(--color-text)] text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-cyan)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--color-bg)] resize-none"
                  rows={3}
                  placeholder="Posez votre question au board (min. 10 caracteres)..."
                  disabled={deliberating}
                />
              </div>
              <div>
                <label className="block text-sm text-[var(--color-muted)] mb-1">
                  Contexte (optionnel)
                </label>
                <textarea
                  value={context}
                  onChange={(e) => setContext(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-800 border border-slate-600 rounded-lg text-[var(--color-text)] text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-cyan)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--color-bg)] resize-none"
                  rows={2}
                  placeholder="Ajoutez du contexte pour des avis plus pertinents..."
                  disabled={deliberating}
                />
              </div>
              <div className="flex items-center gap-4">
                <div className="flex items-center gap-2">
                  <label className="text-sm text-[var(--color-muted)]">Mode :</label>
                  <select
                    value={mode}
                    onChange={(e) => setMode(e.target.value as "cloud" | "sovereign")}
                    className="px-2 py-1 bg-slate-800 border border-slate-600 rounded text-sm text-[var(--color-text)] focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-cyan)]"
                    disabled={deliberating}
                  >
                    <option value="cloud">Cloud (multi-LLM)</option>
                    <option value="sovereign">Souverain (Ollama)</option>
                  </select>
                </div>
                <div className="flex-1" />
                {deliberating ? (
                  <Button variant="danger" onClick={handleCancel}>
                    Annuler
                  </Button>
                ) : (
                  <Button
                    onClick={handleDeliberate}
                    disabled={question.trim().length < 10}
                    className="bg-[var(--color-cyan)] text-[var(--color-bg)] hover:bg-[var(--color-cyan)]/80"
                    data-testid="board-submit-btn"
                  >
                    Deliberer
                  </Button>
                )}
              </div>
            </div>

            {/* Grille des advisors */}
            {advisorStates.size > 0 && (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
                {Array.from(advisorStates.values()).map((advisor) => (
                  <AdvisorCard key={advisor.role} advisor={advisor} />
                ))}
              </div>
            )}

            {/* Synthese */}
            {(synthesisLoading || synthesis) && (
              <div ref={synthesisRef} data-testid="board-result">
                <SynthesisPanel
                  synthesis={synthesis}
                  loading={synthesisLoading}
                  confidenceColors={confidenceColors}
                  confidenceLabels={confidenceLabels}
                />
              </div>
            )}
          </>
        )}

        {/* Tab: Historique */}
        {tab === "history" && (
          <HistoryTab
            decisions={decisions}
            loading={historyLoading}
            selectedDecision={selectedDecision}
            onView={handleViewDecision}
            onDelete={handleDeleteDecision}
            onClose={() => setSelectedDecision(null)}
            confidenceColors={confidenceColors}
            confidenceLabels={confidenceLabels}
          />
        )}
      </main>
    </div>
  );
}

/* ============================================================
   Sub-components
   ============================================================ */

function AdvisorCard({ advisor }: { advisor: AdvisorState }) {
  return (
    <div
      className="p-4 bg-slate-800/20 border border-slate-700 rounded-xl flex flex-col min-h-[200px]"
      style={{ borderLeftColor: advisor.color, borderLeftWidth: "3px" }}
    >
      {/* Header */}
      <div className="flex items-center gap-2 mb-3">
        {ADVISOR_SVGS[advisor.role] || advisor.emoji}
        <span className="text-sm font-semibold text-[var(--color-text)]">
          {advisor.name}
        </span>
        {advisor.provider && (
          <span className="text-xs text-[var(--color-muted)] bg-slate-700 px-1.5 py-0.5 rounded ml-auto">
            {advisor.provider}
          </span>
        )}
      </div>

      {/* Contenu */}
      <div className="flex-1 overflow-y-auto">
        {advisor.status === "idle" && (
          <p className="text-xs text-[var(--color-muted)] italic">
            En attente de deliberation...
          </p>
        )}
        {advisor.status === "loading" && advisor.content === "" && (
          <div className="flex items-center gap-2">
            <Spinner size="sm" />
            <span className="text-xs text-[var(--color-muted)]">Reflexion en cours...</span>
          </div>
        )}
        {advisor.content && (
          <div className="prose prose-sm prose-invert max-w-none text-[var(--color-text)] text-sm leading-relaxed">
            <ReactMarkdown>{advisor.content}</ReactMarkdown>
          </div>
        )}
        {advisor.status === "loading" && advisor.content !== "" && (
          <div className="mt-2">
            <Spinner size="sm" />
          </div>
        )}
      </div>

      {/* Statut */}
      {advisor.status === "done" && (
        <div className="mt-2 pt-2 border-t border-slate-700">
          <span className="text-xs text-emerald-400">Avis rendu</span>
        </div>
      )}
    </div>
  );
}

function SynthesisPanel({
  synthesis,
  loading,
  confidenceColors,
  confidenceLabels,
}: {
  synthesis: BoardSynthesis | null;
  loading: boolean;
  confidenceColors: Record<string, string>;
  confidenceLabels: Record<string, string>;
}) {
  return (
    <div className="p-5 bg-slate-800/30 border border-slate-700 rounded-xl">
      <div className="flex items-center gap-2 mb-4">
        <span className="text-lg">&#x2696;&#xFE0F;</span>
        <h3 className="text-lg font-bold text-[var(--color-text)]">Synthese du Board</h3>
        {loading && <Spinner size="sm" className="ml-2" />}
      </div>

      {loading && !synthesis && (
        <div className="flex items-center gap-2 py-4">
          <Spinner size="sm" />
          <span className="text-sm text-[var(--color-muted)]">Elaboration de la synthese...</span>
        </div>
      )}

      {synthesis && (
        <div className="space-y-4">
          {/* Recommandation */}
          <div className="p-3 bg-slate-800/50 border border-[var(--color-cyan)]/30 rounded-lg">
            <h4 className="text-sm font-semibold text-[var(--color-cyan)] mb-1">Recommandation</h4>
            <p className="text-sm text-[var(--color-text)]">{synthesis.recommendation}</p>
            <div className="mt-2">
              <span className="text-xs text-[var(--color-muted)]">Confiance : </span>
              <span className={`text-xs font-medium ${confidenceColors[synthesis.confidence] || "text-[var(--color-muted)]"}`}>
                {confidenceLabels[synthesis.confidence] || synthesis.confidence}
              </span>
            </div>
          </div>

          {/* Consensus */}
          {synthesis.consensus_points.length > 0 && (
            <div>
              <h4 className="text-sm font-semibold text-emerald-400 mb-2">Points de consensus</h4>
              <ul className="space-y-1">
                {synthesis.consensus_points.map((point, i) => (
                  <li key={i} className="text-sm text-[var(--color-text)] flex items-start gap-2">
                    <span className="text-emerald-400 mt-0.5 shrink-0">&#x2713;</span>
                    {point}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Divergences */}
          {synthesis.divergence_points.length > 0 && (
            <div>
              <h4 className="text-sm font-semibold text-yellow-400 mb-2">Points de divergence</h4>
              <ul className="space-y-1">
                {synthesis.divergence_points.map((point, i) => (
                  <li key={i} className="text-sm text-[var(--color-text)] flex items-start gap-2">
                    <span className="text-yellow-400 mt-0.5 shrink-0">&#x26A0;</span>
                    {point}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Prochaines etapes */}
          {synthesis.next_steps.length > 0 && (
            <div>
              <h4 className="text-sm font-semibold text-[var(--color-muted)] mb-2">Prochaines etapes</h4>
              <ol className="space-y-1 list-decimal list-inside">
                {synthesis.next_steps.map((step, i) => (
                  <li key={i} className="text-sm text-[var(--color-text)]">
                    {step}
                  </li>
                ))}
              </ol>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function HistoryTab({
  decisions,
  loading,
  selectedDecision,
  onView,
  onDelete,
  onClose,
  confidenceColors,
  confidenceLabels,
}: {
  decisions: BoardDecisionSummary[];
  loading: boolean;
  selectedDecision: BoardDecisionFull | null;
  onView: (id: string) => void;
  onDelete: (id: string) => void;
  onClose: () => void;
  confidenceColors: Record<string, string>;
  confidenceLabels: Record<string, string>;
}) {
  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Spinner size="md" />
        <span className="ml-3 text-[var(--color-muted)]">Chargement...</span>
      </div>
    );
  }

  // Detail d'une decision
  if (selectedDecision) {
    return (
      <div className="space-y-4">
        <div className="flex items-center gap-2 mb-4">
          <button
            onClick={onClose}
            className="text-sm text-[var(--color-muted)] hover:text-[var(--color-text)] transition-colors"
          >
            &#x2190; Retour
          </button>
          <span className="text-xs text-[var(--color-muted)]">
            {new Date(selectedDecision.created_at).toLocaleDateString("fr-FR", {
              day: "numeric",
              month: "long",
              year: "numeric",
              hour: "2-digit",
              minute: "2-digit",
            })}
          </span>
        </div>

        <div className="p-4 bg-slate-800/30 border border-slate-700 rounded-xl">
          <h3 className="text-base font-semibold text-[var(--color-text)] mb-2">
            {selectedDecision.question}
          </h3>
          {selectedDecision.context && (
            <p className="text-sm text-[var(--color-muted)] mb-4">{selectedDecision.context}</p>
          )}
        </div>

        {/* Avis des conseillers */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {selectedDecision.opinions.map((opinion) => (
            <div
              key={opinion.role}
              className="p-4 bg-slate-800/20 border border-slate-700 rounded-xl"
            >
              <div className="flex items-center gap-2 mb-2">
                {ADVISOR_SVGS[opinion.role] || opinion.role}
                <span className="text-sm font-semibold text-[var(--color-text)]">
                  {opinion.name}
                </span>
              </div>
              <div className="prose prose-sm prose-invert max-w-none text-[var(--color-text)] text-sm">
                <ReactMarkdown>{opinion.content}</ReactMarkdown>
              </div>
            </div>
          ))}
        </div>

        {/* Synthese */}
        <SynthesisPanel
          synthesis={selectedDecision.synthesis}
          loading={false}
          confidenceColors={confidenceColors}
          confidenceLabels={confidenceLabels}
        />
      </div>
    );
  }

  // Liste des decisions
  if (decisions.length === 0) {
    return (
      <div className="text-center py-12 text-[var(--color-muted)]">
        Aucune deliberation enregistree
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {decisions.map((d) => (
        <div
          key={d.id}
          className="flex items-start gap-3 p-4 bg-slate-800/20 border border-slate-700 rounded-xl hover:bg-slate-800/30 transition-colors"
        >
          <div className="flex-1 min-w-0">
            <button
              onClick={() => onView(d.id)}
              className="text-sm font-medium text-[var(--color-text)] hover:text-[var(--color-cyan)] transition-colors text-left"
            >
              {d.question}
            </button>
            <div className="flex items-center gap-3 mt-1">
              <span className="text-xs text-[var(--color-muted)]">
                {new Date(d.created_at).toLocaleDateString("fr-FR")}
              </span>
              <span className={`text-xs font-medium ${confidenceColors[d.confidence] || "text-[var(--color-muted)]"}`}>
                Confiance : {confidenceLabels[d.confidence] || d.confidence}
              </span>
              <span className="text-xs text-[var(--color-muted)] bg-slate-700 px-1.5 py-0.5 rounded">
                {d.mode}
              </span>
            </div>
            <p className="text-xs text-[var(--color-muted)] mt-1 truncate">
              {d.recommendation}
            </p>
          </div>
          <button
            onClick={() => onDelete(d.id)}
            className="text-[var(--color-muted)] hover:text-red-400 transition-colors shrink-0"
            title="Supprimer"
            aria-label="Supprimer la decision"
          >
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <polyline points="3 6 5 6 21 6" />
              <path d="M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6" />
              <path d="M10 11v6" />
              <path d="M14 11v6" />
            </svg>
          </button>
        </div>
      ))}
    </div>
  );
}
