import { useState } from "react";
import { useAuthStore } from "../stores/authStore";
import { ShieldCheck } from "lucide-react";
import Spinner from "./ui/Spinner";

const CHARTER_SECTIONS = [
  {
    title: "1. Vérification",
    text: "Toujours vérifier les réponses de l'IA avant de les utiliser dans un contexte professionnel. L'IA peut produire des informations inexactes.",
  },
  {
    title: "2. Confidentialité",
    text: "Ne pas saisir de données personnelles sensibles (numéros de sécurité sociale, mots de passe, données médicales) dans les conversations.",
  },
  {
    title: "3. Responsabilité",
    text: "Vous restez responsable des décisions prises sur la base des suggestions de l'IA. L'IA est un outil d'aide, pas un décideur.",
  },
  {
    title: "4. Éthique",
    text: "Ne pas utiliser l'IA pour produire du contenu discriminatoire, trompeur ou contraire aux valeurs de votre organisation.",
  },
  {
    title: "5. Transparence",
    text: "Signaler à vos collègues et administrés lorsqu'un contenu a été produit avec l'aide de l'IA.",
  },
  {
    title: "6. Protection des données",
    text: "Les conversations sont stockées sur les serveurs de votre organisation. Elles peuvent être auditées par l'administrateur.",
  },
];

export default function CharterModal() {
  const { acceptCharter } = useAuthStore();
  const [checked, setChecked] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleAccept = async () => {
    setIsSubmitting(true);
    setError(null);
    try {
      await acceptCharter();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Une erreur est survenue. Veuillez réessayer."
      );
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div
        className="w-full max-w-2xl mx-4 rounded-2xl border border-white/10 shadow-2xl"
        style={{ backgroundColor: "var(--color-bg)" }}
      >
        {/* Header */}
        <div className="flex items-center gap-3 px-8 pt-8 pb-4">
          <ShieldCheck
            className="h-7 w-7 flex-shrink-0"
            style={{ color: "var(--color-cyan)" }}
          />
          <h2
            className="text-xl font-semibold"
            style={{ color: "var(--color-text)" }}
          >
            Charte d'utilisation de l'Intelligence Artificielle
          </h2>
        </div>

        {/* Intro */}
        <p
          className="px-8 pb-4 text-sm"
          style={{ color: "var(--color-muted)" }}
        >
          En utilisant Thérèse, vous vous engagez à :
        </p>

        {/* Charter sections */}
        <div
          className="mx-8 mb-6 max-h-[50vh] overflow-y-auto rounded-lg border border-white/5 p-5 space-y-4"
          style={{ backgroundColor: "rgba(255,255,255,0.03)" }}
        >
          {CHARTER_SECTIONS.map((section) => (
            <div key={section.title}>
              <h3
                className="text-sm font-semibold mb-1"
                style={{ color: "var(--color-text)" }}
              >
                {section.title}
              </h3>
              <p
                className="text-sm leading-relaxed"
                style={{ color: "var(--color-muted)" }}
              >
                {section.text}
              </p>
            </div>
          ))}
        </div>

        {/* Checkbox + button */}
        <div className="px-8 pb-8 space-y-4">
          <label className="flex items-start gap-3 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={checked}
              onChange={(e) => setChecked(e.target.checked)}
              className="mt-0.5 h-4 w-4 rounded border-white/20 accent-[var(--color-cyan)]"
            />
            <span
              className="text-sm leading-snug"
              style={{ color: "var(--color-text)" }}
            >
              J'ai lu et j'accepte la charte d'utilisation de l'IA
            </span>
          </label>

          {error && (
            <p className="text-sm text-red-400">{error}</p>
          )}

          <button
            onClick={handleAccept}
            disabled={!checked || isSubmitting}
            className="w-full py-2.5 rounded-lg text-sm font-medium transition-all duration-200 disabled:opacity-40 disabled:cursor-not-allowed"
            style={{
              backgroundColor: checked ? "var(--color-primary)" : "transparent",
              color: checked ? "#fff" : "var(--color-muted)",
              border: checked ? "none" : "1px solid rgba(255,255,255,0.1)",
            }}
          >
            {isSubmitting ? (
              <span className="flex items-center justify-center gap-2">
                <Spinner size="sm" />
                Validation en cours...
              </span>
            ) : (
              "Accepter"
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
