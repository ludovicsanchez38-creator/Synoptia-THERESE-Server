import { describe, it, expect, beforeEach, vi, afterEach } from "vitest";
import { useAuthStore } from "../authStore";

describe("authStore", () => {
  beforeEach(() => {
    useAuthStore.setState({ user: null, token: null, isLoading: true });
    localStorage.clear();
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("etat initial sans user", () => {
    expect(useAuthStore.getState().user).toBeNull();
    expect(useAuthStore.getState().token).toBeNull();
  });

  it("logout supprime le token du localStorage", () => {
    localStorage.setItem("therese_token", "fake-jwt");
    useAuthStore.setState({ token: "fake-jwt", user: { id: "1", email: "a@b.fr", name: "Test", role: "agent", org_id: "o1", org_name: "Org", charter_accepted: true } });

    useAuthStore.getState().logout();

    expect(useAuthStore.getState().user).toBeNull();
    expect(useAuthStore.getState().token).toBeNull();
    expect(localStorage.getItem("therese_token")).toBeNull();
  });

  it("checkAuth sans token passe isLoading a false", async () => {
    // Pas de token dans localStorage
    await useAuthStore.getState().checkAuth();
    expect(useAuthStore.getState().isLoading).toBe(false);
    expect(useAuthStore.getState().user).toBeNull();
  });

  it("checkAuth avec token valide charge le user", async () => {
    const fakeUser = {
      id: "u1",
      email: "test@mairie.fr",
      name: "Agent Test",
      role: "agent" as const,
      org_id: "org1",
      org_name: "Mairie Test",
      charter_accepted: true,
    };

    localStorage.setItem("therese_token", "valid-token");

    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce({
      ok: true,
      json: async () => fakeUser,
    } as Response);

    await useAuthStore.getState().checkAuth();

    expect(useAuthStore.getState().user).toEqual(fakeUser);
    expect(useAuthStore.getState().token).toBe("valid-token");
    expect(useAuthStore.getState().isLoading).toBe(false);
  });

  it("checkAuth avec token invalide nettoie le state", async () => {
    localStorage.setItem("therese_token", "expired-token");

    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce({
      ok: false,
      status: 401,
    } as Response);

    await useAuthStore.getState().checkAuth();

    expect(useAuthStore.getState().user).toBeNull();
    expect(useAuthStore.getState().token).toBeNull();
    expect(useAuthStore.getState().isLoading).toBe(false);
    expect(localStorage.getItem("therese_token")).toBeNull();
  });

  it("checkAuth sur erreur reseau passe isLoading a false", async () => {
    localStorage.setItem("therese_token", "some-token");

    vi.spyOn(globalThis, "fetch").mockRejectedValueOnce(new Error("Network error"));

    await useAuthStore.getState().checkAuth();

    expect(useAuthStore.getState().isLoading).toBe(false);
  });

  it("login stocke le token et charge le user", async () => {
    const fakeUser = {
      id: "u2",
      email: "admin@mairie.fr",
      name: "Admin",
      role: "admin" as const,
      org_id: "org1",
      org_name: "Mairie",
      charter_accepted: false,
    };

    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ access_token: "new-jwt-token" }),
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => fakeUser,
      } as Response);

    await useAuthStore.getState().login("admin@mairie.fr", "password123");

    expect(useAuthStore.getState().token).toBe("new-jwt-token");
    expect(useAuthStore.getState().user).toEqual(fakeUser);
    expect(localStorage.getItem("therese_token")).toBe("new-jwt-token");
  });

  it("login echoue sur mauvais identifiants", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce({
      ok: false,
      status: 401,
    } as Response);

    await expect(
      useAuthStore.getState().login("bad@email.fr", "wrong")
    ).rejects.toThrow("Identifiants incorrects");
  });

  it("acceptCharter met a jour charter_accepted", async () => {
    useAuthStore.setState({
      token: "valid-token",
      user: {
        id: "u1",
        email: "a@b.fr",
        name: "Test",
        role: "agent",
        org_id: "o1",
        org_name: "Org",
        charter_accepted: false,
      },
    });

    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce({
      ok: true,
      json: async () => ({}),
    } as Response);

    await useAuthStore.getState().acceptCharter();

    expect(useAuthStore.getState().user?.charter_accepted).toBe(true);
  });

  it("acceptCharter echoue sans token", async () => {
    useAuthStore.setState({ token: null, user: null });

    await expect(
      useAuthStore.getState().acceptCharter()
    ).rejects.toThrow("Non authentifié");
  });
});
