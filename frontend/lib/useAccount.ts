"use client";

import { useFallbackPolling } from "../app/AppProvider";
import { useQuery } from "@tanstack/react-query";
import { accountSnapshot, type Entry } from "./account";
import type { Transfer } from "./api";

export function useAccount(active?: Transfer) {
  const fallback = useFallbackPolling();
  const history = useQuery<Entry[]>({
    queryKey: ["account-history"],
    queryFn: async () => {
      const response = await fetch("/api/account", { cache: "no-store" });
      if (!response.ok) throw new Error(String(response.status));
      return response.json();
    },
    ...fallback,
    retry: false,
  });
  const current = active?.created_at
    ? { ...active, created_at: active.created_at }
    : undefined;
  const snapshot = history.data
    ? accountSnapshot(history.data, current)
    : undefined;
  return { history, snapshot };
}
