"use client";
import { useSyncExternalStore } from "react";

function subscribe(callback: () => void) {
  window.addEventListener("storage", callback);
  window.addEventListener("qaqpan-storage", callback);
  return () => {
    window.removeEventListener("storage", callback);
    window.removeEventListener("qaqpan-storage", callback);
  };
}

export function useStoredValue(
  key: string,
  kind: "localStorage" | "sessionStorage",
) {
  const value = useSyncExternalStore(
    subscribe,
    () => window[kind].getItem(key) ?? "",
    () => "",
  );
  return [
    value,
    (next: string) => {
      window[kind].setItem(key, next);
      window.dispatchEvent(new Event("qaqpan-storage"));
    },
  ] as const;
}
