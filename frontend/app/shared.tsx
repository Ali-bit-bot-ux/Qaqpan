"use client";
import { createContext, useContext, useEffect, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, ApiError } from "../lib/api";
import { useFallbackPolling } from "./AppProvider";
export { api } from "../lib/api";
import { useStoredValue } from "../lib/storage";
import type { components } from "./schema";
export type Models = components["schemas"];
export const Language = createContext(false);
export function useText() {
  const kz = useContext(Language);
  return (ru: string, kk: string) => (kz ? kk : ru);
}
export function useData<T>(path: string) {
  const fallback = useFallbackPolling();
  return useQuery({
    queryKey: [path],
    queryFn: () => api<T>(path),
    enabled: !!path,
    ...fallback,
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
export function useStatusLabel() {
  const t = useText();
  return (value: string) => (states[value] ? t(...states[value]) : value);
}
export function Status({ value }: { value: string }) {
  const label = useStatusLabel();
  return (
    <strong className="status" data-status={value}>
      {label(value)}
    </strong>
  );
}
const validationFields: Record<string, [string, string]> = {
  recipient_name: ["Имя получателя", "Алушының аты"],
  recipient_account: ["Реквизиты получателя", "Алушының деректемелері"],
  amount: ["Сумма", "Сома"],
  answer_text: ["Ответ", "Жауап"],
  warning_acknowledged: ["Подтверждение прочтения", "Оқығанын растау"],
  comment: ["Причина решения", "Шешімнің себебі"],
  text: ["Сообщение", "Хабарлама"],
  decision: ["Решение", "Шешім"],
};

export function ErrorBox({ error }: { error: Error | null }) {
  const t = useText();
  if (!error) return null;
  const code = error instanceof ApiError ? error.status : Number(error.message);
  const messages: Record<number, string> = {
    400: t("Проверьте данные формы", "Нысан деректерін тексеріңіз"),
    404: t("Перевод не найден", "Аударым табылмады"),
    409: t("Статус перевода изменился", "Аударым күйі өзгерді"),
    422: t("Проверьте отмеченные поля", "Белгіленген өрістерді тексеріңіз"),
  };
  const fields = error instanceof ApiError ? error.validationFields : [];
  return (
    <div className="bank-error" role="alert">
      {messages[code] ??
        t(
          "Не удалось выполнить запрос. Попробуйте снова.",
          "Сұрау орындалмады. Қайталап көріңіз.",
        )}
      {fields.length > 0 && (
        <ul>
          {fields.map((name) => (
            <li key={name}>
              {validationFields[name]
                ? t(...validationFields[name])
                : t("Проверьте значение", "Мәнді тексеріңіз")}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
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
