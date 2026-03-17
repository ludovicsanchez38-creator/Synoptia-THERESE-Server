import { create } from "zustand";
import {
  fetchConversations,
  createConversation,
  deleteConversation,
  fetchMessages,
  sendMessage,
} from "../services/api/chatService";
import type { Conversation, Message } from "../services/api/chatService";

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
        error: err instanceof Error ? err.message : "Erreur de cr\u00e9ation",
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
      id: `temp-${Date.now()}`,
      role: "user",
      content,
      created_at: new Date().toISOString(),
    };
    set((state) => ({ messages: [...state.messages, tempUserMsg] }));

    try {
      const userMsg = await sendMessage(currentConversationId, content, "user");

      // Remplacer le message temporaire par le vrai
      set((state) => ({
        messages: state.messages.map((m) =>
          m.id === tempUserMsg.id ? userMsg : m
        ),
      }));

      // Recharger les messages pour obtenir la r\u00e9ponse de l'assistant
      // (le backend peut g\u00e9n\u00e9rer une r\u00e9ponse automatiquement)
      const messages = await fetchMessages(currentConversationId);
      set({ messages, isSending: false });

      // Mettre \u00e0 jour le compteur de messages dans la liste
      set((state) => ({
        conversations: state.conversations.map((c) =>
          c.id === currentConversationId
            ? { ...c, message_count: messages.length, updated_at: new Date().toISOString() }
            : c
        ),
      }));
    } catch (err) {
      set({
        error: err instanceof Error ? err.message : "Erreur d\u0027envoi",
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
