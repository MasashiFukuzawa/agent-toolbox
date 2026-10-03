import { createServer } from "node:http";
import { chromium } from "playwright";
import type { Adapter, Decider, Goal, Result } from "./contracts.ts";
import { createSession } from "./session.ts";

export const fixtureHtml = `<!doctype html><html lang="ja"><meta charset="utf-8"><title>Synthetic QA fixture</title>
<main><label>合成名称<input aria-label="合成名称"></label><button id="save">保存</button><output id="saved"></output>
<button id="details">履歴を開く</button><section id="history" hidden>合成履歴</section>
<label>合成分類<select aria-label="合成分類"><option value="one">一</option><option value="two">二</option></select></label>
<label>合成選択<input type="checkbox" aria-label="合成選択"></label>
<button id="human">AIを実行</button><div id="private">PRIVATE CONTENT MUST NOT BE SENT</div></main>
<script>
let saved=''; document.querySelector('#save').onclick=()=>{saved=document.querySelector('input').value;document.querySelector('#saved').textContent=saved};
document.querySelector('#details').onclick=()=>document.querySelector('#history').hidden=false;
</script></html>`;
export const fixtureGoals: Goal[] = [
  { id: "synthetic-save", instruction: "Set the synthetic name to the supplied value and save it.", rules: [
    { name: "合成名称", kind: "fill", effect: "write", values: { synthetic: "QA-SYNTHETIC" } }, { name: "保存", kind: "click", effect: "write" }] },
  { id: "synthetic-history", instruction: "Open the synthetic history.", rules: [{ name: "履歴を開く", kind: "click", effect: "read" }] },
  { id: "synthetic-select", instruction: "Select synthetic category two.", rules: [{ name: "合成分類", kind: "select", effect: "write", values: { two: "two" } }] },
  { id: "synthetic-check", instruction: "Check the synthetic selection.", rules: [{ name: "合成選択", kind: "check", effect: "write", values: { checked: "true" } }] },
  { id: "synthetic-human", instruction: "Start the AI task after human review.", rules: [{ name: "AIを実行", kind: "click", effect: "human" }] },
];

/** The scripted decider exercises plumbing only; it is never a model benchmark. */
export function scriptedFixtureDecider(): Decider {
  const counts = new Map<string, number>();
  return { async decide(goal, observation) {
    const count = counts.get(goal) ?? 0;
    counts.set(goal, count + 1);
    const desiredKind = goal.includes("save") && count === 0 ? "fill" : "click";
    const candidate = observation.candidates.find(c => c.kind === desiredKind) ?? observation.candidates[0];
    return { action: candidate?.id ?? "handoff", confidence: 1, blocker: false, inputTokens: 0, outputTokens: 0 };
  } };
}
export async function withFixture<T>(use: (page: import("playwright").Page, adapter: Adapter, origin: string) => Promise<T>): Promise<T> {
  const server = createServer((_req, response) => { response.writeHead(200, { "content-type": "text/html; charset=utf-8" }); response.end(fixtureHtml); });
  await new Promise<void>(resolve => server.listen(0, "127.0.0.1", resolve));
  const address = server.address();
  if (!address || typeof address === "string") throw new Error("fixture_address");
  const origin = `http://127.0.0.1:${address.port}`;
  let browser: Awaited<ReturnType<typeof chromium.launch>> | undefined;
  try {
    browser = await chromium.launch();
    const context = await browser.newContext({ viewport: { width: 1100, height: 800 } });
    const page = await context.newPage();
    await page.goto(origin);
    const adapter: Adapter = { origin, scopeSelector: "main", context: async () => true,
      authorize: async () => true, afterAction: async () => true,
      async verify(goal) {
        if (goal.id === "synthetic-save") return await page.locator("#saved").textContent() === "QA-SYNTHETIC";
        if (goal.id === "synthetic-history") return page.locator("#history").isVisible();
        if (goal.id === "synthetic-select") return await page.locator("select").inputValue() === "two";
        if (goal.id === "synthetic-check") return page.locator("input[type=checkbox]").isChecked();
        return false;
      } };
    return await use(page, adapter, origin);
  } finally { await browser?.close(); await new Promise<void>((resolve, reject) => server.close(error => error ? reject(error) : resolve())); }
}
export async function runFixture(decider: Decider = scriptedFixtureDecider(), labels: "native" | "normalized" = "native"): Promise<Result[]> {
  const aliases: Record<string, {name: string; selector: string}> = {
    "合成名称": {name: "Synthetic name", selector: "input[aria-label=合成名称]"},
    "保存": {name: "Save synthetic name", selector: "#save"},
    "履歴を開く": {name: "Open synthetic history", selector: "#details"},
    "合成分類": {name: "Synthetic category", selector: "select"},
    "合成選択": {name: "Synthetic checkbox", selector: "input[type=checkbox]"},
    "AIを実行": {name: "Start AI task", selector: "#human"},
  };
  const goals = labels === "native" ? fixtureGoals : fixtureGoals.map(goal => ({...goal,
    rules: goal.rules.map(rule => ({...rule, ...aliases[rule.name], labelIsAlias: true})),
  }));
  return withFixture(async (page, adapter) => {
    const session = createSession(page, adapter);
    try { const results: Result[] = []; for (const goal of goals) results.push(await session.run(goal, decider)); return results; } finally { await session.close(); }
  });
}
