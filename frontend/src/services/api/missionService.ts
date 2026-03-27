/**
 * Service API pour les missions autonomes (agents).
 */

import { apiFetch } from "./index";

export interface MissionTypeInfo {
  type: string;
  label: string;
  description: string;
  icon: string;
}

export interface MissionStartResponse {
  id: string;
  status: string;
  message: string;
}

export interface MissionPollResponse {
  id: string;
  status: string;
  progress: number;
  result_content: string | null;
  error: string | null;
}

export interface Mission {
  id: string;
  mission_type: string;
  title: string;
  status: string;
  progress: number;
  result_content: string | null;
  openclaw_agent: string;
  tokens_used: number;
  cost_eur: number;
  error: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export async function fetchMissionTypes(): Promise<MissionTypeInfo[]> {
  return apiFetch<MissionTypeInfo[]>("/api/missions/types");
}

export async function startMission(
  missionType: string,
  inputText: string,
  conversationId?: string,
  title?: string,
): Promise<MissionStartResponse> {
  return apiFetch<MissionStartResponse>("/api/missions/start", {
    method: "POST",
    body: JSON.stringify({
      mission_type: missionType,
      input_text: inputText,
      conversation_id: conversationId,
      title,
    }),
  });
}

export async function pollMission(missionId: string): Promise<MissionPollResponse> {
  return apiFetch<MissionPollResponse>(`/api/missions/${missionId}/poll`);
}

export async function cancelMission(missionId: string): Promise<void> {
  await apiFetch<void>(`/api/missions/${missionId}/cancel`, { method: "POST" });
}

export async function fetchMissions(): Promise<Mission[]> {
  return apiFetch<Mission[]>("/api/missions");
}
