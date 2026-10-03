import assert from "node:assert/strict";
import {test} from "node:test";
import {mkdtemp, chmod, rm} from "node:fs/promises";
import {tmpdir} from "node:os";
import {join} from "node:path";
import {openBudget, writePrivateFile, readPrivateFile} from "../src/private-files.ts";
test("closed ledger owners cannot write or remove a successor lock", async () => {
  const root = await mkdtemp(join(tmpdir(), "jev-ledger-"));
  await chmod(root, 0o700);
  try {
    const path = join(root, "ledger.json");
    await writePrivateFile(path, JSON.stringify({limitJPY:500, committedJPY:0}));
    const first = await openBudget(path), settle = await first.budget.reserve(1);
    await first.close();
    const second = await openBudget(path);
    await assert.rejects(settle(0), /blocked_budget_usage/);
    await assert.rejects(first.budget.reserve(1), /blocked_budget/);
    await first.close();
    await assert.rejects(openBudget(path), /blocked_budget_lock/);
    assert.equal(JSON.parse(await readPrivateFile(path)).committedJPY, 1);
    await second.close();
  } finally { await rm(root, {recursive:true, force:true}); }
});
