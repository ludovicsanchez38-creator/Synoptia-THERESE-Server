/**
 * Service API pour le Board de Décision (délibération multi-advisors).
 */

import { apiFetch } from "./index";

export interface AdvisorInfo {
  role: string;
  name: string;
  emoji: string;
  color: string;
  personality: string;
}

export interface BoardDecisionSummary {
  id: string;
  question: string;
  context: string | null;
  recommendation: string;
  confidence: string;
  mode: string;
  created_at: string;
}

export interface AdvisorOpinion {
  role: string;
  name: string;
  emoji: string;
  content: string;
  generated_at: string;
}

export interface BoardSynthesis {
  consensus_points: string[];
  divergence_points: string[];
  recommendation: string;
  confidence: string;
  next_steps: string[];
}

export interface BoardDecisionFull {
  id: string;
  question: string;
  context: string | null;
  opinions: AdvisorOpinion[];
  synthesis: BoardSynthesis;
  mode: string;
  created_at: string;
}

export interface BoardSSEChunk {
  type: string;
  role?: string;
  name?: string;
  emoji?: string;
  provider?: string;
  content: string;
}

export async function fetchAdvisors(): Promise<AdvisorInfo[]> {
  return apiFetch<AdvisorInfo[]>("/api/board/advisors");
}

/**
 * Lance une délibération en streaming SSE.
 * Retourne un ReadableStream de chunks SSE parsés.
 */
export async function startDeliberation(
  question: string,
  context?: string,
  mode: "cloud" | "sovereign" = "cloud",
): Promise<{
  stream: ReadableStream<BoardSSEChunk>;
  abort: () => void;
}> {
  const token = localStorage.getItem("therese_token");
  const controller = new AbortController();

  const response = await fetch("/api/board/deliberate", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ question, context: context || null, mode }),
    signal: controller.signal,
  });

  if (!response.ok) {
    const text = await response.text().catch(() => "Erreur inconnue");
    throw new Error(text || `Erreur ${response.status}`);
  }

  if (!response.body) {
    throw new Error("Pas de stream disponible");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  const stream = new ReadableStream<BoardSSEChunk>({
    async pull(streamController) {
      try {
        const { done, value } = await reader.read();
        if (done) {
          // Flush remaining buffer
          if (buffer.trim()) {
            const lines = buffer.split("\n");
            for (const line of lines) {
              const trimmed = line.trim();
              if (trimmed.startsWith("data: ")) {
                try {
                  const parsed = JSON.parse(trimmed.slice(6)) as BoardSSEChunk;
                  streamController.enqueue(parsed);
                } catch {
                  // ignore parse errors on trailing data
                }
              }
            }
          }
          streamController.close();
          return;
        }

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        // Keep the last incomplete line in the buffer
        buffer = lines.pop() || "";

        for (const line of lines) {
          const trimmed = line.trim();
          if (trimmed.startsWith("data: ")) {
            try {
              const parsed = JSON.parse(trimmed.slice(6)) as BoardSSEChunk;
              streamController.enqueue(parsed);
            } catch {
              // skip invalid JSON
            }
          }
        }
      } catch (err) {
        if ((err as Error).name !== "AbortError") {
          streamController.error(err);
        } else {
          streamController.close();
        }
      }
    },
    cancel() {
      reader.cancel();
    },
  });

  return {
    stream,
    abort: () => controller.abort(),
  };
}

export async function fetchDecisions(): Promise<BoardDecisionSummary[]> {
  return apiFetch<BoardDecisionSummary[]>("/api/board/decisions");
}

export async function fetchDecision(id: string): Promise<BoardDecisionFull> {
  return apiFetch<BoardDecisionFull>(`/api/board/decisions/${id}`);
}

export async function deleteDecision(id: string): Promise<void> {
  return apiFetch<void>(`/api/board/decisions/${id}`, {
    method: "DELETE",
  });
}
