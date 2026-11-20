"use client";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, ErrorBox, useText } from "./shared";
const labels: Record<string, [string, string]> = {
  CREATED: ["Клиент оформил перевод", "Клиент аударым жасады"],
  AWAITING_ANSWER: [
    "Банк запросил цель перевода",
    "Банк аударым мақсатын сұрады",
  ],
  ANSWERED: [
    "Клиент ответил на вопрос банка",
    "Клиент банктің сұрағына жауап берді",
  ],
  TRUSTED_PENDING: [
    "Запрос направлен доверенному лицу",
    "Сұрау сенімді тұлғаға жіберілді",
  ],
  TRUSTED_APPROVED: [
    "Близкий подтвердил. Деньги отправлены",
    "Жақыныңыз растады. Ақша жіберілді",
  ],
  BLOCKED: [
    "Близкий отклонил. Деньги не отправлены",
    "Жақыныңыз қабылдамады. Ақша жіберілген жоқ",
  ],
  CANCELLED: ["Клиент отменил перевод", "Клиент аударымнан бас тартты"],
  COMPLETED: ["Деньги отправлены получателю", "Ақша алушыға жіберілді"],
  MANUAL_BANK_REVIEW: [
    "Клиент запросил проверку банка",
    "Клиент банк тексерісін сұрады",
  ],
  COOLING_OFF: [
    "Время ожидания истекло. Деньги не отправлены",
    "Күту уақыты аяқталды. Ақша жіберілген жоқ",
  ],
};
export default function TransferHistory({
  id,
  status,
  expanded = false,
}: {
  id: string;
  status: string;
  expanded?: boolean;
}) {
  const t = useText(),
    [open, setOpen] = useState(expanded);
  const query = useQuery({
    queryKey: ["transfer-history", id, status],
    queryFn: () =>
      api<{ kind: string; at: string }[]>("/transfers/" + id + "/history"),
    enabled: open,
    retry: false,
  });
  return (
    <details
      className="transfer-history"
      open={open}
      onToggle={(e) => setOpen(e.currentTarget.open)}
    >
      <summary>{t("Ход перевода", "Аударым барысы")}</summary>
      {open && (
        <>
          {query.isLoading && <p>…</p>}
          <ol>
            {query.data?.map((step, i) => {
              const date = new Date(
                /Z$|[+-]\d\d:\d\d$/.test(step.at) ? step.at : step.at + "Z",
              );
              return (
                <li key={i}>
                  <time dateTime={date.toISOString()}>
                    {date.toLocaleString(t("ru-KZ", "kk-KZ"), {
                      day: "2-digit",
                      month: "2-digit",
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </time>
                  {labels[step.kind] ? t(...labels[step.kind]) : step.kind}
                </li>
              );
            })}
          </ol>
          <ErrorBox error={query.error} />
        </>
      )}
    </details>
  );
}
