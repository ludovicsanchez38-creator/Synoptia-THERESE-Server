import { apiFetch } from './index';

export interface Contact {
  id: string;
  first_name: string | null;
  last_name: string | null;
  company: string | null;
  email: string | null;
  phone: string | null;
  stage: string;
  score: number;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface PipelineStats {
  total_contacts: number;
  stages: Record<string, number>;
}

export async function fetchContacts(): Promise<Contact[]> {
  return apiFetch('/api/memory/contacts');
}

export async function createContact(data: { name: string; email?: string; phone?: string; organization?: string; role?: string }): Promise<Contact> {
  return apiFetch('/api/memory/contacts', { method: 'POST', body: JSON.stringify(data) });
}

export async function fetchPipelineStats(): Promise<PipelineStats> {
  return apiFetch('/api/crm/pipeline/stats');
}

export async function updateContactStage(id: string, stage: string): Promise<Contact> {
  return apiFetch(`/api/crm/contacts/${id}/stage`, { method: 'PATCH', body: JSON.stringify({ stage }) });
}

export async function fetchActivities(): Promise<any[]> {
  return apiFetch('/api/crm/activities');
}

export async function createActivity(data: { contact_id: string; type: string; description: string }): Promise<any> {
  return apiFetch('/api/crm/activities', { method: 'POST', body: JSON.stringify(data) });
}
