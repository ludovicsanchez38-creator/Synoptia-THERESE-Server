import { useEffect, useState, useCallback } from "react";
import NavBar from "../components/NavBar";
import {
  fetchContacts,
  createContact,
  fetchPipelineStats,
  updateContactStage,
  fetchActivities,
  createActivity,
  type Contact,
  type PipelineStats,
} from "../services/api/crmService";

type CrmTab = "contacts" | "pipeline" | "activities";

const stageLabels: Record<string, string> = {
  lead: "Nouveau",
  contact: "Identifié",
  prospect: "En cours",
  negotiation: "En discussion",
  client: "Actif",
  lost: "Archivé",
};

const stageColors: Record<string, string> = {
  lead: "bg-slate-700 text-slate-300",
  contact: "bg-blue-900/40 text-blue-400",
  prospect: "bg-yellow-900/40 text-yellow-400",
  negotiation: "bg-purple-900/40 text-purple-400",
  client: "bg-emerald-900/40 text-emerald-400",
  lost: "bg-red-900/40 text-red-400",
};

export default function CRMPage() {
  const [activeTab, setActiveTab] = useState<CrmTab>("contacts");
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [pipelineStats, setPipelineStats] = useState<PipelineStats | null>(
    null
  );
  const [activities, setActivities] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Form state pour nouveau contact
  const [showContactForm, setShowContactForm] = useState(false);
  const [contactForm, setContactForm] = useState({
    name: "",
    email: "",
    phone: "",
    organization: "",
  });
  const [submitting, setSubmitting] = useState(false);

  // Form state pour nouvelle activité
  const [showActivityForm, setShowActivityForm] = useState(false);
  const [activityForm, setActivityForm] = useState({
    contact_id: "",
    type: "note",
    description: "",
  });

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const [contactsData, statsData, activitiesData] = await Promise.all([
        fetchContacts().catch(() => []),
        fetchPipelineStats().catch(() => null),
        fetchActivities().catch(() => []),
      ]);
      setContacts(Array.isArray(contactsData) ? contactsData : []);
      setPipelineStats(statsData);
      setActivities(Array.isArray(activitiesData) ? activitiesData : []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erreur de chargement");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    document.title = "Contacts - Thérèse";
    loadData();
  }, [loadData]);

  const handleCreateContact = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!contactForm.name.trim()) return;
    try {
      setSubmitting(true);
      const contact = await createContact({
        name: contactForm.name.trim(),
        email: contactForm.email.trim() || undefined,
        phone: contactForm.phone.trim() || undefined,
        organization: contactForm.organization.trim() || undefined,
      });
      setContacts((prev) => [contact, ...prev]);
      setContactForm({ name: "", email: "", phone: "", organization: "" });
      setShowContactForm(false);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Erreur de cr\u00e9ation"
      );
    } finally {
      setSubmitting(false);
    }
  };

  const handleStageChange = async (id: string, stage: string) => {
    try {
      const updated = await updateContactStage(id, stage);
      setContacts((prev) =>
        prev.map((c) => (c.id === id ? updated : c))
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erreur de mise \u00e0 jour");
    }
  };

  const handleCreateActivity = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activityForm.contact_id || !activityForm.description.trim()) return;
    try {
      setSubmitting(true);
      const activity = await createActivity({
        contact_id: activityForm.contact_id,
        type: activityForm.type,
        description: activityForm.description.trim(),
      });
      setActivities((prev) => [activity, ...prev]);
      setActivityForm({ contact_id: "", type: "note", description: "" });
      setShowActivityForm(false);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Erreur de cr\u00e9ation"
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col">
      <NavBar />

      <main className="flex-1 p-4 md:p-6 max-w-6xl mx-auto w-full">
        {/* Titre */}
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-xl font-bold text-[var(--color-text)]">Contacts</h2>
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

        {/* Onglets */}
        <div className="flex gap-1 mb-6 border-b border-slate-800">
          {(
            [
              { key: "contacts" as CrmTab, label: "Contacts" },
              { key: "pipeline" as CrmTab, label: "Vue d'ensemble" },
              { key: "activities" as CrmTab, label: "Activit\u00e9s" },
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

        {/* Chargement */}
        {loading && (
          <div className="flex items-center justify-center py-12">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[var(--color-cyan)]" />
            <span className="ml-3 text-[var(--color-muted)]">
              Chargement...
            </span>
          </div>
        )}

        {/* === TAB CONTACTS === */}
        {!loading && activeTab === "contacts" && (
          <div>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold text-[var(--color-text)]">
                Contacts ({contacts.length})
              </h3>
              <button
                onClick={() => setShowContactForm(!showContactForm)}
                className="px-4 py-2 text-sm font-medium rounded-lg bg-[var(--color-primary)] text-white hover:opacity-90 transition-opacity"
              >
                {showContactForm ? "Annuler" : "Nouveau contact"}
              </button>
            </div>

            {/* Formulaire nouveau contact */}
            {showContactForm && (
              <form
                onSubmit={handleCreateContact}
                className="mb-6 p-4 bg-slate-800/30 border border-slate-700 rounded-xl space-y-3"
              >
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div>
                    <label className="block text-sm text-[var(--color-muted)] mb-1">
                      Nom *
                    </label>
                    <input
                      type="text"
                      value={contactForm.name}
                      onChange={(e) =>
                        setContactForm({
                          ...contactForm,
                          name: e.target.value,
                        })
                      }
                      className="w-full px-3 py-2 bg-slate-800 border border-slate-600 rounded-lg text-[var(--color-text)] text-sm focus:outline-none focus:border-[var(--color-cyan)]"
                      placeholder="Nom du contact..."
                      autoFocus
                    />
                  </div>
                  <div>
                    <label className="block text-sm text-[var(--color-muted)] mb-1">
                      Email
                    </label>
                    <input
                      type="email"
                      value={contactForm.email}
                      onChange={(e) =>
                        setContactForm({
                          ...contactForm,
                          email: e.target.value,
                        })
                      }
                      className="w-full px-3 py-2 bg-slate-800 border border-slate-600 rounded-lg text-[var(--color-text)] text-sm focus:outline-none focus:border-[var(--color-cyan)]"
                      placeholder="email@exemple.fr"
                    />
                  </div>
                  <div>
                    <label className="block text-sm text-[var(--color-muted)] mb-1">
                      T&eacute;l&eacute;phone
                    </label>
                    <input
                      type="tel"
                      value={contactForm.phone}
                      onChange={(e) =>
                        setContactForm({
                          ...contactForm,
                          phone: e.target.value,
                        })
                      }
                      className="w-full px-3 py-2 bg-slate-800 border border-slate-600 rounded-lg text-[var(--color-text)] text-sm focus:outline-none focus:border-[var(--color-cyan)]"
                      placeholder="06 12 34 56 78"
                    />
                  </div>
                  <div>
                    <label className="block text-sm text-[var(--color-muted)] mb-1">
                      Organisation
                    </label>
                    <input
                      type="text"
                      value={contactForm.organization}
                      onChange={(e) =>
                        setContactForm({
                          ...contactForm,
                          organization: e.target.value,
                        })
                      }
                      className="w-full px-3 py-2 bg-slate-800 border border-slate-600 rounded-lg text-[var(--color-text)] text-sm focus:outline-none focus:border-[var(--color-cyan)]"
                      placeholder="Entreprise / Mairie..."
                    />
                  </div>
                </div>
                <div className="flex justify-end">
                  <button
                    type="submit"
                    disabled={submitting || !contactForm.name.trim()}
                    className="px-4 py-2 text-sm font-medium rounded-lg bg-[var(--color-cyan)] text-[var(--color-bg)] hover:opacity-90 transition-opacity disabled:opacity-50"
                  >
                    {submitting ? "Cr\u00e9ation..." : "Cr\u00e9er le contact"}
                  </button>
                </div>
              </form>
            )}

            {/* Tableau contacts */}
            {contacts.length === 0 ? (
              <div className="text-center py-12 text-[var(--color-muted)]">
                Aucun contact pour le moment
              </div>
            ) : (
              <div className="bg-slate-800/20 border border-slate-700 rounded-xl overflow-hidden">
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-slate-700 text-left text-[var(--color-muted)]">
                        <th className="px-4 py-3">Nom</th>
                        <th className="px-4 py-3">Email</th>
                        <th className="px-4 py-3">T&eacute;l&eacute;phone</th>
                        <th className="px-4 py-3">Étape</th>
                        <th className="px-4 py-3">Priorité</th>
                        <th className="px-4 py-3">Cr&eacute;&eacute; le</th>
                      </tr>
                    </thead>
                    <tbody>
                      {contacts.map((contact) => (
                        <tr
                          key={contact.id}
                          className="border-b border-slate-800 hover:bg-slate-800/20"
                        >
                          <td className="px-4 py-3 text-[var(--color-text)]">
                            {[contact.first_name, contact.last_name]
                              .filter(Boolean)
                              .join(" ") || "-"}
                            {contact.company && (
                              <span className="block text-xs text-[var(--color-muted)]">
                                {contact.company}
                              </span>
                            )}
                          </td>
                          <td className="px-4 py-3 text-[var(--color-muted)]">
                            {contact.email || "-"}
                          </td>
                          <td className="px-4 py-3 text-[var(--color-muted)]">
                            {contact.phone || "-"}
                          </td>
                          <td className="px-4 py-3">
                            <select
                              value={contact.stage}
                              onChange={(e) =>
                                handleStageChange(contact.id, e.target.value)
                              }
                              className="bg-slate-800 border border-slate-600 rounded px-2 py-1 text-xs text-[var(--color-text)]"
                            >
                              {Object.entries(stageLabels).map(
                                ([value, label]) => (
                                  <option key={value} value={value}>
                                    {label}
                                  </option>
                                )
                              )}
                            </select>
                          </td>
                          <td className="px-4 py-3">
                            <span className="text-xs font-mono text-[var(--color-cyan)]">
                              {contact.score}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-[var(--color-muted)] text-xs">
                            {new Date(contact.created_at).toLocaleDateString(
                              "fr-FR"
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}

        {/* === TAB PIPELINE === */}
        {!loading && activeTab === "pipeline" && (
          <div>
            <h3 className="text-sm font-semibold text-[var(--color-text)] mb-4">
              Vue d'ensemble
            </h3>

            {pipelineStats ? (
              <>
                <div className="mb-6 p-4 bg-slate-800/30 border border-slate-700 rounded-xl">
                  <div className="text-sm text-[var(--color-muted)]">
                    Total contacts
                  </div>
                  <div className="text-3xl font-bold text-[var(--color-cyan)] mt-1">
                    {pipelineStats.total_contacts}
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                  {Object.entries(pipelineStats.stages).map(
                    ([stage, stageData]) => (
                      <div
                        key={stage}
                        className="p-4 bg-slate-800/20 border border-slate-700 rounded-xl"
                      >
                        <div className="flex items-center justify-between mb-2">
                          <span
                            className={`text-xs px-2 py-0.5 rounded ${
                              stageColors[stage] ||
                              "bg-slate-700 text-slate-300"
                            }`}
                          >
                            {stageLabels[stage] || stage}
                          </span>
                          <span className="text-lg font-bold text-[var(--color-text)]">
                            {typeof stageData === "object" ? (stageData as any).count : stageData}
                          </span>
                        </div>
                        <div className="w-full bg-slate-700 rounded-full h-2">
                          <div
                            className="bg-[var(--color-cyan)] h-2 rounded-full transition-all"
                            style={{
                              width: `${
                                pipelineStats.total_contacts > 0
                                  ? (((typeof stageData === "object" ? (stageData as any).count : stageData)) / pipelineStats.total_contacts) *
                                    100
                                  : 0
                              }%`,
                            }}
                          />
                        </div>
                      </div>
                    )
                  )}
                </div>
              </>
            ) : (
              <div className="text-center py-12 text-[var(--color-muted)]">
                Aucune donn&eacute;e de pipeline disponible
              </div>
            )}
          </div>
        )}

        {/* === TAB ACTIVITÉS === */}
        {!loading && activeTab === "activities" && (
          <div>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold text-[var(--color-text)]">
                Activit&eacute;s r&eacute;centes
              </h3>
              <button
                onClick={() => setShowActivityForm(!showActivityForm)}
                className="px-4 py-2 text-sm font-medium rounded-lg bg-[var(--color-primary)] text-white hover:opacity-90 transition-opacity"
              >
                {showActivityForm ? "Annuler" : "Nouvelle activit\u00e9"}
              </button>
            </div>

            {/* Formulaire nouvelle activité */}
            {showActivityForm && (
              <form
                onSubmit={handleCreateActivity}
                className="mb-6 p-4 bg-slate-800/30 border border-slate-700 rounded-xl space-y-3"
              >
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div>
                    <label className="block text-sm text-[var(--color-muted)] mb-1">
                      Contact *
                    </label>
                    <select
                      value={activityForm.contact_id}
                      onChange={(e) =>
                        setActivityForm({
                          ...activityForm,
                          contact_id: e.target.value,
                        })
                      }
                      className="w-full bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-sm text-[var(--color-text)]"
                    >
                      <option value="">S&eacute;lectionner un contact</option>
                      {contacts.map((c) => (
                        <option key={c.id} value={c.id}>
                          {[c.first_name, c.last_name]
                            .filter(Boolean)
                            .join(" ") || c.email || c.id}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm text-[var(--color-muted)] mb-1">
                      Type
                    </label>
                    <select
                      value={activityForm.type}
                      onChange={(e) =>
                        setActivityForm({
                          ...activityForm,
                          type: e.target.value,
                        })
                      }
                      className="w-full bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-sm text-[var(--color-text)]"
                    >
                      <option value="note">Note</option>
                      <option value="call">Appel</option>
                      <option value="email">Email</option>
                      <option value="meeting">R&eacute;union</option>
                      <option value="task">T&acirc;che</option>
                    </select>
                  </div>
                </div>
                <div>
                  <label className="block text-sm text-[var(--color-muted)] mb-1">
                    Description *
                  </label>
                  <textarea
                    value={activityForm.description}
                    onChange={(e) =>
                      setActivityForm({
                        ...activityForm,
                        description: e.target.value,
                      })
                    }
                    className="w-full px-3 py-2 bg-slate-800 border border-slate-600 rounded-lg text-[var(--color-text)] text-sm focus:outline-none focus:border-[var(--color-cyan)] resize-none"
                    rows={2}
                    placeholder="D&eacute;crivez l'activit&eacute;..."
                  />
                </div>
                <div className="flex justify-end">
                  <button
                    type="submit"
                    disabled={
                      submitting ||
                      !activityForm.contact_id ||
                      !activityForm.description.trim()
                    }
                    className="px-4 py-2 text-sm font-medium rounded-lg bg-[var(--color-cyan)] text-[var(--color-bg)] hover:opacity-90 transition-opacity disabled:opacity-50"
                  >
                    {submitting ? "Cr\u00e9ation..." : "Ajouter"}
                  </button>
                </div>
              </form>
            )}

            {/* Timeline des activités */}
            {activities.length === 0 ? (
              <div className="text-center py-12 text-[var(--color-muted)]">
                Aucune activit&eacute; enregistr&eacute;e
              </div>
            ) : (
              <div className="space-y-3">
                {activities.map((activity, index) => (
                  <div
                    key={activity.id || index}
                    className="flex gap-3 p-4 bg-slate-800/20 border border-slate-700 rounded-xl"
                  >
                    {/* Indicateur timeline */}
                    <div className="flex flex-col items-center shrink-0">
                      <div className="w-3 h-3 rounded-full bg-[var(--color-cyan)]" />
                      {index < activities.length - 1 && (
                        <div className="w-0.5 flex-1 bg-slate-700 mt-1" />
                      )}
                    </div>
                    {/* Contenu */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-xs px-2 py-0.5 rounded bg-slate-700 text-[var(--color-cyan)]">
                          {activity.type || "note"}
                        </span>
                        {activity.contact_name && (
                          <span className="text-xs text-[var(--color-muted)]">
                            {activity.contact_name}
                          </span>
                        )}
                        {activity.created_at && (
                          <span className="text-xs text-[var(--color-muted)] ml-auto">
                            {new Date(
                              activity.created_at
                            ).toLocaleString("fr-FR")}
                          </span>
                        )}
                      </div>
                      <p className="text-sm text-[var(--color-text)] mt-1">
                        {activity.description}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
