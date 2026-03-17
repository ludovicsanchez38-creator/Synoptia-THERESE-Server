import { useState } from "react";
import { useAuthStore } from "../stores/authStore";

export default function ChatPage() {
  const { user, logout } = useAuthStore();
  const [message, setMessage] = useState("");

  return (
    <div className="min-h-screen flex flex-col">
      {/* Header */}
      <header className="flex items-center justify-between px-6 py-3 border-b border-slate-800">
        <div className="flex items-center gap-3">
          <h1 className="text-lg font-bold text-[var(--color-cyan)]">Thérèse</h1>
          <span className="text-xs text-[var(--color-muted)] bg-slate-800 px-2 py-0.5 rounded">
            {user?.org_name}
          </span>
        </div>
        <div className="flex items-center gap-4">
          <span className="text-sm text-[var(--color-muted)]">{user?.name}</span>
          {user?.role === "admin" && (
            <a href="/admin" className="text-xs text-[var(--color-primary)] hover:underline">
              Admin
            </a>
          )}
          <button
            onClick={logout}
            className="text-xs text-[var(--color-muted)] hover:text-red-400 transition-colors"
          >
            Déconnexion
          </button>
        </div>
      </header>

      {/* Chat area */}
      <div className="flex-1 flex">
        {/* Sidebar - conversations */}
        <aside className="w-64 border-r border-slate-800 p-4">
          <button className="w-full py-2 text-sm bg-[var(--color-primary)]/10 border border-[var(--color-primary)]/30 rounded-lg text-[var(--color-primary)] hover:bg-[var(--color-primary)]/20 transition-colors">
            + Nouvelle conversation
          </button>
          <div className="mt-4 text-sm text-[var(--color-muted)]">
            Aucune conversation
          </div>
        </aside>

        {/* Main chat */}
        <main className="flex-1 flex flex-col">
          <div className="flex-1 flex items-center justify-center text-[var(--color-muted)]">
            Commencez une conversation avec Thérèse
          </div>

          {/* Input */}
          <div className="p-4 border-t border-slate-800">
            <form
              onSubmit={(e) => {
                e.preventDefault();
                // TODO: send message
                setMessage("");
              }}
              className="flex gap-2"
            >
              <input
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                placeholder="Écrivez votre message..."
                className="flex-1 px-4 py-2 bg-slate-800/50 border border-slate-700 rounded-lg focus:outline-none focus:border-[var(--color-primary)] text-[var(--color-text)]"
              />
              <button
                type="submit"
                className="px-6 py-2 bg-[var(--color-primary)] hover:bg-[var(--color-primary)]/80 rounded-lg font-medium transition-colors"
              >
                Envoyer
              </button>
            </form>
          </div>
        </main>
      </div>
    </div>
  );
}
