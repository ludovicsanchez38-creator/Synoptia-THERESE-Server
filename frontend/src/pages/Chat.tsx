import { useState } from "react";
import { useAuthStore } from "../stores/authStore";
import { useChatStore } from "../stores/chatStore";
import ConversationList from "../components/chat/ConversationList";
import MessageList from "../components/chat/MessageList";
import ChatInput from "../components/chat/ChatInput";

export default function ChatPage() {
  const { user, logout } = useAuthStore();
  const { error, clearError } = useChatStore();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="h-screen flex flex-col overflow-hidden">
      {/* Header */}
      <header className="flex items-center justify-between px-4 md:px-6 py-3 border-b border-slate-800 shrink-0">
        <div className="flex items-center gap-3">
          {/* Bouton menu mobile */}
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="md:hidden text-[var(--color-muted)] hover:text-[var(--color-text)]"
            aria-label="Menu"
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
          <h1 className="text-lg font-bold text-[var(--color-cyan)]">
            Th{"\u00e9"}r{"\u00e8"}se
          </h1>
          {user?.org_name && (
            <span className="text-xs text-[var(--color-muted)] bg-slate-800 px-2 py-0.5 rounded hidden sm:inline">
              {user.org_name}
            </span>
          )}
        </div>
        <div className="flex items-center gap-4">
          <span className="text-sm text-[var(--color-muted)] hidden sm:inline">
            {user?.name}
          </span>
          {user?.role === "admin" && (
            <a
              href="/admin"
              className="text-xs text-[var(--color-primary)] hover:underline"
            >
              Admin
            </a>
          )}
          <button
            onClick={logout}
            className="text-xs text-[var(--color-muted)] hover:text-red-400 transition-colors"
          >
            D{"\u00e9"}connexion
          </button>
        </div>
      </header>

      {/* Bandeau d'erreur */}
      {error && (
        <div className="bg-red-500/10 border-b border-red-500/30 text-red-400 px-4 py-2 text-sm flex items-center justify-between shrink-0">
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
        <main className="flex-1 flex flex-col min-w-0">
          <MessageList />
          <ChatInput />
        </main>
      </div>
    </div>
  );
}
