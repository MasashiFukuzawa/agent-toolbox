import type { Page } from "playwright";

export const protocolVersion = 1;
export type Status = "verified" | "failed" | "needs_agent" | "needs_human" | "blocked";
export type Effect = "read" | "write" | "human";
export type Kind = "click" | "fill" | "select" | "check" | "upload";
export interface Rule {
  name: string;
  kind: Kind;
  effect: Effect;
  selector?: string;
  labelIsAlias?: boolean;
  values?: Record<string, string>;
}
export interface Goal {
  id: string;
  instruction: string;
  rules: Rule[];
}
export interface Candidate {
  id: string;
  ref: string;
  name: string;
  kind: Kind;
  effect: Effect;
  valueId?: string;
}
export interface Observation { epoch: number; candidates: Candidate[]; satisfiedInputs?: {name: string; kind: Kind; valueId: string}[]; }
export interface Decision { action: string; confidence: number; blocker: boolean; inputTokens: number; outputTokens: number; }
export interface Decider {
  decide(goal: string, observation: Observation): Promise<Decision>;
}
export interface Adapter {
  origin: string;
  scopeSelector: string;
  context(): Promise<boolean>;
  verify(goal: Goal): Promise<boolean>;
  authorize(candidate: Candidate): Promise<boolean>;
  /** True requires every dispatched external mutation to be durably committed or known not dispatched. Pending/202/timeout must be false. Local input editing alone need not satisfy the goal. */
  afterAction(candidate: Candidate): Promise<boolean>;
  file?(candidate: Candidate, value: string): Promise<{name: string; mimeType: string; buffer: Buffer}>;
}
export interface Event {
  phase: "observe" | "decide" | "act" | "verify";
  ms: number;
  inputTokens?: number;
  outputTokens?: number;
  actionId?: string;
  confidence?: number;
  blocker?: boolean;
}
export interface Result { elapsedMs?: number; status: Status; reason: string; goalId: string; events: Event[]; }
export interface Session {
  observe(goal: Goal): Promise<Observation>;
  act(goal: Goal, epoch: number, actionId: string): Promise<Result>;
  run(goal: Goal, decider: Decider): Promise<Result>;
  checklist(goals: Goal[], decider: Decider): Promise<Result[]>;
  close(): Promise<void>;
}
export interface Limits { actions: number; milliseconds: number; candidates: number; minConfidence: number; }
export type SessionFactory = (page: Page, adapter: Adapter, limits?: Partial<Limits>) => Session;
