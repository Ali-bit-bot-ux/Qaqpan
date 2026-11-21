import { useQuery } from "@tanstack/react-query";
import { apiPrefix } from "./api-origin.mjs";
import type { components } from "../app/schema";

export type Transfer = components["schemas"]["TransferResponse"];

export const capabilities = {
  coolingTimer: (transfer: Transfer) =>
    typeof transfer.cooling_seconds_left === "number" &&
    Number.isFinite(transfer.cooling_seconds_left)
      ? Math.max(0, transfer.cooling_seconds_left)
      : null,
  verifyWhileWaiting: false,
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
  get validationFields(): string[] {
    if (this.status !== 422 || !Array.isArray(this.detail)) return [];
    return [
      ...new Set<string>(
        this.detail.flatMap((issue) => {
          const field = Array.isArray(issue?.loc) ? issue.loc[1] : undefined;
          return typeof field === "string" ? [field] : [];
        }),
      ),
    ];
  }
  field(name: string) {
    return this.validationFields.includes(name);
  }
}

export const apiPath = (path: string) => apiPrefix + path;

export async function api<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(apiPath(path), {
    method: body === undefined ? "GET" : "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    cache: "no-store",
  });
  if (!res.ok) {
    const payload = await res.json().catch(() => null);
    throw new ApiError(res.status, payload?.detail, path);
  }
  return res.json();
}

type OpenApi = {
  paths?: Record<
    string,
    {
      get?: { parameters?: Array<{ name: string; description?: string }> };
      post?: unknown;
    }
  >;
};
export function useBackendCapabilities() {
  const { data } = useQuery<OpenApi>({
    queryKey: ["backend-schema"],
    queryFn: async () => {
      const response = await fetch("/api/schema");
      if (!response.ok) throw Error(String(response.status));
      return response.json();
    },
    staleTime: 300_000,
    retry: false,
  });
  const paths = data?.paths;
  const split = paths?.[apiPath("/benchmark/simulate")]?.get?.parameters?.find(
    (parameter) => parameter.name === "split",
  );
  return {
    analystReview: Boolean(
      paths?.[apiPath("/analyst/transfers/{transfer_id}/review")]?.post,
    ),
    continueAfterCooling: Boolean(
      paths?.[apiPath("/transfers/{transfer_id}/confirm")]?.post,
    ),
    holdout3: /\bholdout3\b/.test(split?.description ?? ""),
  };
}
