import { useAuthStore } from "../../stores/authStore";

export default function AdminDashboard() {
  const { user } = useAuthStore();

  return (
    <div className="min-h-screen">
      <header className="flex items-center justify-between px-6 py-3 border-b border-slate-800">
        <div className="flex items-center gap-3">
          <h1 className="text-lg font-bold text-[var(--color-cyan)]">Thérèse Admin</h1>
          <span className="text-xs text-[var(--color-muted)] bg-slate-800 px-2 py-0.5 rounded">
            {user?.org_name}
          </span>
        </div>
        <a href="/chat" className="text-sm text-[var(--color-primary)] hover:underline">
          Retour au chat
        </a>
      </header>

      <main className="p-6">
        <h2 className="text-xl font-bold mb-6">Tableau de bord</h2>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
          {[
            { label: "Utilisateurs actifs", value: "-", color: "var(--color-cyan)" },
            { label: "Messages aujourd'hui", value: "-", color: "var(--color-primary)" },
            { label: "Coût LLM (mois)", value: "-", color: "var(--color-magenta)" },
            { label: "Modèles actifs", value: "-", color: "#10B981" },
          ].map((kpi) => (
            <div
              key={kpi.label}
              className="bg-slate-800/30 border border-slate-700 rounded-xl p-4"
            >
              <div className="text-sm text-[var(--color-muted)]">{kpi.label}</div>
              <div className="text-2xl font-bold mt-1" style={{ color: kpi.color }}>
                {kpi.value}
              </div>
            </div>
          ))}
        </div>

        <p className="text-[var(--color-muted)]">
          Dashboard en construction (P0-6)
        </p>
      </main>
    </div>
  );
}
