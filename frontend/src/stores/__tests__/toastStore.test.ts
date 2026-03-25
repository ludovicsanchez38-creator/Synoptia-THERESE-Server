import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { useToastStore } from "../toastStore";

describe("toastStore", () => {
  beforeEach(() => {
    useToastStore.setState({ toasts: [] });
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("ajoute un toast", () => {
    useToastStore.getState().addToast("success", "Test reussi");
    expect(useToastStore.getState().toasts).toHaveLength(1);
    expect(useToastStore.getState().toasts[0].type).toBe("success");
    expect(useToastStore.getState().toasts[0].message).toBe("Test reussi");
  });

  it("genere un id unique pour chaque toast", () => {
    useToastStore.getState().addToast("info", "Premier");
    useToastStore.getState().addToast("info", "Deuxieme");
    const toasts = useToastStore.getState().toasts;
    expect(toasts[0].id).not.toBe(toasts[1].id);
  });

  it("supprime un toast manuellement", () => {
    useToastStore.getState().addToast("info", "Hello");
    const id = useToastStore.getState().toasts[0].id;
    useToastStore.getState().removeToast(id);
    expect(useToastStore.getState().toasts).toHaveLength(0);
  });

  it("auto-dismiss apres 5s", () => {
    useToastStore.getState().addToast("warning", "Attention");
    expect(useToastStore.getState().toasts).toHaveLength(1);
    vi.advanceTimersByTime(5100);
    expect(useToastStore.getState().toasts).toHaveLength(0);
  });

  it("supporte les 4 types", () => {
    const types = ["success", "error", "warning", "info"] as const;
    types.forEach((t) => useToastStore.getState().addToast(t, `msg-${t}`));
    expect(useToastStore.getState().toasts).toHaveLength(4);
  });

  it("ne supprime que le toast cible lors du removeToast", () => {
    useToastStore.getState().addToast("success", "A garder");
    useToastStore.getState().addToast("error", "A supprimer");
    const idToRemove = useToastStore.getState().toasts[1].id;
    useToastStore.getState().removeToast(idToRemove);
    expect(useToastStore.getState().toasts).toHaveLength(1);
    expect(useToastStore.getState().toasts[0].message).toBe("A garder");
  });

  it("removeToast avec un id inexistant ne change rien", () => {
    useToastStore.getState().addToast("info", "Stable");
    useToastStore.getState().removeToast("id-inexistant");
    expect(useToastStore.getState().toasts).toHaveLength(1);
  });
});
