/**
 * Base fetch wrapper avec gestion JWT automatique.
 */

const API_BASE = "";

function getToken(): string | null {
  return localStorage.getItem("therese_token");
}

interface FetchOptions extends RequestInit {
  skipAuth?: boolean;
}

export async function apiFetch<T>(
  endpoint: string,
  options: FetchOptions = {}
): Promise<T> {
  const { skipAuth = false, headers: customHeaders, ...rest } = options;

  const headers: Record<string, string> = {
    ...(customHeaders as Record<string, string>),
  };

  if (!skipAuth) {
    const token = getToken();
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }
  }

  if (
    rest.body &&
    typeof rest.body === "string" &&
    !headers["Content-Type"]
  ) {
    headers["Content-Type"] = "application/json";
  }

  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...rest,
    headers,
  });

  if (response.status === 401) {
    localStorage.removeItem("therese_token");
    window.location.href = "/login";
    throw new Error("Session expirée");
  }

  if (!response.ok) {
    const text = await response.text().catch(() => "Erreur inconnue");
    throw new Error(text || `Erreur ${response.status}`);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json();
}
