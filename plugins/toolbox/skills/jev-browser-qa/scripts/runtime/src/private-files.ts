import { constants } from "node:fs";
import { stat, open, rename, unlink, realpath } from "node:fs/promises";
import { resolve } from "node:path";
import { randomUUID } from "node:crypto";
import { Budget, type Ledger } from "./budget.ts";

export async function requireOutsideCheckout(path: string): Promise<void> {
  let directory = await realpath(resolve(path, ".."));
  for (;;) {
    if (await stat(resolve(directory, ".git")).then(() => true, error => {
      if (error.code === "ENOENT") return false;
      throw error;
    })) throw new Error("blocked_private_checkout");
    const parent = resolve(directory, "..");
    if (parent === directory) break;
    directory = parent;
  }
}
export async function readPrivateFile(path: string): Promise<string> {
  await requireOutsideCheckout(path);
  const handle = await open(path, constants.O_RDONLY | constants.O_NOFOLLOW);
  try {
    const info = await handle.stat();
    if (!info.isFile() || info.mode & 0o077 || info.uid !== process.getuid?.())
      throw new Error("blocked_private_file");
    return await handle.readFile("utf8");
  } finally { await handle.close(); }
}

export async function writePrivateFile(path: string, data: string): Promise<void> {
  const temporary = `${path}.${randomUUID()}.tmp`;
  try {
    const handle = await open(temporary, "wx", 0o600);
    try { await handle.writeFile(data); await handle.sync(); } finally { await handle.close(); }
    await rename(temporary, path);
    const directory = await open(resolve(path, ".."), constants.O_RDONLY);
    try { await directory.sync(); } finally { await directory.close(); }
  } catch (error) { await unlink(temporary).catch(() => {}); throw error; }
}
export async function openBudget(path: string, limitJPY = 500): Promise<{ budget: Budget; close(): Promise<void>; }> {
  await requireOutsideCheckout(path);
  const absolute = resolve(path);
  const parent = await stat(resolve(absolute, ".."));
  if (!parent.isDirectory() || parent.mode & 0o077 || parent.uid !== process.getuid?.())
    throw new Error("blocked_private_directory");
  const lockPath = `${absolute}.lock`;
  const lock = await open(lockPath, "wx", 0o600).catch(() => { throw new Error("blocked_budget_lock"); });
  try {
    await lock.writeFile(JSON.stringify({pid: process.pid, createdAt: new Date().toISOString()}));
    await lock.sync();
    const ledger = JSON.parse(await readPrivateFile(absolute)) as Ledger;
    if (ledger.limitJPY !== limitJPY) throw new Error("blocked_budget_limit_changed");
    let closed = false;
    const pending = new Set<Promise<void>>();
    const budget = new Budget(ledger, async next => {
      if (closed) throw new Error("blocked_budget_closed");
      const writing = writePrivateFile(absolute, JSON.stringify(next));
      pending.add(writing);
      try { await writing; } finally { pending.delete(writing); }
    });
    let closing: Promise<void> | undefined;
    return { budget, close() {
      if (closing) return closing;
      closed = true;
      budget.invalidate();
      closing = (async () => { await Promise.allSettled([...pending]); await lock.close(); await unlink(lockPath); })();
      return closing;
    } };
  } catch (error) { await lock.close(); await unlink(lockPath); throw error; }
}
