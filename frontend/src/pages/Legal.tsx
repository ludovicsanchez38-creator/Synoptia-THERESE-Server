import { Link } from "react-router-dom";

export default function LegalPage() {
  return (
    <div className="min-h-screen bg-[var(--color-bg)] text-[var(--color-text)] p-8 max-w-3xl mx-auto">
      <Link to="/login" className="text-[var(--color-primary)] hover:underline text-sm">
        &larr; Retour
      </Link>

      <h1 className="text-2xl font-bold mt-6 mb-8">Mentions légales</h1>

      <section className="mb-8">
        <h2 className="text-lg font-semibold mb-2">Éditeur</h2>
        <p>
          Ce service est édité par l'organisation propriétaire de l'instance Thérèse Server.<br />
          Pour toute question, contactez l'administrateur de votre instance.
        </p>
      </section>

      <section className="mb-8">
        <h2 className="text-lg font-semibold mb-2">Hébergement</h2>
        <p>
          Cette application est hébergée sur l'infrastructure choisie par l'organisation (on-premise ou cloud privé).
          Les données sont stockées sur les serveurs de l'organisation et ne sont transmises à aucun tiers,
          à l'exception des fournisseurs de modèles IA configurés (Anthropic, OpenAI, Mistral, Google, Ollama).
        </p>
      </section>

      <section className="mb-8">
        <h2 className="text-lg font-semibold mb-2">Données personnelles et RGPD</h2>
        <ul className="list-disc ml-6 space-y-2">
          <li>Les données collectées sont : nom, email, messages de conversation, fichiers uploadés.</li>
          <li>Finalité : fournir un assistant IA aux utilisateurs de l'organisation.</li>
          <li>Base légale : intérêt légitime de l'organisation (ou consentement si applicable).</li>
          <li>Durée de conservation : configurable par l'administrateur (par défaut 3 ans).</li>
          <li>Droits : accès, rectification, suppression, portabilité - via le menu "Mes données" ou l'administrateur.</li>
          <li>DPO : contactez l'administrateur de votre instance pour exercer vos droits.</li>
        </ul>
      </section>

      <section className="mb-8">
        <h2 className="text-lg font-semibold mb-2">Politique de confidentialité</h2>
        <ul className="list-disc ml-6 space-y-2">
          <li>Les clés API et tokens sont chiffrés au repos (Fernet). Les conversations sont protégées par l'isolation multi-tenant et le contrôle d'accès.</li>
          <li>Les échanges avec les fournisseurs LLM utilisent des connexions HTTPS chiffrées.</li>
          <li>Aucune donnée n'est utilisée pour entraîner des modèles tiers.</li>
          <li>Les logs d'audit enregistrent les actions sensibles (connexion, export, suppression).</li>
          <li>L'accès aux données est isolé par organisation et par utilisateur (multi-tenancy).</li>
        </ul>
      </section>

      <section className="mb-8">
        <h2 className="text-lg font-semibold mb-2">Cookies</h2>
        <p>
          Cette application utilise uniquement un token JWT stocké dans le localStorage du navigateur
          pour l'authentification. Aucun cookie tiers, aucun tracker, aucune publicité.
        </p>
      </section>

      <section className="mb-8">
        <h2 className="text-lg font-semibold mb-2">Logiciel</h2>
        <p>
          Thérèse Server est un logiciel libre distribué sous licence AGPL-3.0.<br />
          Code source : <a href="https://github.com/ludovicsanchez38-creator/Synoptia-THERESE-Server" className="text-[var(--color-primary)] hover:underline" target="_blank" rel="noopener noreferrer">GitHub</a>
        </p>
      </section>
    </div>
  );
}
