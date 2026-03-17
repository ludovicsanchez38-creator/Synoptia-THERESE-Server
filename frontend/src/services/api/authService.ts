/**
 * Service d'authentification - helpers pour le header JWT.
 */

export function getAuthHeader(): Record<string, string> {
  const token = localStorage.getItem("therese_token");
  if (!token) return {};
  return { Authorization: `Bearer ${token}` };
}

export function getToken(): string | null {
  return localStorage.getItem("therese_token");
}

export function clearToken(): void {
  localStorage.removeItem("therese_token");
}
