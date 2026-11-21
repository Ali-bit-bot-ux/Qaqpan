"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import {
  QueryClient,
  QueryClientProvider,
  useQueryClient,
} from "@tanstack/react-query";
import { apiPath } from "../lib/api";
import { apiOrigin } from "../lib/api-origin.mjs";

const Connection = createContext<"connecting" | "online" | "offline">(
  "connecting",
);
const delays = [1000, 2000, 5000];
const events = [
  "transfer_created",
  "transfer_updated",
  "transfer_cancelled",
  "trusted_approved",
  "trusted_declined",
  "trusted_timeout",
  "bank_review_decided",
  "transfer_confirmed_by_client",
  "trap_message",
  "trap_recipient",
  "trap_recipient_decision",
  "trap_session_timeout",
];

function LiveConnection({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<"connecting" | "online" | "offline">(
    "connecting",
  );
  const cache = useQueryClient();
  useEffect(() => {
    let source: EventSource | undefined;
    let retry: ReturnType<typeof setTimeout> | undefined;
    let attempt = 0;
    let active = true;

    const refresh = () => {
      void cache.invalidateQueries({
        predicate: (query) =>
          query.queryKey[0] !== "backend-schema" ||
          query.state.status === "error",
      });
    };

    const connect = () => {
      const stream = new EventSource(
        apiOrigin + apiPath("/transfers/stream/events"),
      );
      source = stream;
      stream.onopen = () => {
        if (!active || source !== stream) return;
        attempt = 0;
        setStatus("online");
        refresh();
      };
      stream.onerror = () => {
        if (!active || source !== stream) return;
        stream.close();
        source = undefined;
        setStatus("offline");
        const delay = delays[Math.min(attempt, delays.length - 1)];
        attempt += 1;
        retry = setTimeout(connect, delay);
      };
      for (const event of events) stream.addEventListener(event, refresh);
    };

    connect();
    return () => {
      active = false;
      clearTimeout(retry);
      source?.close();
    };
  }, [cache]);
  return <Connection.Provider value={status}>{children}</Connection.Provider>;
}

export function useConnection() {
  return useContext(Connection);
}

export function useFallbackPolling() {
  const status = useConnection();
  return {
    refetchInterval: status === "online" ? (false as const) : 15_000,
    refetchIntervalInBackground: true,
  };
}

export default function AppProvider({ children }: { children: ReactNode }) {
  const [cache] = useState(() => new QueryClient());
  return (
    <QueryClientProvider client={cache}>
      <LiveConnection>{children}</LiveConnection>
    </QueryClientProvider>
  );
}
