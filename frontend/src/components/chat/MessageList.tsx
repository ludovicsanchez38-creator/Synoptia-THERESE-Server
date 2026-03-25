import { useEffect, useRef } from "react";
import ReactMarkdown from "react-markdown";
import { useChatStore } from "../../stores/chatStore";
import Spinner from "../ui/Spinner";

function formatTime(dateStr: string): string {
  try {
    const d = new Date(dateStr);
    return d.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
  } catch {
    return "";
  }
}

export default function MessageList() {
  const { messages, isLoadingMessages, isSending, currentConversationId } =
    useChatStore();
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isSending]);

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

  return (
    <div aria-live="polite" className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
      {messages.length === 0 && (
        <p className="text-center text-[var(--color-muted)] text-sm py-8">
          Aucun message. Commencez la conversation !
        </p>
      )}

      {messages.map((msg) => {
        const isUser = msg.role === "user";
        return (
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
      })}

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
