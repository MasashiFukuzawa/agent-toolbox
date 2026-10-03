import type { ElementHandle, JSHandle, Page } from "playwright";
import type { Adapter, Candidate, Goal, Limits, Observation, Result, Session, Decider, Event } from "./contracts.ts";

const pageLocks = new WeakSet<Page>();
const unresolvedWrites = new WeakSet<Page>();
const runningOwners = new WeakMap<Page, symbol>();

type SnapshotEntry = { ref: string; ruleIndex: number; name: string; currentValueId?: string; };
export function createSession(page: Page, adapter: Adapter, options: Partial<Limits> = {}): Session {
  const limits = { actions: 40, milliseconds: 60_000, candidates: 200, minConfidence: 0.9, ...options };
  if (!Number.isSafeInteger(limits.actions) || limits.actions <= 0 || !Number.isFinite(limits.milliseconds) || limits.milliseconds <= 0 ||
      !Number.isSafeInteger(limits.candidates) || limits.candidates <= 0 || !Number.isFinite(limits.minConfidence) || limits.minConfidence < 0 || limits.minConfidence > 1) throw new Error("blocked_limits");
  const sessionOwner = Symbol("session");
  const origin = adapter.origin, scopeSelector = adapter.scopeSelector;
  let epoch = 0;
  let active: { goal: Goal; observation: Observation; rules: Map<string, import("./contracts.ts").Rule>; store: JSHandle; } | undefined;

  const releaseSnapshot = async () => { const previous = active; active = undefined; await previous?.store.dispose(); };
  async function context() {
    const url = page.url();
    if (adapter.origin !== origin || adapter.scopeSelector !== scopeSelector || new URL(url).origin !== origin) return false;
    const valid = await adapter.context();
    return valid && page.url() === url && new URL(page.url()).origin === origin && adapter.origin === origin && adapter.scopeSelector === scopeSelector;
  }
  async function observe(goal: Goal, internal = false): Promise<Observation> {
    if (runningOwners.has(page) && (!internal || runningOwners.get(page) !== sessionOwner)) throw new Error("blocked_concurrent_operation");
    if (pageLocks.has(page)) throw new Error("blocked_concurrent_operation");
    pageLocks.add(page);
    let pendingStore: JSHandle | undefined;
    try {
    await releaseSnapshot();
    if (goal.rules.some(rule => rule.labelIsAlias && !rule.selector)) throw new Error("blocked_alias_selector");
    if (!await context()) throw new Error("blocked_context");
    const store = await page.evaluateHandle(({ scope, rules, limit }) => {
      const roots = Array.from(document.querySelectorAll(scope));
      const refs = new Map<string, { node: Element; fingerprint: string; ruleIndex: number; }>();
      const entries: { ref: string; ruleIndex: number; name: string; currentValueId?: string; }[] = [];
      const nameOf = (node: Element) => {
        const ids = node.getAttribute("aria-labelledby")?.split(/\s+/).filter(Boolean) ?? [];
        return (node.getAttribute("aria-label") ?? (ids.length ? ids.map((id: string) => document.getElementById(id)?.textContent ?? "").join(" ") :
          (node instanceof HTMLInputElement || node instanceof HTMLTextAreaElement || node instanceof HTMLSelectElement ?
            Array.from(node.labels ?? []).map(label => label.textContent ?? "").join(" ") || node.getAttribute("placeholder") || "" : node.textContent ?? ""))).replace(/\s+/g, " ").trim();
      };
      const fingerprint = (node: Element) => JSON.stringify([node.tagName, nameOf(node), node.getAttribute("role"),
        node.getAttribute("href"), node.getAttribute("type"), node.getAttribute("aria-expanded"), Array.from(node.attributes as NamedNodeMap, attr => [attr.name, attr.value]), node.closest("form")?.getAttribute("action"), node.parentElement?.textContent,
        "value" in node ? node.value : null, "checked" in node ? node.checked : null,
        roots.flatMap(root => Array.from(root.querySelectorAll("input,textarea,select"), field => [field.tagName, field.getAttribute("name"), "value" in field ? field.value : null, "checked" in field ? field.checked : null]))]);
      rules.forEach((rule, ruleIndex) => {
        const selector = rule.selector ?? "button,a,input,textarea,select,[role=button],[role=tab],[role=menuitem],[role=checkbox],[role=option],[role=treeitem]";
        const matched: Element[] = [];
        for (const node of new Set(roots.flatMap(root => [...(root.matches(selector) ? [root] : []), ...root.querySelectorAll(selector)]))) {
          if ((!rule.labelIsAlias && nameOf(node) !== rule.name) || node instanceof HTMLInputElement && node.type === "password" ||
              node.closest("[inert],[aria-hidden=true]") || node.getAttribute("aria-disabled") === "true" || node.matches(":disabled") ||
              node.getBoundingClientRect().width === 0 || node.getBoundingClientRect().height === 0 || getComputedStyle(node).visibility !== "visible") continue;
          if ((rule.kind === "fill" && !(node instanceof HTMLInputElement || node instanceof HTMLTextAreaElement)) ||
              (rule.kind === "select" && !(node instanceof HTMLSelectElement)) ||
              (rule.kind === "upload" && !(node instanceof HTMLInputElement && node.type === "file"))) continue;
          matched.push(node);
        }
        if (matched.length > 1) throw new Error("blocked_ambiguous_rule");
        for (const node of matched) {
          const ref = `r${entries.length}`;
          refs.set(ref, { node, fingerprint: fingerprint(node), ruleIndex });
          const value = rule.kind === "check" && node instanceof HTMLInputElement ? String(node.checked) : "value" in node ? node.value : undefined;
          const currentValueId = Object.entries(rule.values ?? {}).find(([, supplied]) => supplied === value)?.[0];
          entries.push({ ref, ruleIndex, name: rule.name, currentValueId });
          if (entries.length > limit) throw new Error("blocked_candidate_limit");
        }
      });
      return { refs, entries, url: location.href, roots, scope, rules };
    }, { scope: scopeSelector, rules: goal.rules, limit: limits.candidates });
    pendingStore = store;
    const entries: SnapshotEntry[] = await store.evaluate(value => value.entries);
    const candidates: Candidate[] = [];
    const ruleByAction = new Map<string, import("./contracts.ts").Rule>();
    for (const entry of entries) {
      const rule = goal.rules[entry.ruleIndex];
      const valueIds = rule.kind === "click" ? [undefined] : Object.keys(rule.values ?? {}).filter(id => id !== entry.currentValueId);
      for (const valueId of valueIds) {
        const id = `a${candidates.length}`;
        candidates.push({ id, ref: entry.ref, name: entry.name, kind: rule.kind, effect: rule.effect, valueId });
        ruleByAction.set(id, { ...rule, values: { ...rule.values } });
      }
    }
    if (candidates.length > limits.candidates) throw new Error("blocked_candidate_limit");
    const satisfiedInputs = entries.filter(entry => entry.currentValueId !== undefined).map(entry => ({name: entry.name, kind: goal.rules[entry.ruleIndex].kind, valueId: entry.currentValueId!}));
    const observation = { epoch: ++epoch, candidates, satisfiedInputs };
    active = { goal, observation, rules: ruleByAction, store };
    pendingStore = undefined;
    return structuredClone(observation);
    } finally { await pendingStore?.dispose(); pageLocks.delete(page); }
  }
  const result = (goal: Goal, status: Result["status"], reason: string, events: Event[] = []): Result => ({ goalId: goal.id, status, reason, events });
  async function act(goal: Goal, observedEpoch: number, actionId: string, internal = false): Promise<Result> {
    if (runningOwners.has(page) && (!internal || runningOwners.get(page) !== sessionOwner)) return result(goal, "blocked", "concurrent_action");
    if (pageLocks.has(page)) return result(goal, "blocked", "concurrent_action");
    pageLocks.add(page);
    let held: JSHandle | undefined;
    let writeDispatched = false;
    try {
      const snapshot = active;
      active = undefined;
      held = snapshot?.store;
      const candidate = snapshot?.observation.candidates.find(c => c.id === actionId);
      if (snapshot?.goal !== goal || snapshot.observation.epoch !== observedEpoch || !candidate) return result(goal, "needs_agent", "stale_or_unknown_action");
      if (!await context()) return result(goal, "blocked", "context_changed");
      if (unresolvedWrites.has(page) && candidate.effect === "write") return result(goal, "blocked", "unresolved_write");
      if (candidate.effect === "human") return result(goal, "needs_human", "human_checkpoint");
      if (!await adapter.authorize(candidate)) return result(goal, "blocked", "action_denied");
      if (!await context()) return result(goal, "blocked", "context_changed_after_authorize");
      const rule = snapshot.rules.get(actionId);
      if (!rule) return result(goal, "blocked", "rule_changed");
      const value = candidate.valueId === undefined ? undefined : rule.values?.[candidate.valueId];
      if (candidate.kind === "upload" && !adapter.file) return result(goal, "blocked", "upload_bytes_required");
      const file = candidate.kind === "upload" && adapter.file ? await adapter.file(candidate, value!) : undefined;
      if (candidate.kind === "upload" && (!file || typeof file !== "object" || typeof file.name !== "string" || !file.name || typeof file.mimeType !== "string" || !Buffer.isBuffer(file.buffer))) return result(goal, "blocked", "upload_bytes_required");
      if (!await context()) return result(goal, "blocked", "context_changed_after_file");
      const handle = await snapshot.store.evaluateHandle((store, ref) => {
        const entry = store?.refs.get(ref);
        if (!entry || !entry.node.isConnected || store?.url !== location.href) return null;
        const node = entry.node;
        const rule = store.rules[entry.ruleIndex];
        if (!store.roots.some((root: Element) => root.isConnected && root.matches(store.scope) && (root === node || root.contains(node))) || (rule.selector && !node.matches(rule.selector))) return null;
        const ids = node.getAttribute("aria-labelledby")?.split(/\s+/).filter(Boolean) ?? [];
        const name = (node.getAttribute("aria-label") ?? (ids.length ? ids.map((id: string) => document.getElementById(id)?.textContent ?? "").join(" ") :
          (node instanceof HTMLInputElement || node instanceof HTMLTextAreaElement || node instanceof HTMLSelectElement ?
            Array.from(node.labels ?? []).map(label => label.textContent ?? "").join(" ") || node.getAttribute("placeholder") || "" : node.textContent ?? ""))).replace(/\s+/g, " ").trim();
        const fingerprint = JSON.stringify([node.tagName, name, node.getAttribute("role"), node.getAttribute("href"), node.getAttribute("type"), node.getAttribute("aria-expanded"), Array.from(node.attributes as NamedNodeMap, attr => [attr.name, attr.value]), node.closest("form")?.getAttribute("action"), node.parentElement?.textContent,
          "value" in node ? node.value : null, "checked" in node ? node.checked : null,
          store.roots.flatMap((root: Element) => Array.from(root.querySelectorAll("input,textarea,select"), field => [field.tagName, field.getAttribute("name"), "value" in field ? field.value : null, "checked" in field ? field.checked : null]))]);
        if (fingerprint !== entry.fingerprint || node.matches(":disabled") || node.getAttribute("aria-disabled") === "true" || node.closest("[inert],[aria-hidden=true]")) return null;
        const rect = node.getBoundingClientRect();
        const x = Math.max(0, rect.left) + Math.min(rect.width, innerWidth - Math.max(0, rect.left)) / 2;
        const y = Math.max(0, rect.top) + Math.min(rect.height, innerHeight - Math.max(0, rect.top)) / 2;
        const top = document.elementFromPoint(x, y);
        if (!rect.width || !rect.height || getComputedStyle(node).visibility !== "visible" || !top || top !== node && !node.contains(top)) return null;
        return node;
      }, candidate.ref);
      const node = handle.asElement() as ElementHandle<HTMLElement> | null;
      if (!node) { await handle.dispose(); return result(goal, "needs_agent", "stale_or_obscured_target"); }
      const started = performance.now();
      try {
        writeDispatched = candidate.effect === "write";
        if (candidate.kind === "click") await node.click({ timeout: 3000 });
        else if (candidate.kind === "fill") await node.fill(value!, { timeout: 3000 });
        else if (candidate.kind === "select") await node.selectOption(value!, { timeout: 3000 });
        else if (candidate.kind === "check") await node.setChecked(value === "true", { timeout: 3000 });
        else { if (!file) throw new Error("blocked_upload_bytes_required"); await node.setInputFiles(file, { timeout: 3000 }); }
      } catch { if (candidate.effect === "write") unresolvedWrites.add(page); return result(goal, "needs_agent", "action_outcome_unknown", [{phase: "act", ms: performance.now() - started, actionId}]); }
      finally { await node.dispose(); }
      const events: Event[] = [{ phase: "act", ms: performance.now() - started, actionId }];
      if (!await context()) { if (candidate.effect === "write") unresolvedWrites.add(page); return result(goal, "blocked", "context_changed_after_action", events); }
      if (!await adapter.afterAction(candidate)) { if (candidate.effect === "write") unresolvedWrites.add(page); return result(goal, "failed", "postcondition_failed", events); }
      if (!await context()) return result(goal, "blocked", "context_changed_after_postcheck", events);
      writeDispatched = false;
      return result(goal, "needs_agent", "action_applied", events);
    } finally { if (writeDispatched) unresolvedWrites.add(page); await held?.dispose(); pageLocks.delete(page); }
  }
  async function runInternal(goal: Goal, decider: Decider): Promise<Result> {
    const events: Event[] = [];
    const started = performance.now();
    for (let count = 0; count <= limits.actions; count++) {
      try {
        if (!await context()) return result(goal, "blocked", "context_changed", events);
        const verifyStart = performance.now();
        const verified = await adapter.verify(goal);
        events.push({ phase: "verify", ms: performance.now() - verifyStart });
        if (!await context()) return result(goal, "blocked", "context_changed_after_verify", events);
        if (verified) return result(goal, "verified", "independent_postcondition", events);
        if (unresolvedWrites.has(page)) return result(goal, "blocked", "unresolved_write", events);
        if (count === limits.actions) return result(goal, "needs_agent", "action_limit", events);
        if (performance.now() - started >= limits.milliseconds) return result(goal, "needs_agent", "time_limit", events);
        const observationStart = performance.now();
        const observation = await observe(goal, true);
        events.push({ phase: "observe", ms: performance.now() - observationStart });
        if (!observation.candidates.length) return result(goal, "needs_agent", "no_permitted_controls", events);
        if (observation.candidates.every(candidate => candidate.effect === "human")) return result(goal, "needs_human", "human_checkpoint", events);
        const decisionStart = performance.now();
        const decision = await decider.decide(goal.instruction, observation);
        events.push({ phase: "decide", ms: performance.now() - decisionStart, inputTokens: decision.inputTokens, outputTokens: decision.outputTokens, actionId: decision.action, confidence: decision.confidence, blocker: decision.blocker });
        if (performance.now() - started >= limits.milliseconds) return result(goal, "needs_agent", "time_limit", events);
        if (!Number.isFinite(decision.confidence) || decision.confidence < limits.minConfidence || decision.confidence > 1 || decision.blocker || decision.action === "handoff") return result(goal, "needs_agent", "uncertain_or_blocked", events);
        const applied = await act(goal, observation.epoch, decision.action, true);
        events.push(...applied.events);
        if (applied.reason !== "action_applied") return { ...applied, events };
      } catch (error) {
        const reason = error instanceof Error && /^blocked_[a-z0-9_]+$/.test(error.message) ? error.message : "operation_failed";
        return result(goal, "blocked", reason, events);
      }
    }
    return result(goal, "needs_agent", "action_limit", events);
  }
  async function run(goal: Goal, decider: Decider): Promise<Result> {
    if (runningOwners.has(page) || pageLocks.has(page)) return result(goal, "blocked", "concurrent_run");
    runningOwners.set(page, sessionOwner);
    const started = performance.now();
    try {
      const answer = await runInternal(goal, decider);
      return {...answer, elapsedMs: performance.now() - started};
    } finally { runningOwners.delete(page); }
  }
  return { observe: goal => observe(goal), act: (goal, epoch, id) => act(goal, epoch, id), run, async checklist(goals, decider) {
    const results: Result[] = [];
    for (const goal of goals) { const answer = await run(goal, decider); results.push(answer); if (answer.status !== "verified") break; }
    return results;
  }, async close() { if (runningOwners.has(page) || pageLocks.has(page)) throw new Error("blocked_concurrent_operation"); await releaseSnapshot(); } };
}
