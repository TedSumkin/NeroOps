export type EntryType =
  | "feeding"
  | "walk"
  | "symptom"
  | "wellbeing"
  | "training"
  | "medication"
  | "weight"
  | "vet_visit"
  | "note";

export type SyncStatus = "pending" | "syncing" | "synced" | "failed";

export interface Pet {
  id: string;
  name: string;
  species: string;
  breed: string | null;
  birth_date: string | null;
}

export interface Attachment {
  id: string;
  filename: string;
  mime_type: string;
  size_bytes: number;
  sha256: string;
  created_at: string;
  url: string;
}

export interface Entry {
  id: string;
  pet_id: string;
  type: EntryType;
  occurred_at: string;
  note: string | null;
  payload: Record<string, unknown>;
  created_at?: string;
  updated_at?: string;
  attachments: Attachment[];
  sync_status?: SyncStatus;
}

export interface QueuedFile {
  id: string;
  name: string;
  type: string;
  blob: Blob;
}

export interface QueueItem {
  id: string;
  entry: Entry;
  files: QueuedFile[];
  status: SyncStatus;
  error?: string;
}

export interface Bootstrap {
  pet: Pet;
  entry_types: Array<{ value: EntryType; label: string }>;
  recent_entries: Entry[];
  server_time: string;
}

export interface Summary {
  from_date: string;
  to_date: string;
  total_entries: number;
  counts_by_type: Record<string, number>;
  symptom_counts: Record<string, number>;
  average_scores: Record<string, number>;
  weight_series: Array<{ occurred_at: string; weight_kg: number }>;
  daily_counts: Array<{ date: string; count: number }>;
}

