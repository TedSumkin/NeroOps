import { cacheEntries, completeQueueItem, getQueue, setMeta, updateQueue } from "./db";
import type { Bootstrap, Entry, Pet, QueueItem, Summary } from "./types";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`/api/v1${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail));
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export async function checkHealth(): Promise<boolean> {
  try {
    await request<{ status: string }>("/health");
    return true;
  } catch {
    return false;
  }
}

export async function fetchBootstrap(): Promise<Bootstrap> {
  const bootstrap = await request<Bootstrap>("/bootstrap");
  await Promise.all([
    cacheEntries(bootstrap.recent_entries),
    setMeta("pet", bootstrap.pet),
    setMeta("entry_types", bootstrap.entry_types),
  ]);
  return bootstrap;
}

export async function fetchAllEntries(): Promise<Entry[]> {
  const entries: Entry[] = [];
  const limit = 200;
  let offset = 0;
  while (true) {
    const page = await request<{ items: Entry[]; total: number; limit: number; offset: number }>(
      `/entries?limit=${limit}&offset=${offset}`,
    );
    entries.push(...page.items);
    offset += page.items.length;
    if (offset >= page.total || page.items.length === 0) break;
  }
  await cacheEntries(entries);
  return entries;
}

export function createEntry(entry: Entry): Promise<Entry> {
  return request<Entry>("/entries", {
    method: "POST",
    body: JSON.stringify(entry),
  });
}

export function deleteEntry(id: string): Promise<void> {
  return request<void>(`/entries/${id}`, { method: "DELETE" });
}

export function updateEntry(
  id: string,
  changes: Pick<Entry, "occurred_at" | "note" | "payload">,
): Promise<Entry> {
  return request<Entry>(`/entries/${id}`, {
    method: "PATCH",
    body: JSON.stringify(changes),
  });
}

export function updatePet(pet: Omit<Pet, "id">): Promise<Pet> {
  return request<Pet>("/pet", {
    method: "PATCH",
    body: JSON.stringify(pet),
  });
}

export function fetchSummary(from: string, to: string): Promise<Summary> {
  return request<Summary>(`/reports/summary?from=${from}&to=${to}`);
}

export async function uploadAttachment(
  entryId: string,
  attachmentId: string,
  file: Blob,
  filename: string,
): Promise<void> {
  const form = new FormData();
  form.append("file", file, filename);
  const response = await fetch(`/api/v1/entries/${entryId}/attachments`, {
    method: "POST",
    headers: { "X-Attachment-ID": attachmentId },
    body: form,
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(body.detail || "Не удалось загрузить вложение");
  }
}

export async function syncQueue(onChange?: () => void): Promise<void> {
  if (!navigator.onLine) return;
  const queue = await getQueue();
  for (const item of queue) {
    const syncing: QueueItem = { ...item, status: "syncing", error: undefined };
    await updateQueue(syncing);
    onChange?.();
    try {
      let serverEntry = await createEntry(item.entry);
      for (const file of item.files) {
        await uploadAttachment(item.entry.id, file.id, file.blob, file.name);
      }
      if (item.files.length > 0) {
        const refreshed = await fetch(`/api/v1/entries/${item.entry.id}`);
        if (refreshed.ok) serverEntry = (await refreshed.json()) as Entry;
      }
      await completeQueueItem(item.id, serverEntry);
    } catch (error) {
      await updateQueue({
        ...item,
        status: "failed",
        error: error instanceof Error ? error.message : "Ошибка синхронизации",
      });
    }
    onChange?.();
  }
}
