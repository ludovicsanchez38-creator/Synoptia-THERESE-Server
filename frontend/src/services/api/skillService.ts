import { apiFetch } from './index';

export interface SkillInfo {
  skill_id: string;
  name: string;
  description: string;
  format: string;
}

export interface SkillSchema {
  skill_id: string;
  output_type: 'text' | 'file' | 'analysis';
  schema: Record<string, SkillFieldSchema>;
}

export interface SkillFieldSchema {
  type: string;
  label: string;
  placeholder: string;
  required: boolean;
  options: string[] | null;
  default: string | null;
  help_text: string | null;
}

export interface SkillExecuteResponse {
  success: boolean;
  file_id?: string;
  file_name?: string;
  file_size?: number;
  download_url?: string;
  preview?: string;
  error?: string;
}

export async function fetchSkills(): Promise<SkillInfo[]> {
  return apiFetch('/api/skills/list');
}

export async function fetchSkillInfo(skillId: string): Promise<SkillInfo> {
  return apiFetch(`/api/skills/info/${skillId}`);
}

export async function fetchSkillSchema(skillId: string): Promise<SkillSchema> {
  return apiFetch(`/api/skills/schema/${skillId}`);
}

export async function executeSkill(
  skillId: string,
  prompt: string,
  title?: string,
  template?: string,
  context?: Record<string, unknown>,
): Promise<SkillExecuteResponse> {
  return apiFetch(`/api/skills/execute/${skillId}`, {
    method: 'POST',
    body: JSON.stringify({
      prompt,
      title: title || undefined,
      template: template || 'synoptia-dark',
      context: context || {},
    }),
  });
}

export async function downloadSkillFile(fileId: string, fileName?: string): Promise<void> {
  const token = localStorage.getItem('therese_token');
  const response = await fetch(`/api/skills/download/${fileId}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });

  if (!response.ok) {
    throw new Error(`Erreur de téléchargement (${response.status})`);
  }

  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = fileName || 'document';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
