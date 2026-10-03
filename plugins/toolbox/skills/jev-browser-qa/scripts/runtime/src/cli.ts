import { open, stat } from "node:fs/promises";
import { resolve } from "node:path";
import { parseArgs } from "node:util";
import { runFixture } from "./fixture.ts";
import { createJevDecider, model } from "./typesafe.ts";
import { openBudget, readPrivateFile, requireOutsideCheckout } from "./private-files.ts";

const { values, positionals } = parseArgs({ allowPositionals: true, options: {
  provider: { type: "string", default: "scripted" }, labels: {type: "string", default: "native"}, key: { type: "string" }, ledger: { type: "string" },
  "yen-per-usd-upper-bound": { type: "string" }, "input-usd-per-million-upper-bound": {type: "string"}, "pricing-expires-at": {type: "string"}, mode: { type: "string", default: "batched" }
} });
try {
  if (positionals[0] === "budget-init") {
    if (!values.ledger) throw new Error("blocked_budget");
    await requireOutsideCheckout(values.ledger);
    const directory = await stat(resolve(values.ledger, ".."));
    if (directory.mode & 0o077 || directory.uid !== process.getuid?.()) throw new Error("blocked_private_directory");
    const handle = await open(values.ledger, "wx", 0o600);
    try { await handle.writeFile(JSON.stringify({limitJPY: 500, committedJPY: 0})); await handle.sync(); }
    finally { await handle.close(); }
    console.log(JSON.stringify({status: "verified", reason: "budget_initialized_once"}));
  } else {
  if (positionals[0] !== "fixture" || positionals.length !== 1) throw new Error("blocked_command");
  if (values.provider !== "jev" && values.provider !== "jev-playground" && values.provider !== "scripted") throw new Error("blocked_provider");
  if (values.mode !== "batched" && values.mode !== "sequential") throw new Error("blocked_mode");
  let close: (() => Promise<void>) | undefined;
  try {
    let decider;
    let committedBeforeJPY: number | undefined;
    let paidLedger: import("./budget.ts").Ledger | undefined;
    if (values.provider !== "scripted") {
      if (!values.key || !values.ledger || !values["yen-per-usd-upper-bound"]) throw new Error("blocked_budget");
      const key = await readPrivateFile(values.key!);
      const opened = await openBudget(values.ledger);
      close = opened.close;
      paidLedger = opened.budget.ledger;
      committedBeforeJPY = paidLedger.committedJPY;
      decider = createJevDecider(key.trim(), opened.budget, Number(values["yen-per-usd-upper-bound"]), values.mode, values.provider === "jev-playground" ? "independent-playground" : "official", {provider: values.provider === "jev-playground" ? "independent-playground" : "official", inputUsdPerMillionUpperBound: Number(values["input-usd-per-million-upper-bound"]), outputUsdPerMillionUpperBound: 0, expiresAt: values["pricing-expires-at"] ?? ""});
    }
    if (values.labels !== "native" && values.labels !== "normalized") throw new Error("blocked_labels");
    const results = await runFixture(decider, values.labels);
    console.log(JSON.stringify({ kind: "synthetic-fixture", provider: values.provider,
      labels: values.labels, mode: values.mode, committedJPY: paidLedger?.committedJPY ?? null, costDeltaJPY: paidLedger ? paidLedger.committedJPY - committedBeforeJPY! : 0, model: values.provider !== "scripted" ? model : null, benchmark: false, results }, null, 2));
    if (results.some(r => r.status !== "verified" && !(r.goalId === "synthetic-human" && r.status === "needs_human"))) process.exitCode = 1;
  } finally { await close?.(); }
  }
} catch (error) {
  const reason = error instanceof Error && /^blocked_[a-z0-9_]+$/.test(error.message) ? error.message : "blocked_setup";
  console.log(JSON.stringify({ status: "blocked", reason })); process.exitCode = 1;
}
