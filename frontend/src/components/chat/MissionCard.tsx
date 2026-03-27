/**
 * Carte de mission agent affichée dans le flux de messages.
 *
 * Affiche le statut en temps réel (en cours, terminé, erreur)
 * avec barre de progression et résultat en Markdown.
 */

import ReactMarkdown from "react-markdown";
import Spinner from "../ui/Spinner";
import { cancelMission } from "../../services/api/missionService";

/** Labels et icônes par type de mission. */
const MISSION_META: Record<string, { label: string; icon?: string }> = {
  conformity: { label: "Agent Conformité", icon: "" },
  research: { label: "Agent Recherche", icon: "" },
  document: { label: "Agent Rédaction", icon: "" },
  crm: { label: "Agent CRM", icon: "" },
};

function getMeta(missionType: string) {
  return MISSION_META[missionType] || { label: "Agent", icon: "" };
}

interface MissionCardProps {
  missionId: string;
  missionType: string;
  status: string;
  progress: number;
  resultContent: string | null;
  error: string | null;
  onCancel?: (missionId: string) => void;
}

export default function MissionCard({
  missionId,
  missionType,
  status,
  progress,
  resultContent,
  error,
  onCancel,
}: MissionCardProps) {
  const meta = getMeta(missionType);
  const isRunning = status === "pending" || status === "running";
  const isCompleted = status === "completed";
  const isFailed = status === "failed" || status === "cancelled";

  const handleCancel = async () => {
    try {
      await cancelMission(missionId);
      onCancel?.(missionId);
    } catch {
      // Géré silencieusement, le polling mettra à jour
    }
  };

  return (
    <div className="flex justify-start">
      <div className="max-w-[75%] md:max-w-[60%] rounded-2xl rounded-bl-md px-4 py-3 bg-slate-800/60 border border-slate-700">
        {/* En-tête : icône agent + nom + badge statut */}
        <div className="flex items-center gap-2 mb-2">
          <span className="text-base" role="img" aria-label={meta.label}>
            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--color-cyan)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10"/><path d="m9 12 2 2 4-4"/></svg>
          </span>
          <span className="text-xs font-medium text-[var(--color-cyan)]">
            {meta.label}
          </span>

          {/* Badge de statut */}
          {isRunning && (
            <span className="inline-flex items-center gap-1 text-[10px] bg-amber-500/20 text-amber-400 px-2 py-0.5 rounded-full">
              <Spinner size="sm" className="!h-3 !w-3 !border-1" />
              En cours
            </span>
          )}
          {isCompleted && (
            <span className="inline-flex items-center gap-1 text-[10px] bg-emerald-500/20 text-emerald-400 px-2 py-0.5 rounded-full">
              <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="20 6 9 17 4 12" />
              </svg>
              Terminé
            </span>
          )}
          {isFailed && (
            <span className="inline-flex items-center gap-1 text-[10px] bg-red-500/20 text-red-400 px-2 py-0.5 rounded-full">
              <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
              </svg>
              {status === "cancelled" ? "Annulé" : "Erreur"}
            </span>
          )}
        </div>

        {/* Barre de progression (missions en cours) */}
        {isRunning && (
          <div className="mb-2">
            <div className="w-full h-1.5 bg-slate-700 rounded-full overflow-hidden">
              <div
                className="h-full bg-[var(--color-cyan)] rounded-full transition-all duration-500"
                style={{ width: `${Math.max(progress, 5)}%` }}
              />
            </div>
            <p className="text-[10px] text-[var(--color-muted)] mt-1">
              Analyse en cours... {progress > 0 ? `${progress}%` : ""}
            </p>
          </div>
        )}

        {/* Résultat (mission terminée) */}
        {isCompleted && resultContent && (
          <div className="prose prose-invert prose-sm max-w-none break-words">
            <ReactMarkdown>{resultContent}</ReactMarkdown>
          </div>
        )}

        {/* Erreur */}
        {isFailed && error && (
          <p className="text-sm text-red-400 mt-1">{error}</p>
        )}

        {/* Bouton annuler (mission en cours) */}
        {isRunning && (
          <button
            type="button"
            onClick={handleCancel}
            className="mt-2 px-3 py-1 text-xs text-[var(--color-muted)] hover:text-red-400 bg-slate-700/50 hover:bg-red-500/10 border border-slate-600 hover:border-red-500/30 rounded-lg transition-colors"
          >
            Annuler
          </button>
        )}
      </div>
    </div>
  );
}
