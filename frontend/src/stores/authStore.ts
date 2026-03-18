import { create } from "zustand";

export interface User {
  id: string;
  email: string;
  name: string;
  role: "admin" | "manager" | "agent";
  org_id: string;
  org_name: string;
  charter_accepted: boolean;
}

interface AuthState {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  checkAuth: () => Promise<void>;
  acceptCharter: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  token: localStorage.getItem("therese_token"),
  isLoading: true,

  login: async (email: string, password: string) => {
    const response = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({ username: email, password }),
    });
    if (!response.ok) throw new Error("Identifiants incorrects");

    const data = await response.json();
    localStorage.setItem("therese_token", data.access_token);
    set({ token: data.access_token });

    // Fetch user profile
    const userResponse = await fetch("/api/auth/me", {
      headers: { Authorization: `Bearer ${data.access_token}` },
    });
    if (userResponse.ok) {
      const user = await userResponse.json();
      set({ user, isLoading: false });
    }
  },

  logout: () => {
    localStorage.removeItem("therese_token");
    set({ user: null, token: null });
  },

  checkAuth: async () => {
    const token = localStorage.getItem("therese_token");
    if (!token) {
      set({ isLoading: false });
      return;
    }

    try {
      const response = await fetch("/api/auth/me", {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (response.ok) {
        const user = await response.json();
        set({ user, token, isLoading: false });
      } else {
        localStorage.removeItem("therese_token");
        set({ user: null, token: null, isLoading: false });
      }
    } catch {
      set({ isLoading: false });
    }
  },

  acceptCharter: async () => {
    const token = get().token;
    if (!token) throw new Error("Non authentifie");

    const response = await fetch("/api/auth/charter", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ accepted: true }),
    });

    if (!response.ok) {
      throw new Error("Erreur lors de l'acceptation de la charte");
    }

    const user = get().user;
    if (user) {
      set({ user: { ...user, charter_accepted: true } });
    }
  },
}));
