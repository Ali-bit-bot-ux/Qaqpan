"use client";
import { createContext, useContext, useEffect, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { ApiError } from "../lib/api";
import { useStoredValue } from "../lib/storage";
import type { components } from "./schema";
export type Models = components["schemas"];
export const Language = createContext(false);
export function useText() {
  const kz = useContext(Language);
  return (ru: string, kk: string) => (kz ? kk : ru);
}
export async function api<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch("/api/v1" + path, {
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
export function useData<T>(path: string) {
  return useQuery({
    queryKey: [path],
    queryFn: () => api<T>(path),
    enabled: !!path,
    refetchInterval: 15000,
    retry: false,
  });
}
export function useAction() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (fn: () => Promise<void>) => fn(),
    onSettled: () => qc.invalidateQueries(),
  });
}
export function Sync() {
  const qc = useQueryClient();
  useEffect(() => {
    const es = new EventSource("/api/v1/transfers/stream/events");
    let pending: ReturnType<typeof setTimeout> | undefined;
    const refresh = () => {
      if (pending !== undefined) return;
      pending = setTimeout(() => {
        pending = undefined;
        void qc.invalidateQueries();
      }, 150);
    };
    for (const event of "open transfer_created transfer_updated transfer_cancelled trusted_approved trusted_declined trusted_timeout trap_message trap_recipient trap_recipient_decision trap_session_timeout".split(
      " ",
    ))
      es.addEventListener(event, refresh);
    return () => {
      clearTimeout(pending);
      es.close();
    };
  }, [qc]);
  return null;
}
export function useSaved(key: string) {
  return useStoredValue(key, "sessionStorage");
}
const states: Record<string, [string, string]> = {
  COMPLETED: ["Перевод выполнен", "Аударым орындалды"],
  BLOCKED: ["Перевод остановлен", "Аударым тоқтатылды"],
  CANCELLED: ["Перевод отменён", "Аударым жойылды"],
  TRUSTED_PENDING: ["Ожидаем решения близкого", "Жақыныңыздың жауабын күтеміз"],
  AWAITING_ANSWER: ["Уточните цель перевода", "Аударым мақсатын нақтылаңыз"],
  COOLING_OFF: ["Близкий не ответил", "Жақыныңыз жауап бермеді"],
  MANUAL_BANK_REVIEW: ["На проверке банка", "Банк тексеруде"],
  ACTIVE: ["Диалог открыт", "Диалог ашық"],
  STOPPED: ["Диалог завершён", "Диалог аяқталды"],
  TIMEOUT: ["Время истекло", "Уақыт аяқталды"],
  NEW: ["На проверке", "Тексерілуде"],
  CONFIRMED: ["Подтверждено", "Расталды"],
  REJECTED: ["Отклонено", "Қабылданбады"],
};
export function Status({ value }: { value: string }) {
  const t = useText();
  return (
    <strong className="status">
      {states[value] ? t(...states[value]) : value}
    </strong>
  );
}
export function ErrorBox({ error }: { error: Error | null }) {
  const t = useText();
  return error ? (
    <p role="alert">
      {error.message === "409"
        ? t(
            "Статус изменился. Проверьте обновлённые данные.",
            "Күй өзгерді. Деректерді тексеріңіз.",
          )
        : t(
            "Не удалось выполнить запрос. Проверьте подключение к API.",
            "Сұрау орындалмады. API байланысын тексеріңіз.",
          )}{" "}
      ({error.message})
    </p>
  ) : null;
}
const numberFormat = new Intl.NumberFormat("ru-KZ");
export const money = (n: number) => numberFormat.format(n) + " ₸";

export function Clock({
  updated,
  seconds,
}: {
  updated: string;
  seconds: number;
}) {
  const [now, setNow] = useState(Date.now);
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);
  const timestamp = /Z$|[+-]\d\d:\d\d$/.test(updated) ? updated : updated + "Z";
  const left = Math.max(
    0,
    Math.ceil((Date.parse(timestamp) + seconds * 1000 - now) / 1000),
  );
  return (
    <time>
      {Math.floor(left / 60)}:{String(left % 60).padStart(2, "0")}
    </time>
  );
}
