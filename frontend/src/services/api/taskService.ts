import { apiFetch } from './index';

export interface Task {
  id: string;
  title: string;
  description: string | null;
  status: 'todo' | 'in_progress' | 'done';
  priority: 'low' | 'medium' | 'high';
  due_date: string | null;
  project_id: string | null;
  created_at: string;
  updated_at: string;
}

export async function fetchTasks(): Promise<Task[]> {
  return apiFetch('/api/tasks/');
}

export async function createTask(data: { title: string; description?: string; priority?: string; status?: string }): Promise<Task> {
  return apiFetch('/api/tasks/', { method: 'POST', body: JSON.stringify(data) });
}

export async function updateTask(id: string, data: Partial<Task>): Promise<Task> {
  return apiFetch(`/api/tasks/${id}`, { method: 'PUT', body: JSON.stringify(data) });
}

export async function deleteTask(id: string): Promise<void> {
  return apiFetch(`/api/tasks/${id}`, { method: 'DELETE' });
}

export async function completeTask(id: string): Promise<Task> {
  return apiFetch(`/api/tasks/${id}/complete`, { method: 'PATCH' });
}
