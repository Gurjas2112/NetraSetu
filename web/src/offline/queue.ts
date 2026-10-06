import Dexie, { type EntityTable } from "dexie";

/** Pending field captures only. Clinical results never go in IndexedDB. Purged after sync. */
export type PendingCapture = {
  id?: number;
  createdAt: number;
  filename: string;
  mimeType: string;
  bytes: ArrayBuffer;
  patientRef: string;
  consentId: string;
};

const db = new Dexie("netrasetu-field-queue") as Dexie & {
  captures: EntityTable<PendingCapture, "id">;
};

db.version(1).stores({ captures: "++id, createdAt" });

export async function enqueue(capture: Omit<PendingCapture, "id">): Promise<number> {
  const id = await db.captures.add(capture);
  if (typeof id !== "number") {
    throw new Error("queue insert did not return an id");
  }
  return id;
}

export async function pending(): Promise<PendingCapture[]> {
  return db.captures.orderBy("createdAt").toArray();
}

export async function pendingCount(): Promise<number> {
  return db.captures.count();
}

export async function remove(id: number): Promise<void> {
  await db.captures.delete(id);
}

export function captureFile(item: PendingCapture): File {
  return new File([item.bytes], item.filename, { type: item.mimeType });
}
