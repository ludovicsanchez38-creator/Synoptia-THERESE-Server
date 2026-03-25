import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Search, MessageSquare, User, CheckSquare, X } from "lucide-react";
import { apiFetch } from "../services/api/index";

interface SearchResult {
  type: "conversation" | "contact" | "task";
  id: string;
  title: string;
  subtitle: string | null;
}

interface SearchResponse {
  query: string;
  results: SearchResult[];
  total: number;
}

const TYPE_ICONS = {
  conversation: MessageSquare,
  contact: User,
  task: CheckSquare,
} as const;

const TYPE_LABELS = {
  conversation: "Conversation",
  contact: "Contact",
  task: "Tâche",
} as const;

export default function SearchModal({ onClose }: { onClose: () => void }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  // Recherche avec debounce
  useEffect(() => {
    if (query.length < 2) {
      setResults([]);
      return;
    }

    const timer = setTimeout(async () => {
      setLoading(true);
      try {
        const data = await apiFetch<SearchResponse>(
          `/api/search?q=${encodeURIComponent(query)}&limit=15`
        );
        setResults(data.results);
        setSelectedIndex(0);
      } catch {
        setResults([]);
      } finally {
        setLoading(false);
      }
    }, 250);

    return () => clearTimeout(timer);
  }, [query]);

  const navigateToResult = useCallback(
    (result: SearchResult) => {
      switch (result.type) {
        case "conversation":
          navigate("/chat");
          break;
        case "contact":
          navigate("/crm");
          break;
        case "task":
          navigate("/tasks");
          break;
      }
      onClose();
    },
    [navigate, onClose]
  );

  const handleKeyDown = (e: React.KeyboardEvent) => {
    switch (e.key) {
      case "ArrowDown":
        e.preventDefault();
        setSelectedIndex((i) => Math.min(i + 1, results.length - 1));
        break;
      case "ArrowUp":
        e.preventDefault();
        setSelectedIndex((i) => Math.max(i - 1, 0));
        break;
      case "Enter":
        e.preventDefault();
        if (results[selectedIndex]) {
          navigateToResult(results[selectedIndex]);
        }
        break;
      case "Escape":
        onClose();
        break;
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center pt-[20vh] bg-black/60 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="w-full max-w-lg bg-[var(--color-bg)] border border-slate-700 rounded-xl shadow-2xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Input */}
        <div className="flex items-center gap-3 px-4 py-3 border-b border-slate-700">
          <Search className="w-5 h-5 text-[var(--color-muted)]" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Rechercher conversations, contacts, tâches..."
            className="flex-1 bg-transparent text-[var(--color-text)] placeholder-[var(--color-muted)] outline-none text-sm"
          />
          <button
            onClick={onClose}
            className="text-[var(--color-muted)] hover:text-[var(--color-text)]"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Résultats */}
        <div className="max-h-80 overflow-y-auto">
          {loading && (
            <div className="px-4 py-6 text-center text-sm text-[var(--color-muted)]">
              Recherche...
            </div>
          )}

          {!loading && query.length >= 2 && results.length === 0 && (
            <div className="px-4 py-6 text-center text-sm text-[var(--color-muted)]">
              Aucun résultat pour "{query}"
            </div>
          )}

          {results.map((result, i) => {
            const Icon = TYPE_ICONS[result.type];
            return (
              <button
                key={`${result.type}-${result.id}`}
                onClick={() => navigateToResult(result)}
                className={`w-full flex items-center gap-3 px-4 py-2.5 text-left text-sm transition-colors ${
                  i === selectedIndex
                    ? "bg-[var(--color-primary)]/20 text-[var(--color-text)]"
                    : "text-[var(--color-text)] hover:bg-slate-800/50"
                }`}
              >
                <Icon className="w-4 h-4 text-[var(--color-muted)] shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="truncate">{result.title}</div>
                  {result.subtitle && (
                    <div className="text-xs text-[var(--color-muted)] truncate">
                      {result.subtitle}
                    </div>
                  )}
                </div>
                <span className="text-[10px] text-[var(--color-muted)] bg-slate-700/50 px-1.5 py-0.5 rounded shrink-0">
                  {TYPE_LABELS[result.type]}
                </span>
              </button>
            );
          })}
        </div>

        {/* Footer */}
        <div className="flex items-center gap-4 px-4 py-2 border-t border-slate-700 text-[10px] text-[var(--color-muted)]">
          <span>
            <kbd className="px-1 py-0.5 bg-slate-700 rounded text-[9px]">&uarr;</kbd>{" "}
            <kbd className="px-1 py-0.5 bg-slate-700 rounded text-[9px]">&darr;</kbd> naviguer
          </span>
          <span>
            <kbd className="px-1 py-0.5 bg-slate-700 rounded text-[9px]">Enter</kbd> ouvrir
          </span>
          <span>
            <kbd className="px-1 py-0.5 bg-slate-700 rounded text-[9px]">Esc</kbd> fermer
          </span>
        </div>
      </div>
    </div>
  );
}
