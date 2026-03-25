import { describe, it, expect, beforeEach, vi } from "vitest";

// Mock localStorage
const storage: Record<string, string> = {};
vi.stubGlobal("localStorage", {
  getItem: (key: string) => storage[key] ?? null,
  setItem: (key: string, value: string) => { storage[key] = value; },
  removeItem: (key: string) => { delete storage[key]; },
});

// Mock window.location
const locationMock = { href: "" };
vi.stubGlobal("location", locationMock);

import { apiFetch } from "../services/api/index";

describe("apiFetch", () => {
  beforeEach(() => {
    Object.keys(storage).forEach((k) => delete storage[k]);
    locationMock.href = "";
    vi.restoreAllMocks();
  });

  it("ajoute le header Authorization quand un token existe", async () => {
    storage["therese_token"] = "my-token";
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ data: "ok" }),
    }));

    await apiFetch("/api/test");

    expect(fetch).toHaveBeenCalledWith("/api/test", expect.objectContaining({
      headers: expect.objectContaining({ Authorization: "Bearer my-token" }),
    }));
  });

  it("n'ajoute pas Authorization sans token", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({}),
    }));

    await apiFetch("/api/test");

    const call = vi.mocked(fetch).mock.calls[0];
    const headers = call[1]?.headers as Record<string, string>;
    expect(headers["Authorization"]).toBeUndefined();
  });

  it("skipAuth desactive le header Authorization", async () => {
    storage["therese_token"] = "my-token";
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({}),
    }));

    await apiFetch("/api/test", { skipAuth: true });

    const call = vi.mocked(fetch).mock.calls[0];
    const headers = call[1]?.headers as Record<string, string>;
    expect(headers["Authorization"]).toBeUndefined();
  });

  it("ajoute Content-Type json quand body est un string", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({}),
    }));

    await apiFetch("/api/test", { method: "POST", body: JSON.stringify({ a: 1 }) });

    expect(fetch).toHaveBeenCalledWith("/api/test", expect.objectContaining({
      headers: expect.objectContaining({ "Content-Type": "application/json" }),
    }));
  });

  it("redirige vers /login sur 401", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
    }));

    await expect(apiFetch("/api/test")).rejects.toThrow("Session expirée");
    expect(locationMock.href).toBe("/login");
  });

  it("retourne undefined sur 204", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      status: 204,
    }));

    const result = await apiFetch("/api/test");
    expect(result).toBeUndefined();
  });

  it("leve une erreur sur reponse non-ok", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      text: () => Promise.resolve("Internal Server Error"),
    }));

    await expect(apiFetch("/api/test")).rejects.toThrow("Internal Server Error");
  });
});
