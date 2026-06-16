import type { Entry, QueueItem } from "./types";

const DB_NAME = "neroops";
const DB_VERSION = 1;
const ENTRY_STORE = "entries";
const QUEUE_STORE = "queue";
const META_STORE = "meta";

function openDatabase(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    request.onerror = () => reject(request.error);
    request.onsuccess = () => resolve(request.result);
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains(ENTRY_STORE)) {
        const entries = db.createObjectStore(ENTRY_STORE, { keyPath: "id" });
        entries.createIndex("occurred_at", "occurred_at");
      }
      if (!db.objectStoreNames.contains(QUEUE_STORE)) {
        db.createObjectStore(QUEUE_STORE, { keyPath: "id" });
      }
      if (!db.objectStoreNames.contains(META_STORE)) {
        db.createObjectStore(META_STORE);
      }
    };
  });
}

function requestResult<T>(request: IDBRequest<T>): Promise<T> {
  return new Promise((resolve, reject) => {
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

export async function cacheEntries(entries: Entry[]): Promise<void> {
  const db = await openDatabase();
  const transaction = db.transaction(ENTRY_STORE, "readwrite");
  const store = transaction.objectStore(ENTRY_STORE);
  for (const entry of entries) store.put({ ...entry, sync_status: "synced" });
}

export async function cacheEntry(entry: Entry): Promise<void> {
  const db = await openDatabase();
  await requestResult(db.transaction(ENTRY_STORE, "readwrite").objectStore(ENTRY_STORE).put(entry));
}

export async function removeCachedEntry(id: string): Promise<void> {
  const db = await openDatabase();
  await requestResult(db.transaction(ENTRY_STORE, "readwrite").objectStore(ENTRY_STORE).delete(id));
}

export async function getCachedEntries(): Promise<Entry[]> {
  const db = await openDatabase();
  const entries = await requestResult(
    db.transaction(ENTRY_STORE, "readonly").objectStore(ENTRY_STORE).getAll(),
  );
  return entries.sort(
    (left, right) => new Date(right.occurred_at).getTime() - new Date(left.occurred_at).getTime(),
  );
}

export async function enqueue(item: QueueItem): Promise<void> {
  const db = await openDatabase();
  const transaction = db.transaction([QUEUE_STORE, ENTRY_STORE], "readwrite");
  transaction.objectStore(QUEUE_STORE).put(item);
  transaction.objectStore(ENTRY_STORE).put({ ...item.entry, sync_status: item.status });
}

export async function getQueue(): Promise<QueueItem[]> {
  const db = await openDatabase();
  return requestResult(db.transaction(QUEUE_STORE, "readonly").objectStore(QUEUE_STORE).getAll());
}

export async function updateQueue(item: QueueItem): Promise<void> {
  const db = await openDatabase();
  const transaction = db.transaction([QUEUE_STORE, ENTRY_STORE], "readwrite");
  transaction.objectStore(QUEUE_STORE).put(item);
  transaction.objectStore(ENTRY_STORE).put({ ...item.entry, sync_status: item.status });
}

export async function completeQueueItem(id: string, serverEntry: Entry): Promise<void> {
  const db = await openDatabase();
  const transaction = db.transaction([QUEUE_STORE, ENTRY_STORE], "readwrite");
  transaction.objectStore(QUEUE_STORE).delete(id);
  transaction.objectStore(ENTRY_STORE).put({ ...serverEntry, sync_status: "synced" });
}

export async function discardQueueItem(id: string): Promise<void> {
  const db = await openDatabase();
  const transaction = db.transaction([QUEUE_STORE, ENTRY_STORE], "readwrite");
  transaction.objectStore(QUEUE_STORE).delete(id);
  transaction.objectStore(ENTRY_STORE).delete(id);
}

export async function setMeta<T>(key: string, value: T): Promise<void> {
  const db = await openDatabase();
  await requestResult(db.transaction(META_STORE, "readwrite").objectStore(META_STORE).put(value, key));
}

export async function getMeta<T>(key: string): Promise<T | undefined> {
  const db = await openDatabase();
  return requestResult(db.transaction(META_STORE, "readonly").objectStore(META_STORE).get(key));
}
