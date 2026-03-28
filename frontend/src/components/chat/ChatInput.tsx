import { useState, useRef, useEffect, type FormEvent, type KeyboardEvent } from "react";
import { useChatStore } from "../../stores/chatStore";
import { useAuthStore } from "../../stores/authStore";
import TemplateSelector from "./TemplateSelector";
import VoiceRecorder from "./VoiceRecorder";

const MODELS = [
  { id: "claude-sonnet-4-6", name: "Claude Sonnet 4.6", provider: "Anthropic" },
  { id: "claude-opus-4-6", name: "Claude Opus 4.6", provider: "Anthropic" },
  { id: "gpt-5.2", name: "GPT-5.2", provider: "OpenAI" },
  { id: "gemini-3.1-flash-lite-preview", name: "Gemini 3.1 Flash", provider: "Google" },
  { id: "mistral-large-latest", name: "Mistral Large", provider: "Mistral" },
  { id: "grok-4", name: "Grok 4", provider: "xAI" },
  { id: "mistral-nemo", name: "Mistral Nemo (local)", provider: "Ollama" },
];


const AGENTS = [
  { prefix: "@conformite", name: "Vérificateur de conformité", description: "Analyse un document au regard du CGCT" },
];

/** Préfixes @mention reconnus pour les missions agents. */
const MISSION_PREFIXES: { pattern: RegExp; missionType: string }[] = [
  { pattern: /^@conformit[ée]\s+/i, missionType: "conformity" },
];

/**
 * Détecte si le message commence par une @mention de mission.
 * Retourne le type de mission et le texte nettoyé, ou null.
 */
function detectMission(text: string): { missionType: string; inputText: string } | null {
  for (const { pattern, missionType } of MISSION_PREFIXES) {
    if (pattern.test(text)) {
      const inputText = text.replace(pattern, "").trim();
      if (inputText.length > 0) {
        return { missionType, inputText };
      }
    }
  }
  return null;
}

export default function ChatInput() {
  const [content, setContent] = useState("");
  const [selectedModel, setSelectedModel] = useState(MODELS[0].id);
  const [showModels, setShowModels] = useState(false);
  const [showAgents, setShowAgents] = useState(false);
  const agentRef = useRef<HTMLDivElement>(null);
  const { send, isSending, currentConversationId, launchMission } = useChatStore();
  const { user } = useAuthStore();
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const modelRef = useRef<HTMLDivElement>(null);

  const canSend = content.trim().length > 0 && !isSending && !!currentConversationId;
  const currentModel = MODELS.find((m) => m.id === selectedModel) || MODELS[0];

  // Détection live pour afficher un indicateur visuel
  const missionDetected = detectMission(content.trim());

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height =
        Math.min(textareaRef.current.scrollHeight, 160) + "px";
    }
  }, [content]);

  // Fermer le dropdown au clic extérieur
  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (modelRef.current && !modelRef.current.contains(e.target as Node)) {
        setShowModels(false);
      }
      if (agentRef.current && !agentRef.current.contains(e.target as Node)) {
        setShowAgents(false);
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  const handleSubmit = async (e?: FormEvent) => {
    e?.preventDefault();
    if (!canSend) return;
    const msg = content.trim();
    setContent("");

    // Vérifier si c'est une @mention de mission
    const mission = detectMission(msg);
    if (mission) {
      await launchMission(mission.missionType, mission.inputText);
    } else {
      await send(msg, selectedModel);
    }

    textareaRef.current?.focus();
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleTemplateSelect = (prompt: string) => {
    setContent(prompt);
    setTimeout(() => textareaRef.current?.focus(), 50);
  };

  const handleTranscription = (text: string) => {
    setContent((prev) => (prev ? prev + ' ' + text : text));
    setTimeout(() => textareaRef.current?.focus(), 50);
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="p-3 md:p-4 border-t border-slate-800 bg-[var(--color-bg)]"
    >
      {/* Indicateur mission détectée */}
      {missionDetected && (
        <div className="flex items-center gap-2 max-w-4xl mx-auto mb-2 px-3 py-1.5 bg-amber-500/10 border border-amber-500/20 rounded-lg">
          <span className="text-amber-400 text-xs">
            {"🛡️"} Mission <strong>{missionDetected.missionType}</strong> - sera envoyée à l{"'"}agent
          </span>
        </div>
      )}

      {/* Barre de sélection modèle + templates */}
      <div className="flex items-center gap-2 max-w-4xl mx-auto mb-2">
        {/* Sélecteur de modèle LLM (masqué pour les agents) */}
        {user?.role !== "agent" && (
        <div ref={modelRef} className="relative">
          <button
            type="button"
            onClick={() => setShowModels(!showModels)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-slate-800/70 border border-slate-700 rounded-lg hover:border-[var(--color-primary)]/50 transition-colors"
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 2a4 4 0 0 0-4 4v2H6a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V10a2 2 0 0 0-2-2h-2V6a4 4 0 0 0-4-4Z"/>
              <circle cx="12" cy="15" r="2"/>
            </svg>
            <span className="text-[var(--color-cyan)]">{currentModel.name}</span>
            <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="m6 9 6 6 6-6"/></svg>
          </button>

          {showModels && (
            <div className="absolute bottom-full left-0 mb-1 w-64 bg-slate-900 border border-slate-700 rounded-xl shadow-xl z-50 overflow-hidden">
              <div className="p-2 border-b border-slate-800 text-xs text-[var(--color-muted)]">
                Choisir un modèle
              </div>
              {MODELS.map((model) => (
                <button
                  key={model.id}
                  type="button"
                  onClick={() => {
                    setSelectedModel(model.id);
                    setShowModels(false);
                  }}
                  className={`w-full px-3 py-2 text-left text-sm hover:bg-slate-800 transition-colors flex items-center justify-between ${
                    selectedModel === model.id ? "bg-slate-800/50 text-[var(--color-cyan)]" : "text-[var(--color-text)]"
                  }`}
                >
                  <span>{model.name}</span>
                  <span className="text-xs text-[var(--color-muted)]">{model.provider}</span>
                </button>
              ))}
            </div>
          )}
        </div>
        )}

        {/* Sélecteur de templates */}
        <TemplateSelector onSelect={handleTemplateSelect} />

        {/* Selecteur d agents */}
        <div ref={agentRef} className="relative">
          <button type="button" onClick={() => setShowAgents(!showAgents)} className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-slate-800/70 border border-slate-700 rounded-lg hover:border-emerald-500/50 transition-colors">
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10"/><path d="m9 12 2 2 4-4"/></svg>
            <span className="text-emerald-400">Agents</span>
            <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="m6 9 6 6 6-6"/></svg>
          </button>
          {showAgents && (
            <div className="absolute bottom-full left-0 mb-1 w-72 bg-slate-900 border border-slate-700 rounded-xl shadow-xl z-50 overflow-hidden">
              <div className="p-2 border-b border-slate-800 text-xs text-[var(--color-muted)]">Agents autonomes</div>
              {AGENTS.map((agent) => (
                <button key={agent.prefix} type="button" onClick={() => { setContent(agent.prefix + " "); setShowAgents(false); setTimeout(() => textareaRef.current?.focus(), 50); }} className="w-full px-3 py-2.5 text-left hover:bg-slate-800 transition-colors flex items-start gap-2">
                  <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--color-cyan)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="mt-0.5 shrink-0"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10"/><path d="m9 12 2 2 4-4"/></svg>
                  <div><div className="text-sm text-[var(--color-text)]">{agent.name}</div><div className="text-xs text-[var(--color-muted)]">{agent.description}</div></div>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Input + bouton envoyer */}
      <div className="flex items-end gap-2 max-w-4xl mx-auto">
        <textarea
          ref={textareaRef}
          value={content}
          onChange={(e) => setContent(e.target.value)}
          onKeyDown={handleKeyDown}
          data-testid="chat-message-input"
          placeholder={
            currentConversationId
              ? "Écrivez votre message... (@conformité pour lancer un agent)"
              : "Sélectionnez une conversation"
          }
          disabled={!currentConversationId}
          rows={1}
          className="flex-1 px-4 py-2.5 bg-slate-800/50 border border-slate-700 rounded-xl focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-primary)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--color-bg)] text-[var(--color-text)] text-sm resize-none disabled:opacity-40 placeholder:text-[var(--color-muted)]/50"
        />
        <VoiceRecorder
          onTranscription={handleTranscription}
          disabled={!currentConversationId}
        />
        <button
          type="submit"
          disabled={!canSend}
          className="px-5 py-2.5 bg-[var(--color-primary)] hover:bg-[var(--color-primary)]/80 disabled:opacity-30 disabled:cursor-not-allowed rounded-xl font-medium transition-colors text-sm shrink-0"
          title="Envoyer"
          aria-label="Envoyer le message"
          data-testid="chat-send-btn"
        >
          <svg aria-hidden="true" xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M22 2L11 13" />
            <path d="M22 2L15 22L11 13L2 9L22 2Z" />
          </svg>
        </button>
      </div>
    </form>
  );
}
