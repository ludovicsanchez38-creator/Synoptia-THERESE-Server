import { useState, useRef, useEffect, type FormEvent, type KeyboardEvent } from "react";
import { useChatStore } from "../../stores/chatStore";
import TemplateSelector from "./TemplateSelector";

export default function ChatInput() {
  const [content, setContent] = useState("");
  const { send, isSending, currentConversationId } = useChatStore();
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const canSend = content.trim().length > 0 && !isSending && !!currentConversationId;

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height =
        Math.min(textareaRef.current.scrollHeight, 160) + "px";
    }
  }, [content]);

  const handleSubmit = async (e?: FormEvent) => {
    e?.preventDefault();
    if (!canSend) return;
    const msg = content.trim();
    setContent("");
    await send(msg);
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
    // Focus le textarea apres insertion
    setTimeout(() => {
      textareaRef.current?.focus();
    }, 50);
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="p-3 md:p-4 border-t border-slate-800 bg-[var(--color-bg)]"
    >
      <div className="flex items-end gap-2 max-w-4xl mx-auto">
        {/* Bouton modeles de prompts */}
        <TemplateSelector onSelect={handleTemplateSelect} />

        <textarea
          ref={textareaRef}
          value={content}
          onChange={(e) => setContent(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={
            currentConversationId
              ? "\u00c9crivez votre message... (Entr\u00e9e pour envoyer)"
              : "S\u00e9lectionnez une conversation"
          }
          disabled={!currentConversationId}
          rows={1}
          className="flex-1 px-4 py-2.5 bg-slate-800/50 border border-slate-700 rounded-xl focus:outline-none focus:border-[var(--color-primary)] text-[var(--color-text)] text-sm resize-none disabled:opacity-40 placeholder:text-[var(--color-muted)]/50"
        />
        <button
          type="submit"
          disabled={!canSend}
          className="px-5 py-2.5 bg-[var(--color-primary)] hover:bg-[var(--color-primary)]/80 disabled:opacity-30 disabled:cursor-not-allowed rounded-xl font-medium transition-colors text-sm shrink-0"
          title="Envoyer"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M22 2L11 13" />
            <path d="M22 2L15 22L11 13L2 9L22 2Z" />
          </svg>
        </button>
      </div>
    </form>
  );
}
