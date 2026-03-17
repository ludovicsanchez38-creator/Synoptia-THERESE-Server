import { useEffect } from "react";
import { useChatStore } from "../../stores/chatStore";
import Spinner from "../ui/Spinner";

export default function ConversationList() {
  const {
    conversations,
    currentConversationId,
    isLoadingConversations,
    loadConversations,
    selectConversation,
    newConversation,
    removeConversation,
  } = useChatStore();

  useEffect(() => {
    loadConversations();
  }, [loadConversations]);

  const handleDelete = (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    if (window.confirm("Supprimer cette conversation ?")) {
      removeConversation(id);
    }
  };

  return (
    <div className="flex flex-col h-full">
      <div className="p-3">
        <button
          onClick={() => newConversation()}
          className="w-full py-2 text-sm bg-[var(--color-primary)]/10 border border-[var(--color-primary)]/30 rounded-lg text-[var(--color-primary)] hover:bg-[var(--color-primary)]/20 transition-colors"
        >
          + Nouvelle conversation
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-2 pb-2">
        {isLoadingConversations ? (
          <div className="flex justify-center py-8">
            <Spinner size="sm" />
          </div>
        ) : conversations.length === 0 ? (
          <p className="text-sm text-[var(--color-muted)] text-center py-4">
            Aucune conversation
          </p>
        ) : (
          <ul className="space-y-1">
            {conversations.map((conv) => (
              <li key={conv.id}>
                <button
                  onClick={() => selectConversation(conv.id)}
                  className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-colors group flex items-center justify-between gap-2 ${
                    conv.id === currentConversationId
                      ? "bg-[var(--color-primary)]/15 text-[var(--color-text)]"
                      : "text-[var(--color-muted)] hover:bg-slate-800/50 hover:text-[var(--color-text)]"
                  }`}
                >
                  <span className="truncate flex-1">{conv.title}</span>
                  <span className="flex items-center gap-1 shrink-0">
                    <span className="text-xs opacity-60">
                      {conv.message_count}
                    </span>
                    <button
                      onClick={(e) => handleDelete(e, conv.id)}
                      className="opacity-0 group-hover:opacity-60 hover:!opacity-100 text-red-400 hover:text-red-300 transition-opacity ml-1"
                      title="Supprimer"
                    >
                      <svg
                        xmlns="http://www.w3.org/2000/svg"
                        width="14"
                        height="14"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      >
                        <path d="M3 6h18" />
                        <path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6" />
                        <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2" />
                      </svg>
                    </button>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
