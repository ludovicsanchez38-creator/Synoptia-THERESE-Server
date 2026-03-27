import { useEffect, useRef } from "react";
import ReactMarkdown from "react-markdown";
import { useChatStore } from "../../stores/chatStore";
import Spinner from "../ui/Spinner";
import MissionCard from "./MissionCard";

function formatTime(dateStr: string): string {
  try {
    const d = new Date(dateStr);
    return d.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
  } catch {
    return "";
  }
}

/** Détecte si un message utilisateur a déclenché une mission (préfixe @type). */
function extractMissionType(content: string): string | null {
  const match = content.match(/^@(\w+)\s/);
  return match ? match[1] : null;
}

export default function MessageList() {
  const {
    messages,
    isLoadingMessages,
    isSending,
    currentConversationId,
    activeMissions,
    cancelActiveMission,
  } = useChatStore();
  const bottomRef = useRef<HTMLDivElement>(null);

  // Collecter les missions actives triées par ordre d'insertion
  const missionsList = Object.values(activeMissions);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isSending, missionsList]);

  if (!currentConversationId) {
    return (
      <div className="flex-1 flex items-center justify-center text-[var(--color-muted)]">
        <div className="text-center">
          <p className="text-lg mb-2">Bienvenue sur Thérèse</p>
          <p className="text-sm">
            Sélectionnez ou créez une conversation pour commencer.
          </p>
        </div>
      </div>
    );
  }

  if (isLoadingMessages) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <Spinner size="md" />
      </div>
    );
  }

  /**
   * Construit la liste des éléments à afficher.
   * Les messages normaux sont rendus tels quels.
   * Quand on détecte un message utilisateur de type @mission,
   * on injecte une MissionCard juste après.
   */
  const renderItems: React.ReactNode[] = [];

  for (const msg of messages) {
    const isUser = msg.role === "user";
    const missionType = isUser ? extractMissionType(msg.content) : null;

    // Rendre le message normalement
    renderItems.push(
      <div
        key={msg.id}
        className={`flex ${isUser ? "justify-end" : "justify-start"}`}
      >
        <div
          className={`max-w-[75%] md:max-w-[60%] rounded-2xl px-4 py-3 ${
            isUser
              ? "bg-[var(--color-primary)] text-white rounded-br-md"
              : "bg-slate-800/60 border border-slate-700 text-[var(--color-text)] rounded-bl-md"
          }`}
        >
          {!isUser && (
            <div className="flex items-center gap-2 mb-1">
              <span className="text-xs font-medium text-[var(--color-cyan)]">
                Thérèse
              </span>
              {msg.model && (
                <span className="text-[10px] text-[var(--color-muted)] bg-slate-700/50 px-1.5 py-0.5 rounded">
                  {msg.model}
                </span>
              )}
            </div>
          )}
          {isUser ? (
            <div className="text-sm whitespace-pre-wrap break-words">
              {msg.content}
            </div>
          ) : (
            <div className="prose prose-invert prose-sm max-w-none break-words">
              <ReactMarkdown>{msg.content}</ReactMarkdown>
            </div>
          )}
          <div
            className={`text-[10px] mt-1 ${
              isUser ? "text-white/50 text-right" : "text-[var(--color-muted)]/60"
            }`}
          >
            {formatTime(msg.created_at)}
          </div>
        </div>
      </div>
    );

    // Si c'est un message @mission, chercher la mission correspondante
    if (missionType) {
      // Trouver la mission active qui correspond à ce type
      // (on prend la première qui matche le type, car les missions
      //  sont créées juste après le message utilisateur)
      const mission = missionsList.find(
        (m) => m.missionType === missionType || m.missionType === "conformity"
      );

      if (mission) {
        renderItems.push(
          <MissionCard
            key={`mission-${mission.id}`}
            missionId={mission.id}
            missionType={mission.missionType}
            status={mission.status}
            progress={mission.progress}
            resultContent={mission.resultContent}
            error={mission.error}
            onCancel={cancelActiveMission}
          />
        );
      }
    }
  }

  // Missions orphelines (pas encore associées à un message visible)
  for (const mission of missionsList) {
    const alreadyRendered = renderItems.some(
      (item) =>
        item !== null &&
        typeof item === "object" &&
        "key" in item &&
        item.key === `mission-${mission.id}`
    );
    if (!alreadyRendered) {
      renderItems.push(
        <MissionCard
          key={`mission-${mission.id}`}
          missionId={mission.id}
          missionType={mission.missionType}
          status={mission.status}
          progress={mission.progress}
          resultContent={mission.resultContent}
          error={mission.error}
          onCancel={cancelActiveMission}
        />
      );
    }
  }

  return (
    <div aria-live="polite" className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
      {messages.length === 0 && missionsList.length === 0 && (
        <p className="text-center text-[var(--color-muted)] text-sm py-8">
          Aucun message. Commencez la conversation !
        </p>
      )}

      {renderItems}

      {isSending && (
        <div className="flex justify-start">
          <div className="bg-slate-800/60 border border-slate-700 rounded-2xl rounded-bl-md px-4 py-3">
            <div className="flex items-center gap-2">
              <span className="text-xs font-medium text-[var(--color-cyan)]">
                Thérèse
              </span>
              <Spinner size="sm" />
              <span className="text-xs text-[var(--color-muted)]">
                Réflexion en cours...
              </span>
            </div>
          </div>
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  );
}
