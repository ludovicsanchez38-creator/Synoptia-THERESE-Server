import { useEffect, useState, useCallback } from "react";
import NavBar from "../components/NavBar";
import { Button, Spinner, Badge } from "../components/ui";
import {
  fetchSkills,
  fetchSkillSchema,
  executeSkill,
  downloadSkillFile,
  type SkillInfo,
  type SkillSchema,
  type SkillFieldSchema,
  type SkillExecuteResponse,
} from "../services/api/skillService";
import { useToastStore } from "../stores/toastStore";

// -- Catégories frontend (le backend n'expose pas de champ "category") -------
type Category = "generation" | "text" | "analysis" | "planning";

const CATEGORY_META: Record<
  Category,
  { label: string; color: string; icon: string }
> = {
  generation: {
    label: "Génération",
    color: "bg-cyan-900/40 text-cyan-400",
    icon: "M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z",
  },
  text: {
    label: "Texte",
    color: "bg-violet-900/40 text-violet-400",
    icon: "M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z",
  },
  analysis: {
    label: "Analyse",
    color: "bg-amber-900/40 text-amber-400",
    icon: "M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z",
  },
  planning: {
    label: "Planification",
    color: "bg-emerald-900/40 text-emerald-400",
    icon: "M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z",
  },
};

const FORMAT_LABELS: Record<string, { label: string; badge: string }> = {
  docx: { label: "DOCX", badge: "bg-blue-900/40 text-blue-400" },
  pptx: { label: "PPTX", badge: "bg-orange-900/40 text-orange-400" },
  xlsx: { label: "XLSX", badge: "bg-green-900/40 text-green-400" },
  html: { label: "HTML", badge: "bg-pink-900/40 text-pink-400" },
  pdf: { label: "PDF", badge: "bg-red-900/40 text-red-400" },
  md: { label: "Texte", badge: "bg-slate-700 text-slate-300" },
};

// Mapping skill_id → catégorie
const SKILL_CATEGORIES: Record<string, Category> = {
  "docx-pro": "generation",
  "pptx-pro": "generation",
  "xlsx-pro": "generation",
  "html-web": "generation",
  "email-pro": "text",
  "linkedin-post": "text",
  "proposal-pro": "text",
  "explain-concept": "text",
  "best-practices": "text",
  "analyze-xlsx": "analysis",
  "analyze-pdf": "analysis",
  "analyze-website": "analysis",
  "market-research": "analysis",
  "analyze-ai-tool": "analysis",
  "plan-meeting": "planning",
  "plan-project": "planning",
  "plan-week": "planning",
  "plan-goals": "planning",
  "workflow-automation": "planning",
};

function getCategory(skillId: string): Category {
  return SKILL_CATEGORIES[skillId] || "text";
}

// -- Composant principal -----------------------------------------------------

export default function SkillsPage() {
  const [skills, setSkills] = useState<SkillInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeCategory, setActiveCategory] = useState<Category | "all">("all");

  // Panneau d'exécution
  const [selectedSkill, setSelectedSkill] = useState<SkillInfo | null>(null);
  const [schema, setSchema] = useState<SkillSchema | null>(null);
  const [schemaLoading, setSchemaLoading] = useState(false);
  const [formValues, setFormValues] = useState<Record<string, string>>({});
  const [executing, setExecuting] = useState(false);
  const [result, setResult] = useState<SkillExecuteResponse | null>(null);

  const loadSkills = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await fetchSkills();
      setSkills(Array.isArray(data) ? data : []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erreur de chargement");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    document.title = "Skills - Thérèse";
    loadSkills();
  }, [loadSkills]);

  // Ouvrir le panneau d'exécution
  const openSkill = async (skill: SkillInfo) => {
    setSelectedSkill(skill);
    setResult(null);
    setFormValues({});
    setSchemaLoading(true);
    try {
      const s = await fetchSkillSchema(skill.skill_id);
      setSchema(s);
      // Pré-remplir les valeurs par défaut
      const defaults: Record<string, string> = {};
      for (const [key, field] of Object.entries(s.schema)) {
        if (field.default) defaults[key] = field.default;
      }
      setFormValues(defaults);
    } catch {
      setSchema(null);
    } finally {
      setSchemaLoading(false);
    }
  };

  const closePanel = () => {
    setSelectedSkill(null);
    setSchema(null);
    setResult(null);
    setFormValues({});
  };

  // Exécuter le skill
  const handleExecute = async () => {
    if (!selectedSkill) return;

    // Construire le prompt à partir des champs
    const promptParts: string[] = [];
    const context: Record<string, string> = {};

    if (schema) {
      for (const [key, field] of Object.entries(schema.schema)) {
        const value = formValues[key]?.trim();
        if (field.required && !value) {
          useToastStore
            .getState()
            .addToast("error", `Le champ "${field.label}" est requis`);
          return;
        }
        if (value) {
          if (key === "prompt") {
            promptParts.unshift(value);
          } else {
            promptParts.push(`${field.label} : ${value}`);
            context[key] = value;
          }
        }
      }
    }

    const prompt = promptParts.join("\n");
    if (!prompt) {
      useToastStore.getState().addToast("error", "Saisis au moins un prompt");
      return;
    }

    try {
      setExecuting(true);
      setResult(null);
      const res = await executeSkill(
        selectedSkill.skill_id,
        prompt,
        formValues["title"] || undefined,
        undefined,
        context,
      );
      setResult(res);
      if (res.success) {
        useToastStore.getState().addToast("success", "Skill exécuté avec succès");
      } else {
        useToastStore
          .getState()
          .addToast("error", res.error || "Erreur d'exécution");
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Erreur d'exécution";
      setResult({ success: false, error: msg });
      useToastStore.getState().addToast("error", msg);
    } finally {
      setExecuting(false);
    }
  };

  const handleDownload = async () => {
    if (!result?.file_id) return;
    try {
      await downloadSkillFile(result.file_id, result.file_name || undefined);
    } catch (err) {
      useToastStore
        .getState()
        .addToast(
          "error",
          err instanceof Error ? err.message : "Erreur de téléchargement",
        );
    }
  };

  // Filtrage par catégorie
  const filtered =
    activeCategory === "all"
      ? skills
      : skills.filter((s) => getCategory(s.skill_id) === activeCategory);

  // Grouper par catégorie pour l'affichage
  const grouped = filtered.reduce<Record<Category, SkillInfo[]>>(
    (acc, skill) => {
      const cat = getCategory(skill.skill_id);
      if (!acc[cat]) acc[cat] = [];
      acc[cat].push(skill);
      return acc;
    },
    {} as Record<Category, SkillInfo[]>,
  );

  const categoryOrder: Category[] = [
    "generation",
    "text",
    "analysis",
    "planning",
  ];

  return (
    <div className="min-h-screen flex flex-col" data-testid="skills-page">
      <NavBar />

      <main
        id="main-content"
        className="flex-1 p-4 md:p-6 max-w-6xl mx-auto w-full"
      >
        {/* Titre */}
        <div className="mb-6">
          <h2 className="text-xl font-bold text-[var(--color-text)]">
            Skills
          </h2>
          <p className="text-sm text-[var(--color-muted)] mt-1">
            Bibliothèque de compétences IA pour générer des documents, analyser
            et planifier.
          </p>
        </div>

        {/* Erreur */}
        {error && (
          <div
            role="alert"
            className="mb-4 p-3 bg-red-900/30 border border-red-700 rounded-lg text-red-400 text-sm"
          >
            {error}
            <button onClick={() => setError(null)} className="ml-2 underline">
              Fermer
            </button>
          </div>
        )}

        {/* Filtres catégorie */}
        <div className="flex gap-1 mb-6 border-b border-slate-800 overflow-x-auto">
          <button
            onClick={() => setActiveCategory("all")}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors whitespace-nowrap ${
              activeCategory === "all"
                ? "border-[var(--color-cyan)] text-[var(--color-cyan)]"
                : "border-transparent text-[var(--color-muted)] hover:text-[var(--color-text)]"
            }`}
          >
            Tous ({skills.length})
          </button>
          {categoryOrder.map((cat) => {
            const count = skills.filter(
              (s) => getCategory(s.skill_id) === cat,
            ).length;
            if (count === 0) return null;
            return (
              <button
                key={cat}
                onClick={() => setActiveCategory(cat)}
                className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors whitespace-nowrap ${
                  activeCategory === cat
                    ? "border-[var(--color-cyan)] text-[var(--color-cyan)]"
                    : "border-transparent text-[var(--color-muted)] hover:text-[var(--color-text)]"
                }`}
              >
                {CATEGORY_META[cat].label} ({count})
              </button>
            );
          })}
        </div>

        {/* Chargement */}
        {loading && (
          <div className="flex items-center justify-center py-12">
            <Spinner />
            <span className="ml-3 text-[var(--color-muted)]">
              Chargement des skills...
            </span>
          </div>
        )}

        {/* Liste vide */}
        {!loading && filtered.length === 0 && (
          <div className="text-center py-12 text-[var(--color-muted)]">
            Aucun skill disponible
          </div>
        )}

        {/* Grille par catégorie */}
        {!loading &&
          categoryOrder.map((cat) => {
            const catSkills = grouped[cat];
            if (!catSkills || catSkills.length === 0) return null;
            const meta = CATEGORY_META[cat];

            return (
              <section key={cat} className="mb-8">
                <div className="flex items-center gap-2 mb-3">
                  <svg
                    className="w-5 h-5 text-[var(--color-muted)]"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth={1.5}
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d={meta.icon}
                    />
                  </svg>
                  <h3 className="text-sm font-semibold text-[var(--color-muted)] uppercase tracking-wider">
                    {meta.label}
                  </h3>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3" data-testid="skills-list">
                  {catSkills.map((skill) => (
                    <SkillCard
                      key={skill.skill_id}
                      skill={skill}
                      category={cat}
                      isSelected={selectedSkill?.skill_id === skill.skill_id}
                      onClick={() => openSkill(skill)}
                    />
                  ))}
                </div>
              </section>
            );
          })}
      </main>

      {/* Panneau latéral d'exécution */}
      {selectedSkill && (
        <ExecutionPanel
          skill={selectedSkill}
          schema={schema}
          schemaLoading={schemaLoading}
          formValues={formValues}
          setFormValues={setFormValues}
          executing={executing}
          result={result}
          onExecute={handleExecute}
          onDownload={handleDownload}
          onClose={closePanel}
        />
      )}
    </div>
  );
}

// -- Sous-composants ---------------------------------------------------------

function SkillCard({
  skill,
  category,
  isSelected,
  onClick,
}: {
  skill: SkillInfo;
  category: Category;
  isSelected: boolean;
  onClick: () => void;
}) {
  const catMeta = CATEGORY_META[category];
  const fmt = FORMAT_LABELS[skill.format] || {
    label: skill.format.toUpperCase(),
    badge: "bg-slate-700 text-slate-300",
  };

  return (
    <button
      onClick={onClick}
      data-testid="skill-item"
      className={`text-left p-4 rounded-xl border transition-all ${
        isSelected
          ? "border-[var(--color-cyan)] bg-slate-800/50 ring-1 ring-[var(--color-cyan)]/30"
          : "border-slate-700 bg-slate-800/20 hover:bg-slate-800/40 hover:border-slate-600"
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <h4 className="text-sm font-medium text-[var(--color-text)] truncate">
            {skill.name}
          </h4>
          <p className="text-xs text-[var(--color-muted)] mt-1 line-clamp-2">
            {skill.description}
          </p>
        </div>
        <svg
          className="w-4 h-4 text-[var(--color-muted)] shrink-0 mt-0.5"
          fill="none"
          stroke="currentColor"
          strokeWidth={1.5}
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d={catMeta.icon}
          />
        </svg>
      </div>
      <div className="flex items-center gap-2 mt-3">
        <Badge className={catMeta.color}>{catMeta.label}</Badge>
        <Badge className={fmt.badge}>{fmt.label}</Badge>
      </div>
    </button>
  );
}

function ExecutionPanel({
  skill,
  schema,
  schemaLoading,
  formValues,
  setFormValues,
  executing,
  result,
  onExecute,
  onDownload,
  onClose,
}: {
  skill: SkillInfo;
  schema: SkillSchema | null;
  schemaLoading: boolean;
  formValues: Record<string, string>;
  setFormValues: React.Dispatch<React.SetStateAction<Record<string, string>>>;
  executing: boolean;
  result: SkillExecuteResponse | null;
  onExecute: () => void;
  onDownload: () => void;
  onClose: () => void;
}) {
  const fmt = FORMAT_LABELS[skill.format] || {
    label: skill.format.toUpperCase(),
    badge: "bg-slate-700 text-slate-300",
  };

  return (
    <>
      {/* Overlay */}
      <div
        className="fixed inset-0 bg-black/50 z-40"
        onClick={onClose}
      />

      {/* Panneau */}
      <div className="fixed inset-y-0 right-0 w-full max-w-lg bg-[var(--color-bg)] border-l border-slate-700 z-50 flex flex-col shadow-2xl animate-slide-in">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-800">
          <div className="flex-1 min-w-0">
            <h3 className="text-base font-semibold text-[var(--color-text)] truncate">
              {skill.name}
            </h3>
            <p className="text-xs text-[var(--color-muted)] mt-0.5">
              {skill.description}
            </p>
          </div>
          <div className="flex items-center gap-2 ml-3">
            <Badge className={fmt.badge}>{fmt.label}</Badge>
            <button
              onClick={onClose}
              className="text-[var(--color-muted)] hover:text-[var(--color-text)] transition-colors p-1"
              aria-label="Fermer le panneau"
            >
              <svg
                className="w-5 h-5"
                fill="none"
                stroke="currentColor"
                strokeWidth={2}
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M6 18L18 6M6 6l12 12"
                />
              </svg>
            </button>
          </div>
        </div>

        {/* Contenu scrollable */}
        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
          {schemaLoading && (
            <div className="flex items-center justify-center py-8">
              <Spinner size="sm" />
              <span className="ml-2 text-sm text-[var(--color-muted)]">
                Chargement du formulaire...
              </span>
            </div>
          )}

          {/* Champs dynamiques */}
          {!schemaLoading &&
            schema &&
            Object.entries(schema.schema).map(([key, field]) => (
              <DynamicField
                key={key}
                fieldKey={key}
                field={field}
                value={formValues[key] || ""}
                onChange={(val) =>
                  setFormValues((prev) => ({ ...prev, [key]: val }))
                }
              />
            ))}

          {/* Résultat */}
          {result && (
            <div
              className={`p-4 rounded-xl border ${
                result.success
                  ? "bg-emerald-900/20 border-emerald-700"
                  : "bg-red-900/20 border-red-700"
              }`}
            >
              {result.success ? (
                <>
                  <div className="flex items-center gap-2 mb-2">
                    <svg
                      className="w-5 h-5 text-emerald-400"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth={2}
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
                      />
                    </svg>
                    <span className="text-sm font-medium text-emerald-400">
                      Généré avec succès
                    </span>
                  </div>

                  {/* Aperçu texte (pour skills text/analysis) */}
                  {result.preview && (
                    <div className="mb-3 p-3 bg-slate-800/40 rounded-lg max-h-60 overflow-y-auto">
                      <pre className="text-xs text-[var(--color-text)] whitespace-pre-wrap font-sans">
                        {result.preview}
                      </pre>
                    </div>
                  )}

                  {/* Bouton téléchargement (pour skills file) */}
                  {result.file_id && (
                    <Button
                      onClick={onDownload}
                      className="w-full bg-[var(--color-cyan)] text-[var(--color-bg)] hover:bg-[var(--color-cyan)]/80"
                    >
                      <span className="flex items-center justify-center gap-2">
                        <svg
                          className="w-4 h-4"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth={2}
                          viewBox="0 0 24 24"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
                          />
                        </svg>
                        Télécharger {result.file_name || "le fichier"}
                        {result.file_size
                          ? ` (${formatSize(result.file_size)})`
                          : ""}
                      </span>
                    </Button>
                  )}
                </>
              ) : (
                <div className="flex items-start gap-2">
                  <svg
                    className="w-5 h-5 text-red-400 shrink-0 mt-0.5"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth={2}
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                    />
                  </svg>
                  <div>
                    <p className="text-sm font-medium text-red-400">
                      Erreur d'exécution
                    </p>
                    <p className="text-xs text-red-400/80 mt-1">
                      {result.error}
                    </p>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer avec bouton exécuter */}
        <div className="px-5 py-4 border-t border-slate-800">
          <Button
            onClick={onExecute}
            disabled={executing || schemaLoading}
            className="w-full bg-[var(--color-primary)] hover:bg-[var(--color-primary)]/80 text-white"
            data-testid="skill-execute-btn"
          >
            {executing ? (
              <span className="flex items-center justify-center gap-2">
                <Spinner size="sm" />
                Exécution en cours...
              </span>
            ) : (
              <span className="flex items-center justify-center gap-2">
                <svg
                  className="w-4 h-4"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth={2}
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"
                  />
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                  />
                </svg>
                Exécuter
              </span>
            )}
          </Button>
        </div>
      </div>
    </>
  );
}

function DynamicField({
  fieldKey,
  field,
  value,
  onChange,
}: {
  fieldKey: string;
  field: SkillFieldSchema;
  value: string;
  onChange: (val: string) => void;
}) {
  const id = `skill-field-${fieldKey}`;

  return (
    <div>
      <label
        htmlFor={id}
        className="block text-sm text-[var(--color-muted)] mb-1"
      >
        {field.label}
        {field.required && <span className="text-red-400 ml-1">*</span>}
      </label>

      {field.type === "textarea" ? (
        <textarea
          id={id}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={field.placeholder || ""}
          required={field.required}
          rows={4}
          className="w-full px-3 py-2 bg-slate-800 border border-slate-600 rounded-lg text-[var(--color-text)] text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-cyan)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--color-bg)] resize-y"
        />
      ) : field.type === "select" && field.options ? (
        <select
          id={id}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="w-full px-3 py-2 bg-slate-800 border border-slate-600 rounded-lg text-[var(--color-text)] text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-cyan)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--color-bg)]"
        >
          <option value="">Choisir...</option>
          {field.options.map((opt) => (
            <option key={opt} value={opt}>
              {opt}
            </option>
          ))}
        </select>
      ) : (
        <input
          id={id}
          type={field.type === "number" ? "number" : "text"}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={field.placeholder || ""}
          required={field.required}
          className="w-full px-3 py-2 bg-slate-800 border border-slate-600 rounded-lg text-[var(--color-text)] text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-cyan)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--color-bg)]"
        />
      )}

      {field.help_text && (
        <p className="text-xs text-[var(--color-muted)] mt-1">
          {field.help_text}
        </p>
      )}
    </div>
  );
}

// -- Helpers -----------------------------------------------------------------

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} o`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} Ko`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} Mo`;
}
