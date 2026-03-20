import { useEffect, useState, useCallback } from "react";
import { useAuthStore } from "../../stores/authStore";
import NavBar from "../../components/NavBar";
import {
  fetchAdminStats,
  fetchUsers,
  fetchAuditLogs,
  updateUser,
  type AdminStats,
  type UserItem,
  type AuditLogItem,
} from "../../services/api/adminService";

// -- Composant KPI --
function KpiCard({
  label,
  value,
  color,
}: {
  label: string;
  value: string | number;
  color: string;
}) {
  return (
    <div className="bg-slate-800/30 border border-slate-700 rounded-xl p-4">
      <div className="text-sm text-[var(--color-muted)]">{label}</div>
      <div className="text-2xl font-bold mt-1" style={{ color }}>
        {value}
      </div>
    </div>
  );
}

// -- Tableau Utilisateurs --
function UsersTable({
  users,
  currentUserId,
  onRoleChange,
  onToggleActive,
}: {
  users: UserItem[];
  currentUserId: string;
  onRoleChange: (userId: string, role: string) => void;
  onToggleActive: (userId: string, active: boolean) => void;
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-slate-700 text-left text-[var(--color-muted)]">
            <th className="pb-2 pr-4">Nom</th>
            <th className="pb-2 pr-4">Email</th>
            <th className="pb-2 pr-4">Role</th>
            <th className="pb-2 pr-4">Statut</th>
            <th className="pb-2 pr-4">Derniere connexion</th>
            <th className="pb-2">Actions</th>
          </tr>
        </thead>
        <tbody>
          {users.map((u) => (
            <tr
              key={u.id}
              className="border-b border-slate-800 hover:bg-slate-800/20"
            >
              <td className="py-2 pr-4 text-[var(--color-text)]">{u.name}</td>
              <td className="py-2 pr-4 text-[var(--color-muted)]">
                {u.email}
              </td>
              <td className="py-2 pr-4">
                <select
                  value={u.role}
                  onChange={(e) => onRoleChange(u.id, e.target.value)}
                  disabled={u.id === currentUserId}
                  className="bg-slate-800 border border-slate-600 rounded px-2 py-1 text-xs text-[var(--color-text)] disabled:opacity-50"
                >
                  <option value="admin">Admin</option>
                  <option value="manager">Manager</option>
                  <option value="agent">Agent</option>
                </select>
              </td>
              <td className="py-2 pr-4">
                <span
                  className={`text-xs px-2 py-0.5 rounded ${
                    u.is_active
                      ? "bg-emerald-900/40 text-emerald-400"
                      : "bg-red-900/40 text-red-400"
                  }`}
                >
                  {u.is_active ? "Actif" : "Inactif"}
                </span>
              </td>
              <td className="py-2 pr-4 text-[var(--color-muted)] text-xs">
                {u.last_login
                  ? new Date(u.last_login).toLocaleString("fr-FR")
                  : "Jamais"}
              </td>
              <td className="py-2">
                {u.id !== currentUserId && (
                  <button
                    onClick={() => onToggleActive(u.id, !u.is_active)}
                    className={`text-xs px-3 py-1 rounded border ${
                      u.is_active
                        ? "border-red-700 text-red-400 hover:bg-red-900/30"
                        : "border-emerald-700 text-emerald-400 hover:bg-emerald-900/30"
                    }`}
                  >
                    {u.is_active ? "Desactiver" : "Reactiver"}
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// -- Tableau Audit --
function AuditTable({ logs }: { logs: AuditLogItem[] }) {
  const actionLabels: Record<string, string> = {
    login: "Connexion",
    logout: "Deconnexion",
    admin_update_user: "Modification utilisateur",
    admin_deactivate_user: "Desactivation utilisateur",
    admin_update_org: "Modification organisation",
    rgpd_delete_all_data: "Suppression RGPD",
    chat: "Message chat",
  };

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-slate-700 text-left text-[var(--color-muted)]">
            <th className="pb-2 pr-4">Date</th>
            <th className="pb-2 pr-4">Utilisateur</th>
            <th className="pb-2 pr-4">Action</th>
            <th className="pb-2 pr-4">Ressource</th>
            <th className="pb-2">IP</th>
          </tr>
        </thead>
        <tbody>
          {logs.map((log) => (
            <tr
              key={log.id}
              className="border-b border-slate-800 hover:bg-slate-800/20"
            >
              <td className="py-2 pr-4 text-[var(--color-muted)] text-xs">
                {new Date(log.timestamp).toLocaleString("fr-FR")}
              </td>
              <td className="py-2 pr-4 text-[var(--color-text)]">
                {log.user_email || "-"}
              </td>
              <td className="py-2 pr-4">
                <span className="text-xs px-2 py-0.5 rounded bg-slate-800 text-[var(--color-cyan)]">
                  {actionLabels[log.action] || log.action}
                </span>
              </td>
              <td className="py-2 pr-4 text-[var(--color-muted)] text-xs">
                {log.resource || "-"}
              </td>
              <td className="py-2 text-[var(--color-muted)] text-xs">
                {log.ip_address || "-"}
              </td>
            </tr>
          ))}
          {logs.length === 0 && (
            <tr>
              <td
                colSpan={5}
                className="py-4 text-center text-[var(--color-muted)]"
              >
                Aucune entree dans le journal
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

// -- Dashboard principal --
export default function AdminDashboard() {
  const { user } = useAuthStore();
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [users, setUsers] = useState<UserItem[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditLogItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"overview" | "users" | "audit">(
    "overview"
  );

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const [statsData, usersData, auditData] = await Promise.all([
        fetchAdminStats(),
        fetchUsers(),
        fetchAuditLogs({ page_size: 20 }),
      ]);
      setStats(statsData);
      setUsers(usersData);
      setAuditLogs(auditData.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erreur de chargement");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleRoleChange = async (userId: string, role: string) => {
    try {
      const updated = await updateUser(userId, { role });
      setUsers((prev) =>
        prev.map((u) => (u.id === updated.id ? updated : u))
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erreur de mise a jour");
    }
  };

  const handleToggleActive = async (userId: string, active: boolean) => {
    try {
      const updated = await updateUser(userId, { is_active: active });
      setUsers((prev) =>
        prev.map((u) => (u.id === updated.id ? updated : u))
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erreur de mise a jour");
    }
  };

  return (
    <div className="min-h-screen flex flex-col">
      <NavBar />

      <main className="flex-1 p-6 max-w-7xl mx-auto w-full">
        {/* Onglets */}
        <div className="flex gap-1 mb-6 border-b border-slate-800">
          {(
            [
              { key: "overview", label: "Vue d'ensemble" },
              { key: "users", label: "Utilisateurs" },
              { key: "audit", label: "Journal d'audit" },
            ] as const
          ).map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                activeTab === tab.key
                  ? "border-[var(--color-cyan)] text-[var(--color-cyan)]"
                  : "border-transparent text-[var(--color-muted)] hover:text-[var(--color-text)]"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Erreur */}
        {error && (
          <div className="mb-4 p-3 bg-red-900/30 border border-red-700 rounded-lg text-red-400 text-sm">
            {error}
            <button
              onClick={() => setError(null)}
              className="ml-2 underline"
            >
              Fermer
            </button>
          </div>
        )}

        {/* Chargement */}
        {loading && (
          <div className="flex items-center justify-center py-12">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[var(--color-cyan)]" />
            <span className="ml-3 text-[var(--color-muted)]">
              Chargement...
            </span>
          </div>
        )}

        {/* Vue d'ensemble */}
        {!loading && activeTab === "overview" && stats && (
          <>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4 mb-8">
              <KpiCard
                label="Utilisateurs actifs"
                value={stats.active_users}
                color="var(--color-cyan)"
              />
              <KpiCard
                label="Total utilisateurs"
                value={stats.total_users}
                color="var(--color-primary)"
              />
              <KpiCard
                label="Conversations"
                value={stats.total_conversations}
                color="var(--color-magenta)"
              />
              <KpiCard
                label="Messages aujourd'hui"
                value={stats.messages_today}
                color="#10B981"
              />
              <KpiCard
                label="Contacts"
                value={stats.total_contacts}
                color="#8B5CF6"
              />
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Derniers utilisateurs */}
              <div className="bg-slate-800/20 border border-slate-700 rounded-xl p-4">
                <h3 className="text-sm font-semibold text-[var(--color-text)] mb-3">
                  Utilisateurs recents
                </h3>
                <div className="space-y-2">
                  {users.slice(0, 5).map((u) => (
                    <div
                      key={u.id}
                      className="flex items-center justify-between text-sm"
                    >
                      <div>
                        <span className="text-[var(--color-text)]">
                          {u.name}
                        </span>
                        <span className="text-[var(--color-muted)] ml-2">
                          {u.email}
                        </span>
                      </div>
                      <span
                        className={`text-xs px-2 py-0.5 rounded ${
                          u.is_active
                            ? "bg-emerald-900/40 text-emerald-400"
                            : "bg-red-900/40 text-red-400"
                        }`}
                      >
                        {u.role}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Derniers audit logs */}
              <div className="bg-slate-800/20 border border-slate-700 rounded-xl p-4">
                <h3 className="text-sm font-semibold text-[var(--color-text)] mb-3">
                  Activite recente
                </h3>
                <div className="space-y-2">
                  {auditLogs.slice(0, 5).map((log) => (
                    <div
                      key={log.id}
                      className="flex items-center justify-between text-sm"
                    >
                      <div>
                        <span className="text-[var(--color-cyan)] text-xs font-mono">
                          {log.action}
                        </span>
                        <span className="text-[var(--color-muted)] ml-2">
                          {log.user_email}
                        </span>
                      </div>
                      <span className="text-[var(--color-muted)] text-xs">
                        {new Date(log.timestamp).toLocaleString("fr-FR")}
                      </span>
                    </div>
                  ))}
                  {auditLogs.length === 0 && (
                    <p className="text-[var(--color-muted)] text-xs">
                      Aucune activite recente
                    </p>
                  )}
                </div>
              </div>
            </div>
          </>
        )}

        {/* Onglet utilisateurs */}
        {!loading && activeTab === "users" && (
          <div className="bg-slate-800/20 border border-slate-700 rounded-xl p-4">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold text-[var(--color-text)]">
                Utilisateurs de l'organisation ({users.length})
              </h3>
              <button
                onClick={loadData}
                className="text-xs text-[var(--color-primary)] hover:underline"
              >
                Actualiser
              </button>
            </div>
            <UsersTable
              users={users}
              currentUserId={user?.id || ""}
              onRoleChange={handleRoleChange}
              onToggleActive={handleToggleActive}
            />
          </div>
        )}

        {/* Onglet audit */}
        {!loading && activeTab === "audit" && (
          <div className="bg-slate-800/20 border border-slate-700 rounded-xl p-4">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold text-[var(--color-text)]">
                Journal d'audit
              </h3>
              <button
                onClick={loadData}
                className="text-xs text-[var(--color-primary)] hover:underline"
              >
                Actualiser
              </button>
            </div>
            <AuditTable logs={auditLogs} />
          </div>
        )}
      </main>
    </div>
  );
}
