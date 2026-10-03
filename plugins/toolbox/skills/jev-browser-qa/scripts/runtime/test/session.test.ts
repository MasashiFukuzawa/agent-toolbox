import assert from "node:assert/strict";
import { test } from "node:test";
import { Budget } from "../src/budget.ts";
import { createSession } from "../src/session.ts";
import { fixtureGoals, runFixture, withFixture } from "../src/fixture.ts";
import type { Decider } from "../src/contracts.ts";
const pickFirst: Decider = { async decide(_goal, observation) { return { action: observation.candidates[0]?.id ?? "handoff", confidence: 1, blocker: false, inputTokens: 0, outputTokens: 0 }; } };

test("synthetic checklist verifies four effects and stops before the human AI action", async () => {
  const results = await runFixture();
  assert.deepEqual(results.map(r => r.status), ["verified", "verified", "verified", "verified", "needs_human"]);
});
test("observation contains only explicitly named controls, never page bodies or field values", async () => {
  await withFixture(async (page, adapter) => {
    await page.locator("input[aria-label='合成名称']").fill("PRIVATE FIELD");
    const observed = await createSession(page, adapter).observe(fixtureGoals[0]);
    assert(!JSON.stringify(observed).includes("PRIVATE"));
    assert.equal(observed.candidates.length, 2);
  });
});
test("replaced controls are not re-resolved by label and clicked", async () => {
  await withFixture(async (page, adapter) => {
    const session = createSession(page, adapter);
    const goal = fixtureGoals[1];
    const observation = await session.observe(goal);
    await page.locator("#details").evaluate(node => node.replaceWith(node.cloneNode(true)));
    const result = await session.act(goal, observation.epoch, observation.candidates[0].id);
    assert.equal(result.reason, "stale_or_obscured_target");
    assert.equal(await page.locator("#history").isVisible(), false);
  });
});
test("an overlay stops input before the click", async () => {
  await withFixture(async (page, adapter) => {
    const session = createSession(page, adapter);
    const goal = fixtureGoals[1];
    const observation = await session.observe(goal);
    await page.evaluate(() => { const overlay = document.createElement("div"); overlay.style.cssText = "position:fixed;inset:0;z-index:999;background:white"; document.body.append(overlay); });
    assert.equal((await session.act(goal, observation.epoch, observation.candidates[0].id)).reason, "stale_or_obscured_target");
  });
});
test("unknown action IDs and reused epochs never execute", async () => {
  await withFixture(async (_page, adapter) => {
    const session = createSession(_page, adapter);
    const goal = fixtureGoals[1];
    const observed = await session.observe(goal);
    assert.equal((await session.act(goal, observed.epoch, "invented-selector")).reason, "stale_or_unknown_action");
    assert.equal((await session.act(goal, observed.epoch, observed.candidates[0].id)).reason, "stale_or_unknown_action");
  });
});
test("a model saying handoff cannot mark a failed save verified", async () => {
  await withFixture(async (page, adapter) => {
    await page.locator("#save").evaluate(node => { (node as HTMLElement).onclick = () => {}; });
    const result = await createSession(page, adapter, { actions: 2 }).run(fixtureGoals[0], pickFirst);
    assert.notEqual(result.status, "verified");
  });
});
test("context change between observation and action prevents mutation", async () => {
  await withFixture(async (page, adapter) => {
    let valid = true;
    const session = createSession(page, { ...adapter, context: async () => valid });
    const goal = fixtureGoals[0]; const observed = await session.observe(goal); valid = false;
    assert.equal((await session.act(goal, observed.epoch, observed.candidates[0].id)).status, "blocked");
    assert.equal(await page.locator("input[aria-label='合成名称']").inputValue(), "");
  });
});
test("low confidence hands off before a mutation", async () => {
  await withFixture(async (page, adapter) => {
    const result = await createSession(page, adapter).run(fixtureGoals[0], { async decide(_goal, observed) {
      return { action: observed.candidates[0].id, confidence: 0.5, blocker: false, inputTokens: 0, outputTokens: 0 };
    } });
    assert.equal(result.reason, "uncertain_or_blocked");
    assert.equal(await page.locator("input[aria-label='合成名称']").inputValue(), "");
  });
});
test("budget reservation survives an uncertain request and rejects a second overspend", async () => {
  const budget = new Budget({ limitJPY: 2, committedJPY: 0 }, async () => {});
  await budget.reserve(1.5);
  await assert.rejects(() => budget.reserve(1), /blocked_budget/);
  assert.equal(budget.ledger.committedJPY, 1.5);
});
test("known usage settles a reservation without exceeding the total ceiling", async () => {
  const budget = new Budget({ limitJPY: 2, committedJPY: 0 }, async () => {});
  const settle = await budget.reserve(1.5); await settle(0.25);
  assert.equal(budget.ledger.committedJPY, 0.25);
  await assert.rejects(() => settle(0), /blocked_budget_usage/);
});
test("disabled and human controls cannot be auto-executed", async () => {
  await withFixture(async (page, adapter) => {
    const session = createSession(page, adapter);
    const goal = fixtureGoals[4];
    assert.equal((await session.run(goal, pickFirst)).status, "needs_human");
    await page.locator("#human").evaluate(node => node.setAttribute("disabled", ""));
    assert.equal((await session.observe(goal)).candidates.length, 0);
  });
});

test("an adapter alias distinguishes duplicate visible labels without sending their surrounding text", async () => {
  await withFixture(async (page, adapter) => {
    await page.evaluate(() => {
      const button = document.createElement("button"); button.id = "unrelated"; button.textContent = "履歴を開く"; document.querySelector("main")!.append(button);
    });
    const goal = { ...fixtureGoals[1], rules: [{ name: "synthetic target", kind: "click" as const, effect: "read" as const, selector: "#details", labelIsAlias: true }] };
    const session = createSession(page, adapter);
    const observed = await session.observe(goal);
    assert.equal(observed.candidates.length, 1);
    const answer = await session.act(goal, observed.epoch, observed.candidates[0].id);
    assert.equal(answer.reason, "action_applied");
    assert.equal(await page.locator("#history").isVisible(), true);
  });
});
test("password inputs never become model candidates, even when a matching rule is supplied", async () => {
  await withFixture(async (page, adapter) => {
    await page.evaluate(() => { const input = document.createElement("input"); input.type = "password"; input.setAttribute("aria-label", "Synthetic password"); document.querySelector("main")!.append(input); });
    const goal = { id: "password", instruction: "Fill", rules: [{ name: "Synthetic password", kind: "fill" as const, effect: "write" as const, values: { value: "synthetic-only" } }] };
    assert.equal((await createSession(page, adapter).observe(goal)).candidates.length, 0);
  });
});

test("separate sessions retain their own DOM references", async () => {
  await withFixture(async (page, adapter) => {
    const first = createSession(page, adapter), second = createSession(page, adapter);
    const observed = await first.observe(fixtureGoals[1]);
    await second.observe(fixtureGoals[0]);
    assert.equal((await first.act(fixtureGoals[1], observed.epoch, observed.candidates[0].id)).reason, "action_applied");
    assert.equal(await page.locator("#history").isVisible(), true);
    assert.equal(await page.locator("input[aria-label='合成名称']").inputValue(), "");
    await first.close(); await second.close();
  });
});
test("input edits invalidate a previously observed save button", async () => {
  await withFixture(async (page, adapter) => {
    const session = createSession(page, adapter);
    const observed = await session.observe(fixtureGoals[0]);
    await page.locator("input[aria-label='合成名称']").fill("UNEXPECTED");
    const save = observed.candidates.find(candidate => candidate.kind === "click")!;
    assert.equal((await session.act(fixtureGoals[0], observed.epoch, save.id)).reason, "stale_or_obscured_target");
    assert.equal(await page.locator("#saved").textContent(), "");
  });
});
test("a concurrent observation cannot replace targets during authorization", async () => {
  await withFixture(async (page, adapter) => {
    let release!: () => void;
    let entered!: () => void;
    const authorized = new Promise<void>(resolve => { entered = resolve; });
    const gate = new Promise<void>(resolve => { release = resolve; });
    const session = createSession(page, {...adapter, authorize: async () => { entered(); await gate; return true; }});
    const observed = await session.observe(fixtureGoals[1]);
    const pending = session.act(fixtureGoals[1], observed.epoch, observed.candidates[0].id);
    await authorized;
    await assert.rejects(() => session.observe(fixtureGoals[0]), /blocked_concurrent_operation/);
    release();
    assert.equal((await pending).reason, "action_applied");
  });
});
test("context is rechecked after asynchronous authorization", async () => {
  await withFixture(async (page, adapter) => {
    let valid = true;
    const session = createSession(page, {...adapter, context: async () => valid, authorize: async () => {valid = false; return true;}});
    const observed = await session.observe(fixtureGoals[0]);
    assert.equal((await session.act(fixtureGoals[0], observed.epoch, observed.candidates[0].id)).reason, "context_changed_after_authorize");
    assert.equal(await page.locator("input[aria-label='合成名称']").inputValue(), "");
  });
});
test("unconfirmed write outcomes stop later writes", async () => {
  await withFixture(async (page, adapter) => {
    const session = createSession(page, {...adapter, afterAction: async () => false});
    let observed = await session.observe(fixtureGoals[0]);
    assert.equal((await session.act(fixtureGoals[0], observed.epoch, observed.candidates[0].id)).reason, "postcondition_failed");
    observed = await session.observe(fixtureGoals[0]);
    assert.equal((await session.act(fixtureGoals[0], observed.epoch, observed.candidates[0].id)).reason, "unresolved_write");
    assert.equal(await page.locator("#saved").textContent(), "");
  });
});
test("the final permitted action receives an independent verification", async () => {
  await withFixture(async (page, adapter) => {
    assert.equal((await createSession(page, adapter, {actions: 1}).run(fixtureGoals[1], pickFirst)).status, "verified");
  });
});
test("native synthetic file upload uses a supplied file without exposing its path to Jev", async () => {
  const {mkdtemp, writeFile, readFile, rm} = await import("node:fs/promises");
  const {tmpdir} = await import("node:os");
  const {join} = await import("node:path");
  const directory = await mkdtemp(join(tmpdir(), "jev-upload-"));
  const path = join(directory, "synthetic.txt");
  await writeFile(path, "QA-SYNTHETIC upload");
  try {
    await withFixture(async (page, adapter) => {
      await page.evaluate(() => {const input = document.createElement("input"); input.type="file"; input.setAttribute("aria-label", "Synthetic file"); document.querySelector("main")!.append(input);});
      const goal = {id: "upload", instruction: "Upload the supplied synthetic file", rules:[{name: "Synthetic file", kind: "upload" as const, effect: "write" as const, values: {synthetic_file: path}}]};
      const session = createSession(page, {...adapter, async file() {return {name: "synthetic.txt", mimeType: "text/plain", buffer: await readFile(path)};}});
      const observed = await session.observe(goal);
      assert(!JSON.stringify(observed).includes(path));
      assert.equal((await session.act(goal, observed.epoch, observed.candidates[0].id)).reason, "action_applied");
      assert.equal(await page.locator("input[type=file]").evaluate(input => (input as HTMLInputElement).files?.[0]?.name), "synthetic.txt");
    });
  } finally {await rm(directory, {recursive:true, force:true});}
});

test("ambiguous native labels require a uniquely scoped rule", async () => {
  await withFixture(async (page, adapter) => {
    await page.locator("#details").evaluate(node => node.parentElement!.append(node.cloneNode(true)));
    await assert.rejects(createSession(page, adapter).observe(fixtureGoals[1]), /blocked_ambiguous_rule/);
  });
});
test("target attribute changes invalidate the observed object", async () => {
  await withFixture(async (page, adapter) => {
    const session = createSession(page, adapter);
    const goal = fixtureGoals[1];
    const observed = await session.observe(goal);
    await page.locator("#details").evaluate(node => node.setAttribute("data-object-id", "replacement"));
    assert.equal((await session.act(goal, observed.epoch, observed.candidates[0].id)).reason, "stale_or_obscured_target");
  });
});
test("unknown writes remain stopped when a Session is replaced on the same Page", async () => {
  await withFixture(async (page, adapter) => {
    const guarded = {...adapter, async afterAction() {return false;}};
    const goal = fixtureGoals[0];
    const first = createSession(page, guarded);
    const before = await first.observe(goal);
    await first.act(goal, before.epoch, before.candidates.find(c => c.kind === "fill")!.id);
    await first.close();
    const second = createSession(page, adapter);
    const after = await second.observe(goal);
    assert.equal((await second.act(goal, after.epoch, after.candidates[0].id)).reason, "unresolved_write");
  });
});

test("a cloned goal can reconcile a previous Session's uncertain write", async () => {
  await withFixture(async (page, adapter) => {
    let committed = false;
    const guarded = {...adapter, async verify() {return committed;}, async afterAction() {return false;}};
    const goal = fixtureGoals[0];
    const first = createSession(page, guarded), observed = await first.observe(goal);
    await first.act(goal, observed.epoch, observed.candidates.find(c => c.kind === "fill")!.id);
    await first.close();
    committed = true;
    assert.equal((await createSession(page, guarded).run(structuredClone(goal), pickFirst)).status, "verified");
  });
});
test("checker context changes cannot verify a different target", async () => {
  await withFixture(async (page, adapter) => {
    let valid = true;
    const session = createSession(page, {...adapter, async context() {return valid;}, async verify() {valid = false; return true;}});
    assert.equal((await session.run(fixtureGoals[1], pickFirst)).reason, "context_changed_after_verify");
  });
});
test("a pending run owns the Page through its asynchronous checker", async () => {
  await withFixture(async (page, adapter) => {
    let enter!: () => void, release!: () => void;
    const entered = new Promise<void>(resolve => {enter = resolve;});
    const waiting = new Promise<void>(resolve => {release = resolve;});
    const first = createSession(page, {...adapter, async verify() {enter(); await waiting; return true;}});
    const run = first.run(fixtureGoals[1], pickFirst);
    await entered;
    const second = createSession(page, adapter);
    await assert.rejects(second.observe(fixtureGoals[1]), /blocked_concurrent_operation/);
    await assert.rejects(first.observe(fixtureGoals[1]), /blocked_concurrent_operation/);
    assert.equal((await second.run(fixtureGoals[1], pickFirst)).reason, "concurrent_run");
    release();
    assert.equal((await run).status, "verified");
  });
});

test("an earlier act owns the Page before a run can check it", async () => {
  await withFixture(async (page, adapter) => {
    let enter!: () => void, release!: () => void;
    const entered = new Promise<void>(resolve => {enter = resolve;});
    const waiting = new Promise<void>(resolve => {release = resolve;});
    const first = createSession(page, {...adapter, async authorize() {enter(); await waiting; return true;}});
    const observed = await first.observe(fixtureGoals[0]);
    const act = first.act(fixtureGoals[0], observed.epoch, observed.candidates[0].id);
    await entered;
    assert.equal((await createSession(page, adapter).run(fixtureGoals[1], pickFirst)).reason, "concurrent_run");
    await assert.rejects(first.close(), /blocked_concurrent_operation/);
    release(); await act;
  });
});
test("postcheck context loss retains the write fence", async () => {
  await withFixture(async (page, adapter) => {
    let valid = true;
    const first = createSession(page, {...adapter, async context() {return valid;}, async afterAction() {valid = false; return true;}});
    const observed = await first.observe(fixtureGoals[0]);
    assert.equal((await first.act(fixtureGoals[0], observed.epoch, observed.candidates[0].id)).reason, "context_changed_after_postcheck");
    const second = createSession(page, adapter), after = await second.observe(fixtureGoals[0]);
    assert.equal((await second.act(fixtureGoals[0], after.epoch, after.candidates[0].id)).reason, "unresolved_write");
  });
});
test("a successful checker does not reopen uncertain writes", async () => {
  await withFixture(async (page, adapter) => {
    const first = createSession(page, {...adapter, async afterAction() {return false;}});
    const observed = await first.observe(fixtureGoals[0]);
    await first.act(fixtureGoals[0], observed.epoch, observed.candidates[0].id);
    const second = createSession(page, {...adapter, async verify() {return true;}});
    assert.equal((await second.run(fixtureGoals[0], pickFirst)).status, "verified");
    const after = await second.observe(fixtureGoals[0]);
    assert.equal((await second.act(fixtureGoals[0], after.epoch, after.candidates[0].id)).reason, "unresolved_write");
  });
});

test("a JavaScript path-only upload callback is rejected at runtime", async () => {
  await withFixture(async (page, adapter) => {
    await page.setContent('<main><input type="file" aria-label="Upload"></main>');
    const goal = {id:"upload", instruction:"Upload", rules:[{name:"Upload", kind:"upload" as const, effect:"write" as const, values:{fixture:"fixture"}}]};
    const malformed = {...adapter, file: async () => "not-an-in-memory-payload"} as unknown as Parameters<typeof createSession>[1];
    const session = createSession(page, malformed), observed = await session.observe(goal);
    assert.equal((await session.act(goal, observed.epoch, observed.candidates[0].id)).reason, "upload_bytes_required");
  });
});

test("navigation during asynchronous context checks cannot report verified", async () => {
  await withFixture(async (page, adapter) => {
    let checks = 0;
    const session = createSession(page, {...adapter, async verify() {return true;}, async context() {
      if (++checks === 2) await page.goto("about:blank");
      return true;
    }});
    assert.equal((await session.run(fixtureGoals[1], pickFirst)).reason, "context_changed_after_verify");
  });
});
test("changing adapter scope after observation cannot use the previous target", async () => {
  await withFixture(async (page, adapter) => {
    const session = createSession(page, adapter), observed = await session.observe(fixtureGoals[1]);
    adapter.scopeSelector = "#unrelated";
    assert.equal((await session.act(fixtureGoals[1], observed.epoch, observed.candidates[0].id)).reason, "context_changed");
  });
});
