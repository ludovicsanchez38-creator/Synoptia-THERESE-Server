import { create } from "zustand";
import {
  fetchConversations,
  createConversation,
  deleteConversation,
  fetchMessages,
} from "../services/api/chatService";
import type { Conversation, Message } from "../services/api/chatService";
import { getToken } from "../services/api/authService";

interface ChatState {
  conversations: Conversation[];
  currentConversationId: string | null;
  messages: Message[];
  isLoadingConversations: boolean;
  isLoadingMessages: boolean;
  isSending: boolean;
  error: string | null;

  loadConversations: () => Promise<void>;
  selectConversation: (id: string) => Promise<void>;
  newConversation: (title?: string) => Promise<void>;
  removeConversation: (id: string) => Promise<void>;
  send: (content: string) => Promise<void>;
  clearError: () => void;
  reset: () => void;
}

export const useChatStore = create<ChatState>((set, get) => ({
  conversations: [],
  currentConversationId: null,
  messages: [],
  isLoadingConversations: false,
  isLoadingMessages: false,
  isSending: false,
  error: null,

  loadConversations: async () => {
    set({ isLoadingConversations: true, error: null });
    try {
      const conversations = await fetchConversations();
      set({ conversations, isLoadingConversations: false });
    } catch (err) {
      set({
        error: err instanceof Error ? err.message : "Erreur de chargement",
        isLoadingConversations: false,
      });
    }
  },

  selectConversation: async (id: string) => {
    set({ currentConversationId: id, isLoadingMessages: true, error: null });
    try {
      const messages = await fetchMessages(id);
      set({ messages, isLoadingMessages: false });
    } catch (err) {
      set({
        error: err instanceof Error ? err.message : "Erreur de chargement",
        isLoadingMessages: false,
      });
    }
  },

  newConversation: async (title?: string) => {
    set({ error: null });
    try {
      const conversation = await createConversation(
        title || "Nouvelle conversation"
      );
      const { conversations } = get();
      set({
        conversations: [conversation, ...conversations],
        currentConversationId: conversation.id,
        messages: [],
      });
    } catch (err) {
      set({
        error: err instanceof Error ? err.message : "Erreur de création",
      });
    }
  },

  removeConversation: async (id: string) => {
    set({ error: null });
    try {
      await deleteConversation(id);
      const { conversations, currentConversationId } = get();
      const updated = conversations.filter((c) => c.id !== id);
      set({
        conversations: updated,
        ...(currentConversationId === id
          ? { currentConversationId: null, messages: [] }
          : {}),
      });
    } catch (err) {
      set({
        error: err instanceof Error ? err.message : "Erreur de suppression",
      });
    }
  },

  send: async (content: string) => {
    const { currentConversationId } = get();
    if (!currentConversationId) return;

    set({ isSending: true, error: null });

    // Ajouter le message utilisateur localement (optimistic)
    const tempUserMsg: Message = {
      id: `temp-user-${Date.now()}`,
      role: "user",
      content,
      created_at: new Date().toISOString(),
    };
    // Ajouter un message assistant vide pour le streaming
    const tempAssistantMsg: Message = {
      id: `temp-assistant-${Date.now()}`,
      role: "assistant",
      content: "",
      created_at: new Date().toISOString(),
    };
    set((state) => ({
      messages: [...state.messages, tempUserMsg, tempAssistantMsg],
    }));

    try {
      const token = getToken();
      const response = await fetch("/api/chat/send", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          conversation_id: currentConversationId,
          message: content,
        }),
      });

      if (!response.ok) {
        throw new Error("Erreur lors de l'envoi du message");
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error("Streaming non supporté");

      const decoder = new TextDecoder();
      let assistantContent = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const text = decoder.decode(value, { stream: true });
        const lines = text.split("\n");

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const jsonStr = line.slice(6).trim();
          if (!jsonStr) continue;

          try {
            const event = JSON.parse(jsonStr);
            if (event.type === "chunk") {
              assistantContent += event.content;
              // Mettre à jour le message assistant en temps réel
              set((state) => ({
                messages: state.messages.map((m) =>
                  m.id === tempAssistantMsg.id
                    ? { ...m, content: assistantContent }
                    : m
                ),
              }));
            } else if (event.type === "error") {
              set({ error: event.content });
            }
          } catch {
            // Ignorer les lignes SSE malformées
          }
        }
      }

      // Recharger les messages pour avoir les vrais IDs
      const messages = await fetchMessages(currentConversationId);
      set({ messages, isSending: false });

      // Mettre à jour le compteur
      set((state) => ({
        conversations: state.conversations.map((c) =>
          c.id === currentConversationId
            ? {
                ...c,
                message_count: messages.length,
                updated_at: new Date().toISOString(),
              }
            : c
        ),
      }));
    } catch (err) {
      set({
        error: err instanceof Error ? err.message : "Erreur d'envoi",
        isSending: false,
      });
    }
  },

  clearError: () => set({ error: null }),

  reset: () =>
    set({
      conversations: [],
      currentConversationId: null,
      messages: [],
      isLoadingConversations: false,
      isLoadingMessages: false,
      isSending: false,
      error: null,
    }),
}));
