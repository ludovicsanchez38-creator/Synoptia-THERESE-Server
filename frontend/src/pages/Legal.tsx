import { useEffect } from "react";

export default function Legal() {
  useEffect(() => {
    document.title = "Mentions légales - Thérèse";
  }, []);

  return (
    <main id="main-content" className="min-h-screen bg-[var(--color-bg)] text-[var(--color-text)] p-6 max-w-4xl mx-auto">
      <a href="/login" className="text-[var(--color-cyan)] hover:underline text-sm mb-6 inline-block">
        ← Retour
      </a>

      <h1 className="text-2xl font-bold mb-8">Mentions légales et politique de confidentialité</h1>

      <section className="mb-8">
        <h2 className="text-xl font-semibold mb-4 text-[var(--color-cyan)]">1. Mentions légales</h2>
        <p className="text-[var(--color-muted)] mb-2">
          Thérèse Server est un logiciel libre distribué sous licence AGPL-3.0.
        </p>
        <p className="text-[var(--color-muted)] mb-2">
          L'hébergement et l'exploitation de cette instance sont sous la responsabilité de l'organisme
          qui a déployé le logiciel. Contactez votre administrateur pour connaître l'identité de l'hébergeur.
        </p>
      </section>

      <section className="mb-8">
        <h2 className="text-xl font-semibold mb-4 text-[var(--color-cyan)]">2. Politique de confidentialité</h2>
        <h3 className="text-lg font-medium mb-2">Données collectées</h3>
        <ul className="list-disc list-inside text-[var(--color-muted)] mb-4 space-y-1">
          <li>Identifiants de connexion (email, mot de passe chiffré)</li>
          <li>Conversations avec l'assistant IA</li>
          <li>Contacts et activités CRM</li>
          <li>Documents indexés (RAG)</li>
          <li>Logs d'audit (actions, horodatage, adresse IP)</li>
        </ul>

        <h3 className="text-lg font-medium mb-2">Finalité du traitement</h3>
        <p className="text-[var(--color-muted)] mb-4">
          Les données sont traitées pour fournir le service d'assistance IA, gérer les contacts professionnels,
          et assurer la traçabilité des actions (audit).
        </p>

        <h3 className="text-lg font-medium mb-2">Durée de conservation</h3>
        <p className="text-[var(--color-muted)] mb-4">
          Les données sont conservées pendant la durée configurée par l'administrateur (par défaut : 3 ans).
          Les logs d'audit sont conservés 90 jours.
        </p>

        <h3 className="text-lg font-medium mb-2">Vos droits (RGPD)</h3>
        <p className="text-[var(--color-muted)] mb-4">
          Conformément au RGPD, vous disposez d'un droit d'accès, de rectification, d'effacement,
          de portabilité et d'opposition. Ces droits sont exercables via les fonctionnalités RGPD intégrées
          à l'application ou en contactant votre administrateur.
        </p>

        <h3 className="text-lg font-medium mb-2">Chiffrement</h3>
        <p className="text-[var(--color-muted)] mb-4">
          Les données sensibles (clés API, profils) sont chiffrées avec l'algorithme Fernet (AES-128-CBC + HMAC).
          Les mots de passe sont hachés avec bcrypt.
        </p>
      </section>

      <section className="mb-8">
        <h2 className="text-xl font-semibold mb-4 text-[var(--color-cyan)]">3. Sous-traitants et fournisseurs IA</h2>
        <p className="text-[var(--color-muted)] mb-4">
          Selon la configuration de l'instance, les messages envoyés à l'assistant IA peuvent être transmis
          aux fournisseurs suivants :
        </p>
        <div className="overflow-x-auto">
          <table className="w-full text-sm text-[var(--color-muted)] border-collapse">
            <thead>
              <tr className="border-b border-slate-700">
                <th className="text-left py-2 pr-4 font-medium text-[var(--color-text)]">Fournisseur</th>
                <th className="text-left py-2 pr-4 font-medium text-[var(--color-text)]">Modèles</th>
                <th className="text-left py-2 font-medium text-[var(--color-text)]">Localisation</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              <tr><td className="py-2 pr-4">Anthropic</td><td className="py-2 pr-4">Claude (Sonnet, Opus, Haiku)</td><td className="py-2">USA</td></tr>
              <tr><td className="py-2 pr-4">OpenAI</td><td className="py-2 pr-4">GPT-4o, GPT-4o-mini</td><td className="py-2">USA</td></tr>
              <tr><td className="py-2 pr-4">Google</td><td className="py-2 pr-4">Gemini (Pro, Flash)</td><td className="py-2">USA / UE</td></tr>
              <tr><td className="py-2 pr-4">Mistral AI</td><td className="py-2 pr-4">Mistral Large, Small</td><td className="py-2">France / UE</td></tr>
              <tr><td className="py-2 pr-4">Ollama (local)</td><td className="py-2 pr-4">Modèles locaux</td><td className="py-2">Sur site</td></tr>
              <tr><td className="py-2 pr-4">Infomaniak</td><td className="py-2 pr-4">LLM Infomaniak</td><td className="py-2">Suisse</td></tr>
            </tbody>
          </table>
        </div>
        <p className="text-[var(--color-muted)] mt-4 text-sm">
          Seuls les fournisseurs configurés par l'administrateur reçoivent des données.
          L'utilisation d'Ollama (local) garantit qu'aucune donnée ne quitte le réseau de l'organisme.
        </p>
      </section>

      <section className="mb-8">
        <h2 className="text-xl font-semibold mb-4 text-[var(--color-cyan)]">4. Contact DPO</h2>
        <p className="text-[var(--color-muted)]">
          Pour toute question relative à la protection des données, contactez le délégué à la protection
          des données (DPO) de votre organisme ou votre administrateur Thérèse.
        </p>
      </section>

      <footer className="text-[var(--color-muted)]/50 text-xs mt-12 pt-4 border-t border-slate-800">
        Thérèse Server - Logiciel libre sous licence AGPL-3.0
      </footer>
    </main>
  );
}
