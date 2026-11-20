import type { components } from "../app/schema";

type Contract = components["schemas"]["TransferResponse"];
export type Transfer = Contract & { cooling_seconds_left?: number | null };

export const capabilities = {
  coolingTimer: (transfer: Transfer) =>
    typeof transfer.cooling_seconds_left === "number" &&
    Number.isFinite(transfer.cooling_seconds_left)
      ? Math.max(0, transfer.cooling_seconds_left)
      : null,
  continueAfterCooling: false,
  analystReview: false,
  verifyWhileWaiting: false,
  holdout3: false,
} as const;

export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: unknown,
    public path: string,
  ) {
    super(String(status));
    this.name = "ApiError";
  }
  get expiredAnswer() {
    return (
      this.status === 409 &&
      this.path.endsWith("/answer") &&
      typeof this.detail === "string" &&
      /expired|timed out|deadline elapsed|время вышло|срок ист[её]к|уақыт аяқталды/i.test(
        this.detail,
      )
    );
  }
  field(name: string) {
    return (
      this.status === 422 &&
      Array.isArray(this.detail) &&
      this.detail.some(
        (issue) => Array.isArray(issue?.loc) && issue.loc.includes(name),
      )
    );
  }
}
