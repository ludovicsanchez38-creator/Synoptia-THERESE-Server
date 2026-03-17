/**
 * Service API pour les conversations et messages.
 */

import { apiFetch } from "./index";

export interface Conversation {
  id: string;
  title: string;
  message_count: number;
  created_at: string;
  updated_at: string;
}

export interface Message {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  model?: string;
  created_at: string;
}

export async function fetchConversations(): Promise<Conversation[]> {
  return apiFetch<Conversation[]>("/api/chat/conversations");
}

export async function createConversation(title: string): Promise<Conversation> {
  return apiFetch<Conversation>("/api/chat/conversations", {
    method: "POST",
    body: JSON.stringify({ title }),
  });
}

export async function deleteConversation(id: string): Promise<void> {
  return apiFetch<void>(`/api/chat/conversations/${id}`, {
    method: "DELETE",
  });
}

export async function fetchMessages(conversationId: string): Promise<Message[]> {
  return apiFetch<Message[]>(
    `/api/chat/conversations/${conversationId}/messages`
  );
}

export async function sendMessage(
  conversationId: string,
  content: string,
  role: "user" | "assistant" = "user"
): Promise<Message> {
  return apiFetch<Message>(
    `/api/chat/conversations/${conversationId}/messages`,
    {
      method: "POST",
      body: JSON.stringify({ content, role }),
    }
  );
}
