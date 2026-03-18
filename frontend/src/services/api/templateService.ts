/**
 * Service API pour les templates de prompts.
 */

import { apiFetch } from "./index";

export interface PromptTemplate {
  id: string;
  name: string;
  prompt: string;
  category: string;
  icon: string | null;
  user_id: string | null;
  org_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface CreateTemplateRequest {
  name: string;
  prompt: string;
  category?: string;
  icon?: string;
}

export interface SeedResult {
  message: string;
  count: number;
  created: number;
}

export async function fetchTemplates(
  category?: string
): Promise<PromptTemplate[]> {
  const params = category ? `?category=${encodeURIComponent(category)}` : "";
  return apiFetch<PromptTemplate[]>(`/api/templates${params}`);
}

export async function createTemplate(
  data: CreateTemplateRequest
): Promise<PromptTemplate> {
  return apiFetch<PromptTemplate>("/api/templates", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function seedTemplates(): Promise<SeedResult> {
  return apiFetch<SeedResult>("/api/templates/seed", {
    method: "POST",
  });
}
