import { describe, it, expect, beforeEach, vi } from "vitest";
import { useAuthStore } from "../stores/authStore";

// Mock localStorage
const storage: Record<string, string> = {};
vi.stubGlobal("localStorage", {
  getItem: (key: string) => storage[key] ?? null,
  setItem: (key: string, value: string) => { storage[key] = value; },
  removeItem: (key: string) => { delete storage[key]; },
});

describe("authStore", () => {
  beforeEach(() => {
    useAuthStore.setState({
      user: null,
      token: null,
      isLoading: true,
    });
    Object.keys(storage).forEach((k) => delete storage[k]);
  });

  it("etat initial sans token", () => {
    const state = useAuthStore.getState();
    expect(state.user).toBeNull();
    expect(state.isLoading).toBe(true);
  });

  it("logout nettoie le state", () => {
    useAuthStore.setState({
      user: { id: "1", email: "a@b.com", name: "Test", role: "admin", org_id: "o1", org_name: "Org", charter_accepted: true },
      token: "tok123",
    });
    storage["therese_token"] = "tok123";

    useAuthStore.getState().logout();
    const state = useAuthStore.getState();

    expect(state.user).toBeNull();
    expect(state.token).toBeNull();
    expect(storage["therese_token"]).toBeUndefined();
  });

  it("checkAuth sans token met isLoading a false", async () => {
    await useAuthStore.getState().checkAuth();
    expect(useAuthStore.getState().isLoading).toBe(false);
    expect(useAuthStore.getState().user).toBeNull();
  });

  it("acceptCharter sans token leve une erreur", async () => {
    useAuthStore.setState({ token: null });
    await expect(useAuthStore.getState().acceptCharter()).rejects.toThrow("Non authentifié");
  });

  it("login stocke le token en localStorage", async () => {
    vi.stubGlobal("fetch", vi.fn()
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ access_token: "new-token" }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ id: "1", email: "a@b.com", name: "Test", role: "admin", org_id: "o1", org_name: "Org", charter_accepted: true }),
      })
    );

    await useAuthStore.getState().login("a@b.com", "pass");

    expect(storage["therese_token"]).toBe("new-token");
    expect(useAuthStore.getState().user?.email).toBe("a@b.com");
  });
});
