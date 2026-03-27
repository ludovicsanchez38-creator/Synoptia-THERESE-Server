/**
 * Service API pour la transcription vocale (Groq Whisper).
 */

import { getToken } from "./authService";

const API_BASE = "";

export interface TranscriptionResult {
  text: string;
  duration_seconds: number | null;
  language: string | null;
}

/**
 * Envoie un blob audio au backend pour transcription via Groq Whisper.
 * Utilise FormData (pas JSON) car le backend attend un UploadFile.
 */
export async function transcribeAudio(
  audioBlob: Blob
): Promise<TranscriptionResult> {
  const formData = new FormData();
  formData.append("audio", audioBlob, "recording.webm");

  const headers: Record<string, string> = {};
  const token = getToken();
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  // Ne PAS mettre Content-Type : fetch le gere automatiquement pour FormData

  const response = await fetch(`${API_BASE}/api/voice/transcribe`, {
    method: "POST",
    headers,
    body: formData,
  });

  if (response.status === 401) {
    localStorage.removeItem("therese_token");
    window.location.href = "/login";
    throw new Error("Session expirée");
  }

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ detail: "Erreur inconnue" }));
    throw new Error(errorData.detail || `Erreur ${response.status}`);
  }

  return response.json();
}

/**
 * Vérifie si le navigateur supporte l'enregistrement audio.
 */
export function isMediaRecorderSupported(): boolean {
  return typeof navigator.mediaDevices?.getUserMedia === "function" && typeof window.MediaRecorder === "function";
}
