import { describe, it, expect, beforeEach, vi } from "vitest";
import { useChatStore } from "../stores/chatStore";

// Mock localStorage
vi.stubGlobal("localStorage", {
  getItem: () => "fake-token",
  setItem: () => {},
  removeItem: () => {},
});

// Mock chatService
vi.mock("../services/api/chatService", () => ({
  fetchConversations: vi.fn(),
  createConversation: vi.fn(),
  deleteConversation: vi.fn(),
  fetchMessages: vi.fn(),
}));

vi.mock("../services/api/authService", () => ({
  getToken: () => "fake-token",
}));

import {
  fetchConversations,
  createConversation,
  deleteConversation,
  fetchMessages,
} from "../services/api/chatService";

describe("chatStore", () => {
  beforeEach(() => {
    useChatStore.getState().reset();
    vi.clearAllMocks();
  });

  it("etat initial", () => {
    const state = useChatStore.getState();
    expect(state.conversations).toEqual([]);
    expect(state.currentConversationId).toBeNull();
    expect(state.messages).toEqual([]);
    expect(state.isSending).toBe(false);
    expect(state.error).toBeNull();
  });

  it("loadConversations charge les conversations", async () => {
    const mockConvs = [
      { id: "c1", title: "Conv 1", message_count: 3, created_at: "2026-01-01", updated_at: "2026-01-01" },
    ];
    vi.mocked(fetchConversations).mockResolvedValue(mockConvs);

    await useChatStore.getState().loadConversations();

    expect(useChatStore.getState().conversations).toEqual(mockConvs);
    expect(useChatStore.getState().isLoadingConversations).toBe(false);
  });

  it("loadConversations gere les erreurs", async () => {
    vi.mocked(fetchConversations).mockRejectedValue(new Error("Network error"));

    await useChatStore.getState().loadConversations();

    expect(useChatStore.getState().error).toBe("Network error");
    expect(useChatStore.getState().isLoadingConversations).toBe(false);
  });

  it("selectConversation charge les messages", async () => {
    const mockMessages = [
      { id: "m1", role: "user" as const, content: "Hello", created_at: "2026-01-01" },
      { id: "m2", role: "assistant" as const, content: "Hi!", created_at: "2026-01-01" },
    ];
    vi.mocked(fetchMessages).mockResolvedValue(mockMessages);

    await useChatStore.getState().selectConversation("c1");

    expect(useChatStore.getState().currentConversationId).toBe("c1");
    expect(useChatStore.getState().messages).toEqual(mockMessages);
  });

  it("newConversation cree et selectionne", async () => {
    const newConv = { id: "c2", title: "Nouvelle", message_count: 0, created_at: "2026-01-01", updated_at: "2026-01-01" };
    vi.mocked(createConversation).mockResolvedValue(newConv);

    await useChatStore.getState().newConversation("Nouvelle");

    expect(useChatStore.getState().currentConversationId).toBe("c2");
    expect(useChatStore.getState().conversations).toHaveLength(1);
  });

  it("removeConversation supprime de la liste", async () => {
    useChatStore.setState({
      conversations: [
        { id: "c1", title: "A", message_count: 0, created_at: "", updated_at: "" },
        { id: "c2", title: "B", message_count: 0, created_at: "", updated_at: "" },
      ],
      currentConversationId: "c1",
    });
    vi.mocked(deleteConversation).mockResolvedValue();

    await useChatStore.getState().removeConversation("c1");

    expect(useChatStore.getState().conversations).toHaveLength(1);
    expect(useChatStore.getState().currentConversationId).toBeNull();
  });

  it("clearError remet error a null", () => {
    useChatStore.setState({ error: "une erreur" });
    useChatStore.getState().clearError();
    expect(useChatStore.getState().error).toBeNull();
  });

  it("reset remet tout a zero", () => {
    useChatStore.setState({
      conversations: [{ id: "c1", title: "A", message_count: 0, created_at: "", updated_at: "" }],
      currentConversationId: "c1",
      isSending: true,
      error: "erreur",
    });

    useChatStore.getState().reset();

    const state = useChatStore.getState();
    expect(state.conversations).toEqual([]);
    expect(state.currentConversationId).toBeNull();
    expect(state.isSending).toBe(false);
    expect(state.error).toBeNull();
  });
});
