import { useEffect, useState, useCallback } from "react";
import NavBar from "../components/NavBar";
import {
  fetchTasks,
  createTask,
  deleteTask,
  completeTask,
  type Task,
} from "../services/api/taskService";

type StatusFilter = "all" | "todo" | "in_progress" | "done";

const statusLabels: Record<string, string> = {
  todo: "\u00c0 faire",
  in_progress: "En cours",
  done: "Termin\u00e9e",
};

const statusColors: Record<string, string> = {
  todo: "bg-slate-700 text-slate-300",
  in_progress: "bg-blue-900/40 text-blue-400",
  done: "bg-emerald-900/40 text-emerald-400",
};

const priorityColors: Record<string, string> = {
  low: "bg-slate-700 text-slate-300",
  medium: "bg-yellow-900/40 text-yellow-400",
  high: "bg-red-900/40 text-red-400",
};

const priorityLabels: Record<string, string> = {
  low: "Basse",
  medium: "Moyenne",
  high: "Haute",
};

export default function TasksPage() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<StatusFilter>("all");
  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState({
    title: "",
    description: "",
    priority: "medium",
  });
  const [submitting, setSubmitting] = useState(false);

  const loadTasks = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await fetchTasks();
      setTasks(Array.isArray(data) ? data : []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erreur de chargement");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    document.title = "T\u00e2ches - Th\u00e9r\u00e8se";
    loadTasks();
  }, [loadTasks]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.title.trim()) return;
    try {
      setSubmitting(true);
      const task = await createTask({
        title: formData.title.trim(),
        description: formData.description.trim() || undefined,
        priority: formData.priority,
        status: "todo",
      });
      setTasks((prev) => [task, ...prev]);
      setFormData({ title: "", description: "", priority: "medium" });
      setShowForm(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erreur de cr\u00e9ation");
    } finally {
      setSubmitting(false);
    }
  };

  const handleComplete = async (id: string) => {
    try {
      const updated = await completeTask(id);
      setTasks((prev) => prev.map((t) => (t.id === id ? updated : t)));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erreur");
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteTask(id);
      setTasks((prev) => prev.filter((t) => t.id !== id));
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Erreur de suppression"
      );
    }
  };

  const filtered =
    filter === "all" ? tasks : tasks.filter((t) => t.status === filter);

  const counts = {
    all: tasks.length,
    todo: tasks.filter((t) => t.status === "todo").length,
    in_progress: tasks.filter((t) => t.status === "in_progress").length,
    done: tasks.filter((t) => t.status === "done").length,
  };

  return (
    <div className="min-h-screen flex flex-col">
      <NavBar />

      <main className="flex-1 p-4 md:p-6 max-w-5xl mx-auto w-full">
        {/* Titre + bouton */}
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-xl font-bold text-[var(--color-text)]">
            T&acirc;ches
          </h2>
          <button
            onClick={() => setShowForm(!showForm)}
            className="px-4 py-2 text-sm font-medium rounded-lg bg-[var(--color-primary)] text-white hover:opacity-90 transition-opacity"
          >
            {showForm ? "Annuler" : "Nouvelle t\u00e2che"}
          </button>
        </div>

        {/* Erreur */}
        {error && (
          <div role="alert" className="mb-4 p-3 bg-red-900/30 border border-red-700 rounded-lg text-red-400 text-sm">
            {error}
            <button
              onClick={() => setError(null)}
              className="ml-2 underline"
            >
              Fermer
            </button>
          </div>
        )}

        {/* Formulaire de création */}
        {showForm && (
          <form
            onSubmit={handleCreate}
            className="mb-6 p-4 bg-slate-800/30 border border-slate-700 rounded-xl space-y-3"
          >
            <div>
              <label className="block text-sm text-[var(--color-muted)] mb-1">
                Titre *
              </label>
              <input
                type="text"
                value={formData.title}
                onChange={(e) =>
                  setFormData({ ...formData, title: e.target.value })
                }
                className="w-full px-3 py-2 bg-slate-800 border border-slate-600 rounded-lg text-[var(--color-text)] text-sm focus:outline-none focus:border-[var(--color-cyan)]"
                placeholder="Titre de la t\u00e2che..."
                autoFocus
              />
            </div>
            <div>
              <label className="block text-sm text-[var(--color-muted)] mb-1">
                Description
              </label>
              <textarea
                value={formData.description}
                onChange={(e) =>
                  setFormData({ ...formData, description: e.target.value })
                }
                className="w-full px-3 py-2 bg-slate-800 border border-slate-600 rounded-lg text-[var(--color-text)] text-sm focus:outline-none focus:border-[var(--color-cyan)] resize-none"
                rows={2}
                placeholder="Description optionnelle..."
              />
            </div>
            <div className="flex items-center gap-4">
              <div>
                <label className="block text-sm text-[var(--color-muted)] mb-1">
                  Priorit&eacute;
                </label>
                <select
                  value={formData.priority}
                  onChange={(e) =>
                    setFormData({ ...formData, priority: e.target.value })
                  }
                  className="bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-sm text-[var(--color-text)]"
                >
                  <option value="low">Basse</option>
                  <option value="medium">Moyenne</option>
                  <option value="high">Haute</option>
                </select>
              </div>
              <div className="flex-1" />
              <button
                type="submit"
                disabled={submitting || !formData.title.trim()}
                className="px-4 py-2 text-sm font-medium rounded-lg bg-[var(--color-cyan)] text-[var(--color-bg)] hover:opacity-90 transition-opacity disabled:opacity-50"
              >
                {submitting ? "Cr\u00e9ation..." : "Cr\u00e9er"}
              </button>
            </div>
          </form>
        )}

        {/* Filtres par statut */}
        <div className="flex gap-1 mb-4 border-b border-slate-800">
          {(
            [
              { key: "all" as StatusFilter, label: "Toutes" },
              { key: "todo" as StatusFilter, label: "\u00c0 faire" },
              {
                key: "in_progress" as StatusFilter,
                label: "En cours",
              },
              { key: "done" as StatusFilter, label: "Termin\u00e9es" },
            ] as const
          ).map((tab) => (
            <button
              key={tab.key}
              onClick={() => setFilter(tab.key)}
              className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                filter === tab.key
                  ? "border-[var(--color-cyan)] text-[var(--color-cyan)]"
                  : "border-transparent text-[var(--color-muted)] hover:text-[var(--color-text)]"
              }`}
            >
              {tab.label} ({counts[tab.key]})
            </button>
          ))}
        </div>

        {/* Chargement */}
        {loading && (
          <div className="flex items-center justify-center py-12">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[var(--color-cyan)]" />
            <span className="ml-3 text-[var(--color-muted)]">
              Chargement...
            </span>
          </div>
        )}

        {/* Liste vide */}
        {!loading && filtered.length === 0 && (
          <div className="text-center py-12 text-[var(--color-muted)]">
            {filter === "all"
              ? "Aucune t\u00e2che pour le moment"
              : `Aucune t\u00e2che avec le statut "${statusLabels[filter] || filter}"`}
          </div>
        )}

        {/* Liste des tâches */}
        {!loading && filtered.length > 0 && (
          <div className="space-y-2">
            {filtered.map((task) => (
              <div
                key={task.id}
                className={`flex items-start gap-3 p-4 bg-slate-800/20 border border-slate-700 rounded-xl hover:bg-slate-800/30 transition-colors ${
                  task.status === "done" ? "opacity-60" : ""
                }`}
              >
                {/* Bouton complétion */}
                <button
                  onClick={() =>
                    task.status !== "done" && handleComplete(task.id)
                  }
                  disabled={task.status === "done"}
                  className={`mt-0.5 w-5 h-5 rounded-full border-2 flex items-center justify-center shrink-0 transition-colors ${
                    task.status === "done"
                      ? "border-emerald-500 bg-emerald-500"
                      : "border-slate-500 hover:border-[var(--color-cyan)]"
                  }`}
                  title={
                    task.status === "done"
                      ? "Termin\u00e9e"
                      : "Marquer comme termin\u00e9e"
                  }
                >
                  {task.status === "done" && (
                    <svg
                      width="10"
                      height="10"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="white"
                      strokeWidth="3"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    >
                      <polyline points="20 6 9 17 4 12" />
                    </svg>
                  )}
                </button>

                {/* Contenu */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span
                      className={`text-sm font-medium ${
                        task.status === "done"
                          ? "line-through text-[var(--color-muted)]"
                          : "text-[var(--color-text)]"
                      }`}
                    >
                      {task.title}
                    </span>
                    <span
                      className={`text-xs px-2 py-0.5 rounded ${priorityColors[task.priority]}`}
                    >
                      {priorityLabels[task.priority]}
                    </span>
                    <span
                      className={`text-xs px-2 py-0.5 rounded ${statusColors[task.status]}`}
                    >
                      {statusLabels[task.status]}
                    </span>
                  </div>
                  {task.description && (
                    <p className="text-xs text-[var(--color-muted)] mt-1 truncate">
                      {task.description}
                    </p>
                  )}
                  <div className="text-xs text-[var(--color-muted)] mt-1">
                    {new Date(task.created_at).toLocaleDateString("fr-FR")}
                    {task.due_date && (
                      <span className="ml-2">
                        &Eacute;ch&eacute;ance :{" "}
                        {new Date(task.due_date).toLocaleDateString("fr-FR")}
                      </span>
                    )}
                  </div>
                </div>

                {/* Supprimer */}
                <button
                  onClick={() => handleDelete(task.id)}
                  className="text-[var(--color-muted)] hover:text-red-400 transition-colors shrink-0"
                  title="Supprimer"
                >
                  <svg
                    width="16"
                    height="16"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <polyline points="3 6 5 6 21 6" />
                    <path d="M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6" />
                    <path d="M10 11v6" />
                    <path d="M14 11v6" />
                  </svg>
                </button>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
