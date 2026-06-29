import { Conversation } from '@/types';

const BASE = '/api/conversations';

export async function listConversations(): Promise<Conversation[]> {
  const res = await fetch(BASE);
  if (!res.ok) throw new Error('Failed to list conversations');
  return res.json();
}

export async function createConversation(): Promise<Conversation> {
  const res = await fetch(BASE, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to create conversation');
  return res.json();
}

export async function getConversation(id: string): Promise<Conversation> {
  const res = await fetch(`${BASE}/${id}`);
  if (!res.ok) throw new Error('Failed to get conversation');
  return res.json();
}

export async function updateConversation(
  id: string,
  data: Partial<Pick<Conversation, 'title' | 'messages'>>
): Promise<Conversation> {
  const res = await fetch(`${BASE}/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error('Failed to update conversation');
  return res.json();
}

export async function deleteConversation(id: string): Promise<void> {
  const res = await fetch(`${BASE}/${id}`, { method: 'DELETE' });
  if (!res.ok) throw new Error('Failed to delete conversation');
}
