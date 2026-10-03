import assert from "node:assert/strict";
import { test } from "node:test";
import { Budget } from "../src/budget.ts";
import { createJevDecider } from "../src/typesafe.ts";
const pricing = () => ({provider: "independent-playground" as const, inputUsdPerMillionUpperBound: .42, outputUsdPerMillionUpperBound: 0 as const, expiresAt: new Date(Date.now() + 3_600_000).toISOString()});
test("missing or expired provider-bound pricing prevents paid dispatch", () => {
  const budget = new Budget({limitJPY: 500, committedJPY: 0}, async () => {});
  assert.throws(() => createJevDecider("synthetic", budget, 400, "batched", "independent-playground"), /blocked_pricing_authority/);
  assert.throws(() => createJevDecider("synthetic", budget, 400, "batched", "independent-playground", {...pricing(), expiresAt: new Date(0).toISOString()}), /blocked_pricing_authority/);
  assert.equal(budget.ledger.committedJPY, 0);
});
test("a low-confidence clear answer cannot pass the action confidence floor", async () => {
  const original = globalThis.fetch;
  globalThis.fetch = async () => new Response(JSON.stringify({model: "jev-1.13.0", answers: {
    action: {type: "choice", choice: "a0", confidence: .99},
    blocker: {type: "choice", choice: "clear", confidence: .4},
  }, usage: {input_tokens: 4, output_tokens: 1, cost_usd: .000002}}));
  try {
    const budget = new Budget({limitJPY: 500, committedJPY: 0}, async () => {});
    const answer = await createJevDecider("synthetic", budget, 400, "batched", "independent-playground", pricing()).decide("Open history", {epoch: 1, candidates: [{id: "a0", ref: "r0", name: "History", kind: "click", effect: "read"}]});
    assert.equal(answer.confidence, .4);
  } finally {globalThis.fetch = original;}
});
test("pricing authority is copied before the caller can mutate it", async () => {
  const original = globalThis.fetch;
  globalThis.fetch = async () => new Response(JSON.stringify({model: "jev-1.13.0", answers: {
    action: {type: "choice", choice: "a0", confidence: 1}, blocker: {type: "choice", choice: "clear", confidence: 1},
  }, usage: {input_tokens: 4, output_tokens: 1, cost_usd: .000002}}));
  try {
    const budget = new Budget({limitJPY: 500, committedJPY: 0}, async () => {}), authority = pricing();
    const decider = createJevDecider("synthetic", budget, 400, "batched", "independent-playground", authority);
    authority.inputUsdPerMillionUpperBound = 100;
    authority.expiresAt = new Date(0).toISOString();
    await decider.decide("Open", {epoch: 1, candidates: [{id: "a0", ref: "r0", name: "Open", kind: "click", effect: "read"}]});
    assert(Math.abs(budget.ledger.committedJPY - .001072) < .00000001);
  } finally {globalThis.fetch = original;}
});

test("official answers also reject unknown blocker choices in either mode", async () => {
  const original = globalThis.fetch;
  globalThis.fetch = async (_url, init) => {
    const request = JSON.parse(String(init?.body));
    const answers = request.questions.answer ? {answer:{type:"choice", choice: request.questions.answer.criteria.a0 ? "a0" : "invented", confidence:1}} : {
      action:{type:"choice", choice:"a0", confidence:1}, blocker:{type:"choice", choice:"invented", confidence:1},
    };
    return new Response(JSON.stringify({model:"jev-1.13.0", answers, usage:{input_tokens:4, output_tokens:1}}), {headers:{"Content-Type":"application/json"}});
  };
  try {
    for (const mode of ["batched", "sequential"] as const) {
      const budget = new Budget({limitJPY:500, committedJPY:0}, async () => {});
      const authority = {...pricing(), provider:"official" as const, inputUsdPerMillionUpperBound:.042};
      await assert.rejects(createJevDecider("synthetic", budget, 400, mode, "official", authority).decide("Open", {epoch:1,candidates:[{id:"a0",ref:"r0",name:"Open",kind:"click",effect:"read"}]}), /blocked_provider_response/);
    }
  } finally {globalThis.fetch = original;}
});
