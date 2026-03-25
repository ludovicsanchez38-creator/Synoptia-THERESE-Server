import { useState, useEffect } from "react";
import { useChatStore } from "../stores/chatStore";
import NavBar from "../components/NavBar";
import ConversationList from "../components/chat/ConversationList";
import MessageList from "../components/chat/MessageList";
import ChatInput from "../components/chat/ChatInput";

export default function ChatPage() {
  const { error, clearError } = useChatStore();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  useEffect(() => {
    document.title = "Chat - Thérèse";
  }, []);

  return (
    <div className="h-screen flex flex-col overflow-hidden">
      {/* Header avec NavBar */}
      <div className="shrink-0 relative">
        <NavBar />
        {/* Bouton menu mobile pour sidebar conversations */}
        <button
          onClick={() => setSidebarOpen(!sidebarOpen)}
          className="md:hidden absolute left-2 top-1/2 -translate-y-1/2 text-[var(--color-muted)] hover:text-[var(--color-text)] p-1"
          aria-label="Menu conversations"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="20"
            height="20"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M3 12h18" />
            <path d="M3 6h18" />
            <path d="M3 18h18" />
          </svg>
        </button>
      </div>

      {/* Bandeau d'erreur */}
      {error && (
        <div role="alert" className="bg-red-500/10 border-b border-red-500/30 text-red-400 px-4 py-2 text-sm flex items-center justify-between shrink-0">
          <span>{error}</span>
          <button
            onClick={clearError}
            className="text-red-400 hover:text-red-300 ml-4"
          >
            Fermer
          </button>
        </div>
      )}

      {/* Corps principal */}
      <div className="flex-1 flex overflow-hidden relative">
        {/* Overlay mobile */}
        {sidebarOpen && (
          <div
            className="fixed inset-0 bg-black/50 z-10 md:hidden"
            onClick={() => setSidebarOpen(false)}
          />
        )}

        {/* Sidebar conversations */}
        <aside
          className={`
            w-72 border-r border-slate-800 bg-[var(--color-bg)] shrink-0
            absolute md:relative z-20 h-full
            transition-transform duration-200 ease-in-out
            ${sidebarOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0"}
          `}
        >
          <ConversationList />
        </aside>

        {/* Zone principale */}
        <main id="main-content" className="flex-1 flex flex-col min-w-0">
          <MessageList />
          <ChatInput />
        </main>
      </div>
    </div>
  );
}
