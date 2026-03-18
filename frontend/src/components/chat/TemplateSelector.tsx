import { useState, useEffect, useRef } from "react";
import {
  Mail,
  Scale,
  FileText,
  ClipboardList,
  Megaphone,
  Users,
  Sparkles,
  ChevronDown,
  X,
} from "lucide-react";
import { fetchTemplates, type PromptTemplate } from "../../services/api/templateService";

const CATEGORY_META: Record<
  string,
  { label: string; icon: React.ComponentType<{ size?: number; className?: string }> }
> = {
  courrier: { label: "Courrier", icon: Mail },
  deliberation: { label: "D\u00e9lib\u00e9ration", icon: Scale },
  note: { label: "Note", icon: FileText },
  synthese: { label: "Synth\u00e8se", icon: ClipboardList },
  communication: { label: "Communication", icon: Megaphone },
  rh: { label: "Ressources humaines", icon: Users },
  general: { label: "G\u00e9n\u00e9ral", icon: Sparkles },
};

function getIconComponent(
  iconName: string | null
): React.ComponentType<{ size?: number; className?: string }> {
  switch (iconName) {
    case "Mail":
      return Mail;
    case "Scale":
      return Scale;
    case "FileText":
      return FileText;
    case "ClipboardList":
      return ClipboardList;
    case "Megaphone":
      return Megaphone;
    case "Users":
      return Users;
    case "Sparkles":
      return Sparkles;
    default:
      return FileText;
  }
}

interface TemplateSelectorProps {
  onSelect: (prompt: string) => void;
}

export default function TemplateSelector({ onSelect }: TemplateSelectorProps) {
  const [open, setOpen] = useState(false);
  const [templates, setTemplates] = useState<PromptTemplate[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;

    setLoading(true);
    setError(null);
    fetchTemplates()
      .then((data) => {
        setTemplates(data);
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : "Erreur de chargement");
      })
      .finally(() => {
        setLoading(false);
      });
  }, [open]);

  // Fermer au clic en dehors
  useEffect(() => {
    if (!open) return;

    function handleClickOutside(e: MouseEvent) {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [open]);

  // Regrouper par categorie
  const grouped: Record<string, PromptTemplate[]> = {};
  for (const tpl of templates) {
    if (!grouped[tpl.category]) {
      grouped[tpl.category] = [];
    }
    grouped[tpl.category].push(tpl);
  }

  // Ordre des categories
  const categoryOrder = [
    "courrier",
    "deliberation",
    "note",
    "synthese",
    "communication",
    "rh",
    "general",
  ];
  const sortedCategories = categoryOrder.filter((c) => grouped[c]);

  function handleSelect(tpl: PromptTemplate) {
    onSelect(tpl.prompt);
    setOpen(false);
  }

  return (
    <div className="relative" ref={panelRef}>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 px-3 py-2 text-sm text-[var(--color-muted)] hover:text-[var(--color-text)] bg-slate-800/50 hover:bg-slate-800 border border-slate-700 rounded-lg transition-colors"
        title="Mod\u00e8les de prompts"
      >
        <FileText size={16} />
        <span className="hidden sm:inline">Mod\u00e8les</span>
        <ChevronDown size={14} className={`transition-transform ${open ? "rotate-180" : ""}`} />
      </button>

      {open && (
        <div className="absolute bottom-full left-0 mb-2 w-80 sm:w-96 max-h-[60vh] overflow-y-auto bg-[var(--color-bg)] border border-slate-700 rounded-xl shadow-xl z-50">
          {/* En-tete */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-slate-800">
            <h3 className="text-sm font-semibold text-[var(--color-text)]">
              Mod\u00e8les de prompts
            </h3>
            <button
              type="button"
              onClick={() => setOpen(false)}
              className="text-[var(--color-muted)] hover:text-[var(--color-text)]"
            >
              <X size={16} />
            </button>
          </div>

          {/* Contenu */}
          <div className="p-2">
            {loading && (
              <p className="text-sm text-[var(--color-muted)] text-center py-4">
                Chargement...
              </p>
            )}

            {error && (
              <p className="text-sm text-red-400 text-center py-4">{error}</p>
            )}

            {!loading && !error && templates.length === 0 && (
              <p className="text-sm text-[var(--color-muted)] text-center py-4">
                Aucun mod\u00e8le disponible. Un administrateur peut initialiser les mod\u00e8les par d\u00e9faut.
              </p>
            )}

            {!loading &&
              !error &&
              sortedCategories.map((cat) => {
                const meta = CATEGORY_META[cat] || {
                  label: cat,
                  icon: FileText,
                };
                const CategoryIcon = meta.icon;
                return (
                  <div key={cat} className="mb-2">
                    <div className="flex items-center gap-2 px-2 py-1.5 text-xs font-medium text-[var(--color-muted)] uppercase tracking-wide">
                      <CategoryIcon size={14} />
                      {meta.label}
                    </div>
                    {grouped[cat].map((tpl) => {
                      const TplIcon = getIconComponent(tpl.icon);
                      return (
                        <button
                          key={tpl.id}
                          type="button"
                          onClick={() => handleSelect(tpl)}
                          className="w-full text-left px-3 py-2 rounded-lg hover:bg-slate-800/70 transition-colors group"
                        >
                          <div className="flex items-start gap-2">
                            <TplIcon
                              size={16}
                              className="mt-0.5 text-[var(--color-primary)] shrink-0"
                            />
                            <div className="min-w-0">
                              <div className="text-sm font-medium text-[var(--color-text)] group-hover:text-[var(--color-cyan)]">
                                {tpl.name}
                              </div>
                              <div className="text-xs text-[var(--color-muted)] truncate mt-0.5">
                                {tpl.prompt.slice(0, 80)}
                                {tpl.prompt.length > 80 ? "..." : ""}
                              </div>
                            </div>
                          </div>
                        </button>
                      );
                    })}
                  </div>
                );
              })}
          </div>
        </div>
      )}
    </div>
  );
}
