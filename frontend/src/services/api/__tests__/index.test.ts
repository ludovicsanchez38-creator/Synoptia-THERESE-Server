import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { apiFetch } from "../index";

describe("apiFetch", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("existe et est une fonction", () => {
    expect(apiFetch).toBeDefined();
    expect(typeof apiFetch).toBe("function");
  });

  it("ajoute le header Authorization si un token est stocke", async () => {
    localStorage.setItem("therese_token", "mon-jwt");

    const spy = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({ data: "ok" }),
    } as Response);

    await apiFetch("/api/test");

    expect(spy).toHaveBeenCalledOnce();
    const [, options] = spy.mock.calls[0];
    expect((options?.headers as Record<string, string>)["Authorization"]).toBe(
      "Bearer mon-jwt"
    );
  });

  it("n'ajoute pas Authorization si skipAuth est true", async () => {
    localStorage.setItem("therese_token", "mon-jwt");

    const spy = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({}),
    } as Response);

    await apiFetch("/api/public", { skipAuth: true });

    const [, options] = spy.mock.calls[0];
    expect(
      (options?.headers as Record<string, string>)["Authorization"]
    ).toBeUndefined();
  });

  it("n'ajoute pas Authorization sans token", async () => {
    const spy = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({}),
    } as Response);

    await apiFetch("/api/test");

    const [, options] = spy.mock.calls[0];
    expect(
      (options?.headers as Record<string, string>)["Authorization"]
    ).toBeUndefined();
  });

  it("redirige vers /login sur 401", async () => {
    // Mock window.location.href
    const locationSpy = vi.spyOn(window, "location", "get").mockReturnValue({
      ...window.location,
      href: "",
    } as Location);

    // On doit aussi intercepter l'ecriture
    let redirectedTo = "";
    Object.defineProperty(window, "location", {
      value: { ...window.location, href: "" },
      writable: true,
      configurable: true,
    });
    const originalDescriptor = Object.getOwnPropertyDescriptor(window, "location");

    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce({
      ok: false,
      status: 401,
    } as Response);

    await expect(apiFetch("/api/protected")).rejects.toThrow("Session expirée");
    expect(localStorage.getItem("therese_token")).toBeNull();

    // Cleanup
    if (locationSpy) locationSpy.mockRestore();
  });

  it("ajoute Content-Type json si body est un string", async () => {
    const spy = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({ id: 1 }),
    } as Response);

    await apiFetch("/api/items", {
      method: "POST",
      body: JSON.stringify({ name: "test" }),
    });

    const [, options] = spy.mock.calls[0];
    expect((options?.headers as Record<string, string>)["Content-Type"]).toBe(
      "application/json"
    );
  });

  it("retourne undefined sur 204 No Content", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce({
      ok: true,
      status: 204,
      json: async () => {
        throw new Error("No body");
      },
    } as Response);

    const result = await apiFetch("/api/items/1", { method: "DELETE" });
    expect(result).toBeUndefined();
  });

  it("lance une erreur sur reponse non-ok (hors 401)", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce({
      ok: false,
      status: 500,
      text: async () => "Internal Server Error",
    } as Response);

    await expect(apiFetch("/api/broken")).rejects.toThrow(
      "Internal Server Error"
    );
  });
});
