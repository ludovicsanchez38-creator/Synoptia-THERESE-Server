/**
 * Service API pour le dashboard administrateur.
 */

import { apiFetch } from "./index";

// --- Types ---

export interface AdminStats {
  total_users: number;
  active_users: number;
  total_conversations: number;
  messages_today: number;
  total_contacts: number;
}

export interface UserItem {
  id: string;
  email: string;
  name: string;
  role: string;
  is_active: boolean;
  is_verified: boolean;
  last_login: string | null;
  created_at: string | null;
}

export interface AuditLogItem {
  id: string;
  user_email: string | null;
  action: string;
  resource: string | null;
  resource_id: string | null;
  details_json: string | null;
  ip_address: string | null;
  timestamp: string;
}

export interface AuditLogResponse {
  items: AuditLogItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface OrgSettings {
  id: string;
  name: string;
  slug: string;
  max_users: number;
  max_tokens_per_day: number;
  is_active: boolean;
  settings: Record<string, unknown> | null;
}

// --- API calls ---

export async function fetchAdminStats(): Promise<AdminStats> {
  return apiFetch<AdminStats>("/api/admin/stats");
}

export async function fetchUsers(): Promise<UserItem[]> {
  return apiFetch<UserItem[]>("/api/admin/users");
}

export async function updateUser(
  userId: string,
  data: { role?: string; is_active?: boolean }
): Promise<UserItem> {
  return apiFetch<UserItem>(`/api/admin/users/${userId}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function deactivateUser(userId: string): Promise<void> {
  return apiFetch<void>(`/api/admin/users/${userId}`, {
    method: "DELETE",
  });
}

export async function fetchAuditLogs(params?: {
  page?: number;
  page_size?: number;
  action?: string;
  user_id?: string;
}): Promise<AuditLogResponse> {
  const searchParams = new URLSearchParams();
  if (params?.page) searchParams.set("page", String(params.page));
  if (params?.page_size) searchParams.set("page_size", String(params.page_size));
  if (params?.action) searchParams.set("action", params.action);
  if (params?.user_id) searchParams.set("user_id", params.user_id);

  const qs = searchParams.toString();
  return apiFetch<AuditLogResponse>(`/api/admin/audit${qs ? `?${qs}` : ""}`);
}

export async function fetchOrgSettings(): Promise<OrgSettings> {
  return apiFetch<OrgSettings>("/api/admin/org/settings");
}

export async function updateOrgSettings(
  data: { name?: string; max_users?: number; max_tokens_per_day?: number; settings?: Record<string, unknown> }
): Promise<OrgSettings> {
  return apiFetch<OrgSettings>("/api/admin/org/settings", {
    method: "PUT",
    body: JSON.stringify(data),
  });
}
