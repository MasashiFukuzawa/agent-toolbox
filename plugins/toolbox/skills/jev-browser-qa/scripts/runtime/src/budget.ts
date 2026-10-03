export interface Ledger { limitJPY: number; committedJPY: number; paidGrants?: string[]; }

/** Reserve before dispatch. Uncertain requests retain their full reservation. */
export class Budget {
  readonly ledger: Ledger;
  readonly persist: (ledger: Ledger) => Promise<void>;
  #busy = false;
  #closed = false;
  invalidate(): void { this.#closed = true; }
  constructor(ledger: Ledger, persist: (ledger: Ledger) => Promise<void>) {
    if (!Number.isFinite(ledger.limitJPY) || ledger.limitJPY <= 0 || ledger.limitJPY > 500 ||
        !Number.isFinite(ledger.committedJPY) || ledger.committedJPY < 0 || ledger.committedJPY > ledger.limitJPY) {
      throw new Error("blocked_budget");
    }
    this.ledger = { ...ledger };
    this.persist = persist;
  }
  async reserve(maximumJPY: number): Promise<(actualJPY: number) => Promise<void>> {
    if (this.#closed || this.#busy || !Number.isFinite(maximumJPY) || maximumJPY <= 0 ||
        this.ledger.committedJPY + maximumJPY > this.ledger.limitJPY) throw new Error("blocked_budget");
    this.#busy = true;
    this.ledger.committedJPY += maximumJPY;
    try { await this.persist({ ...this.ledger }); } catch { throw new Error("blocked_budget_persistence"); }
    if (this.#closed) throw new Error("blocked_budget_closed");
    let settled = false;
    return async (actualJPY) => {
      if (this.#closed || settled || !Number.isFinite(actualJPY) || actualJPY < 0 || actualJPY > maximumJPY) {
        throw new Error("blocked_budget_usage");
      }
      settled = true;
      this.ledger.committedJPY -= maximumJPY - actualJPY;
      await this.persist({ ...this.ledger });
      this.#busy = false;
    };
  }
}
