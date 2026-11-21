"use client";
import { ChevronRight, Clock3, ListChecks, X } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { dateValue, seedTransferNames } from "../lib/account";
import { riskLabels, signalCopy } from "../lib/analyst-copy";
import { api, ApiError, useBackendCapabilities } from "../lib/api";
import { profile } from "../lib/profile-data";
import { useProfile } from "../lib/profile";
import { Badge, Money, Skeleton } from "./ui";
import TransferHistory from "./TransferHistory";
import { useState } from "react";
import {
  useAction,
  useData,
  useSaved,
  useText,
  Models,
  ErrorBox,
  Clock,
  useStatusLabel,
  Status,
} from "./shared";
import Trap from "./Trap";
import Simulator from "./Simulator";
type Case = Models["AnalystCard"];
const previewCopy = {
  real: ["Реальные", "Нақты"],
  training: ["Учебные", "Оқу"],
  dataset: ["Источник данных", "Дерек көзі"],
  source: ["Источник", "Дереккөз"],
  label: ["Учебные данные", "Оқу деректері"],
  recipient: ["Получатель", "Алушы"],
  amount: ["Сумма", "Сома"],
  risk: ["Риск", "Тәуекел"],
  status: ["Статус", "Күй"],
} as const;

const trainingTransfers = [
  {
    name: ["Данияр Садыков", "Данияр Садықов"],
    amount: 250_000,
    risk: "HIGH",
    status: "BLOCKED",
  },
  {
    name: ["Айгерим К.", "Айгерім К."],
    amount: 12_000,
    risk: "LOW",
    status: "COMPLETED",
  },
  {
    name: ["Арман А.", "Арман А."],
    amount: 85_000,
    risk: "MEDIUM",
    status: "AWAITING_ANSWER",
  },
] as const;

const sources = ["ALL", "TRANSFER", "TRAP"];
const tiers = ["LOW", "MEDIUM", "HIGH", "CRITICAL"] as const;
const transferStates = [
  "AWAITING_ANSWER",
  "TRUSTED_PENDING",
  "COOLING_OFF",
  "MANUAL_BANK_REVIEW",
  "COMPLETED",
  "BLOCKED",
  "CANCELLED",
];
const trapStates = ["ACTIVE", "STOPPED", "TIMEOUT"];
const periods = { "24h": 1, "7d": 7, "30d": 30 };
const priority = { LOW: 1, MEDIUM: 2, HIGH: 3, CRITICAL: 4 };

const recipientNames = new Set(
  [
    ...seedTransferNames,
    ...profile.name,
    ...profile.trustedName,
    ...profile.contacts.flatMap((contact) => [...contact.name]),
  ].map((name) => name.toLowerCase()),
);

const activeQueueStatuses = new Set<string>([
  "WAITING_TRUSTED",
  "TRUSTED_PENDING",
  "COOLING",
  "MANUAL_BANK_REVIEW",
]);
const waitingForTrusted = (status: string) =>
  status === "WAITING_TRUSTED" || status === "TRUSTED_PENDING";

function looksLikeTestName(value: string) {
  const name = value.trim().toLowerCase();
  return /^\S{1,6}$/u.test(name) && !recipientNames.has(name);
}

function SignalChips({ signals }: { signals: string[] }) {
  const t = useText();
  const labels = [
    ...new Map(
      signals.map((signal) => {
        const [label] = signalCopy(signal);
        return [label[0], label] as const;
      }),
    ).values(),
  ];
  return (
    <div className="analyst-signals">
      {labels.slice(0, 2).map((label) => (
        <span key={label[0]}>{t(...label)}</span>
      ))}
      {labels.length > 2 && (
        <small>
          {t("ещё", "тағы")} {labels.length - 2}
        </small>
      )}
    </div>
  );
}

function Risk({ value }: { value: Case["risk_tier"] }) {
  const t = useText();
  return value ? (
    <span className="analyst-risk" data-level={value}>
      {t(...riskLabels[value])}
    </span>
  ) : (
    <span aria-label={t("Без оценки", "Бағаланбаған")}>—</span>
  );
}

function TrainingPreview() {
  const t = useText();
  const label = ([ru, kz]: readonly [string, string]) => t(ru, kz);
  return (
    <div className="analyst-table-wrap">
      <table
        className="analyst-table analyst-preview-table"
        aria-label={t(...previewCopy.label)}
      >
        <thead>
          <tr>
            {(["recipient", "amount", "risk", "status", "source"] as const).map(
              (key) => (
                <th key={key} scope="col">
                  {label(previewCopy[key])}
                </th>
              ),
            )}
          </tr>
        </thead>
        <tbody>
          {trainingTransfers.map((row) => (
            <tr key={row.name[0]}>
              <td>{label(row.name)}</td>
              <td>
                <Money amount={row.amount} />
              </td>
              <td>
                <Risk value={row.risk} />
              </td>
              <td>
                <Status value={row.status} />
              </td>
              <td>
                <Badge>{t(...previewCopy.label)}</Badge>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function CaseClock({ id }: { id: string }) {
  const t = useText();
  const { data } = useData<Models["TransferResponse"]>("/transfers/" + id);
  return (
    <span className="analyst-sla">
      <Clock3 size={13} aria-hidden="true" />
      {t("До ответа", "Жауапқа дейін")}{" "}
      {data &&
      waitingForTrusted(data.status) &&
      data.updated_at &&
      data.timeout_seconds != null ? (
        <Clock updated={data.updated_at} seconds={data.timeout_seconds} />
      ) : (
        "—"
      )}
    </span>
  );
}

function CasePanel({
  entry,
  close,
  openTrap,
}: {
  entry: Case;
  close: () => void;
  openTrap: (id: string) => void;
}) {
  const t = useText();
  const isTrap = entry.source === "TRAP";
  const { data } = useData<Models["TransferResponse"]>(
    isTrap ? "" : "/transfers/" + entry.transfer_id,
  );
  const rationale = t(
    data?.alert_reason_ru || entry.explanation || "",
    data?.alert_reason_kz || "",
  );
  const backend = useBackendCapabilities();
  const action = useAction();
  const [comment, setComment] = useState("");
  const reviewAvailable =
    backend.analystReview && entry.status === "MANUAL_BANK_REVIEW";
  const review = (decision: Models["DecisionType"]) =>
    action.mutate(async () => {
      const body: Models["BankReviewDecisionRequest"] = {
        decision,
        comment: comment.trim() || null,
      };
      await api<Models["TransferResponse"]>(
        "/analyst/transfers/" + entry.transfer_id + "/review",
        body,
      );
      setComment("");
    });
  return (
    <aside className="analyst-case">
      <div className="analyst-case-head">
        <h2>{t("Карточка дела", "Іс карточкасы")}</h2>
        <button
          type="button"
          onClick={close}
          aria-label={t("Закрыть дело", "Істі жабу")}
        >
          <X size={17} aria-hidden="true" />
        </button>
      </div>
      <div className="analyst-case-body">
        {isTrap ? (
          <>
            <h3>{t("Диалог-ловушка", "Тұзақ диалогы")}</h3>
            <Status value={entry.status} />
            {entry.dialogue_excerpt?.length ? (
              <blockquote>{entry.dialogue_excerpt.at(-1)}</blockquote>
            ) : null}
            {entry.session_id && (
              <button onClick={() => openTrap(entry.session_id!)}>
                {t("Открыть диалог", "Диалогты ашу")}
              </button>
            )}
          </>
        ) : (
          <>
            <strong className="analyst-case-amount">
              <Money amount={entry.amount} />
            </strong>
            <p className="analyst-payee">{entry.recipient_name}</p>
            <div className="analyst-labels">
              <Risk value={entry.risk_tier} />
              <Status value={entry.status} />
            </div>
            <TransferHistory
              id={entry.transfer_id}
              status={entry.status}
              expanded
            />
            <h3>{t("Сигналы и причины", "Белгілер мен себептер")}</h3>
            {entry.signals?.length ? (
              <ul className="analyst-evidence">
                {entry.signals.map((signal, index) => {
                  const [label, description] = signalCopy(signal);
                  return (
                    <li key={index}>
                      <strong>{t(...label)}</strong>
                      <span>{t(...description)}</span>
                    </li>
                  );
                })}
              </ul>
            ) : (
              <p>{t("Сигналов проверки нет.", "Тексеру белгілері жоқ.")}</p>
            )}
            {rationale && (
              <details>
                <summary>
                  {t("Обоснование банка", "Банктің негіздемесі")}
                  <ChevronRight
                    className="details-chevron"
                    size={16}
                    aria-hidden="true"
                  />
                </summary>
                <p>{rationale}</p>
              </details>
            )}
            <h3>{t("Ответ клиента", "Клиент жауабы")}</h3>
            {entry.client_answer ? (
              <blockquote>{entry.client_answer}</blockquote>
            ) : (
              <p>{t("Ответа клиента нет.", "Клиент жауабы жоқ.")}</p>
            )}
          </>
        )}
      </div>
      {!isTrap && (
        <div className="analyst-review">
          <label>
            {t("Причина решения", "Шешімнің себебі")}
            <textarea
              rows={2}
              aria-invalid={
                action.error instanceof ApiError &&
                action.error.field("comment")
              }
              aria-describedby="review-unavailable"
              placeholder={t(
                "Укажите, что подтвердилось при проверке",
                "Тексеруде не расталғанын көрсетіңіз",
              )}
            />
          </label>
          <div>
            <button
              type="button"
              disabled={!reviewAvailable || action.isPending}
              aria-describedby={
                reviewAvailable ? undefined : "review-unavailable"
              }
              onClick={() => review("APPROVE")}
            >
              {t("Одобрить", "Мақұлдау")}
            </button>
            <button
              type="button"
              disabled={!reviewAvailable || action.isPending}
              aria-describedby={
                reviewAvailable ? undefined : "review-unavailable"
              }
              onClick={() => review("DECLINE")}
            >
              {t("Отклонить", "Қабылдамау")}
            </button>
          </div>
          {!reviewAvailable && (
            <small id="review-unavailable">
              {backend.analystReview
                ? t(
                    "Дело не ожидает решения банка.",
                    "Іс банк шешімін күтпейді.",
                  )
                : t(
                    "Отправка решения банка пока недоступна.",
                    "Банк шешімін жіберу әзірге қолжетімсіз.",
                  )}
            </small>
          )}
          <ErrorBox error={action.error} />
        </div>
      )}
    </aside>
  );
}

export default function Analyst() {
  const t = useText();
  const statusLabel = useStatusLabel();
  const { clientId, displayName } = useProfile();
  const filters = useSearchParams();
  const source =
    sources.find((value) => value === filters.get("source")) ?? "ALL";
  const risk = tiers.find((value) => value === filters.get("risk")) ?? "";
  const status =
    [...transferStates, ...trapStates].find(
      (value) => value === filters.get("status"),
    ) ?? "";
  const period = Object.keys(periods).find(
    (value) => value === filters.get("period"),
  ) as keyof typeof periods | undefined;
  const updateFilter = (key: string, value: string) => {
    const next = new URLSearchParams(filters.toString());
    if (value) next.set(key, value);
    else next.delete(key);
    if (key === "source") {
      next.delete("status");
      if (value === "TRAP") next.delete("risk");
    }
    const query = next.toString();
    window.history.replaceState(
      null,
      "",
      window.location.pathname + (query ? "?" + query : ""),
    );
  };
  const [id, select] = useSaved("qaqpan-trap");
  const [selected, setSelected] = useState<string>();
  const [training, setTraining] = useState(false);
  const [now] = useState(Date.now);
  const trapFilter = trapStates.includes(status);
  const hideTest = filters.get("test") !== "show";
  const q = useData<Models["AnalystFeedResponse"]>(
    "/analyst/feed?" +
      new URLSearchParams({
        source,
        ...(source !== "TRAP" && risk ? { risk_tier: risk } : {}),
        ...(source !== "TRAP" && transferStates.includes(status)
          ? { status }
          : {}),
      }),
  );
  const cards =
    q.data?.cards.filter(
      (c) =>
        (!hideTest ||
          c.source !== "TRANSFER" ||
          !looksLikeTestName(c.recipient_name)) &&
        (!period ||
          +dateValue(c.created_at) >= now - periods[period] * 86_400_000) &&
        (!trapFilter || c.status === status) &&
        (source !== "TRAP" || !status || c.status === status),
    ) ?? [];
  const transfers = cards.filter((card) => card.source === "TRANSFER");
  const queue = transfers
    .filter((c) => c.source === "TRANSFER" && activeQueueStatuses.has(c.status))
    .sort(
      (left, right) =>
        priority[right.risk_tier ?? "LOW"] -
          priority[left.risk_tier ?? "LOW"] ||
        +dateValue(left.created_at) - +dateValue(right.created_at),
    );
  const entry =
    selected === ""
      ? undefined
      : (cards.find((c) => c.transfer_id === selected) ??
        queue[0] ??
        transfers[0]);
  const clock = new Intl.DateTimeFormat(t("ru-KZ", "kk-KZ"), {
    timeZone: "Asia/Almaty",
    hour: "2-digit",
    minute: "2-digit",
  });
  const date = new Intl.DateTimeFormat(t("ru-KZ", "kk-KZ"), {
    timeZone: "Asia/Almaty",
    day: "2-digit",
    month: "2-digit",
  });
  const counts = [
    [t("Всего", "Барлығы"), cards.length],
    [
      t("Высокий риск", "Жоғары тәуекел"),
      cards.filter((c) => c.risk_tier === "HIGH" || c.risk_tier === "CRITICAL")
        .length,
    ],
    [
      t("Ждут близкого", "Жақынын күтуде"),
      cards.filter((c) => waitingForTrusted(c.status)).length,
    ],
    [
      t("Проверка банка", "Банк тексерісі"),
      cards.filter((c) => c.status === "MANUAL_BANK_REVIEW").length,
    ],
  ] as const;
  return (
    <>
      <div className="analyst-workspace">
        <aside className="analyst-queue">
          <h2>
            <ListChecks size={17} aria-hidden="true" />
            {t("Очередь дел", "Істер кезегі")}
          </h2>
          {!queue.length && (
            <p>{t("Активных дел нет", "Белсенді істер жоқ")}</p>
          )}
          <ul>
            {queue.map((c) => (
              <li key={c.transfer_id}>
                <button
                  type="button"
                  aria-pressed={entry?.transfer_id === c.transfer_id}
                  onClick={() => setSelected(c.transfer_id)}
                >
                  <Risk value={c.risk_tier} />
                  <Money amount={c.amount} />
                  <span className="analyst-queue-payee">
                    {c.recipient_name}
                  </span>
                  <span className="analyst-queue-status">
                    {statusLabel(c.status)}
                  </span>
                  {waitingForTrusted(c.status) ? (
                    <CaseClock id={c.transfer_id} />
                  ) : (
                    <span className="analyst-sla">
                      <Clock3 size={13} aria-hidden="true" />
                      {t("Срок не задан", "Мерзім көрсетілмеген")}
                    </span>
                  )}
                </button>
              </li>
            ))}
          </ul>
        </aside>
        <div className="analyst-primary">
          <div className="analyst-center">
            <div className="analyst-counts">
              {counts.map(([label, count]) => (
                <span key={label}>
                  {label} <b>{q.data ? count : "—"}</b>
                </span>
              ))}
            </div>
            <div
              className="analyst-dataset"
              role="group"
              aria-label={t(...previewCopy.dataset)}
            >
              <button
                type="button"
                aria-pressed={!training}
                onClick={() => setTraining(false)}
              >
                {t(...previewCopy.real)}
              </button>
              <button
                type="button"
                aria-pressed={training}
                onClick={() => setTraining(true)}
              >
                {t(...previewCopy.training)}
              </button>
            </div>
            {training && <TrainingPreview />}
            <div className="analyst-live" hidden={training}>
              <div className="analyst-filters">
                <label>
                  {t("Источник", "Дереккөз")}
                  <select
                    value={source}
                    onChange={(event) =>
                      updateFilter(
                        "source",
                        event.target.value === "ALL" ? "" : event.target.value,
                      )
                    }
                  >
                    <option value="ALL">{t("Все", "Барлығы")}</option>
                    <option value="TRANSFER">
                      {t("Переводы", "Аударымдар")}
                    </option>
                    <option value="TRAP">{t("Ловушки", "Тұзақтар")}</option>
                  </select>
                </label>
                <label>
                  {t("Риск", "Тәуекел")}
                  <select
                    disabled={source === "TRAP"}
                    value={risk}
                    onChange={(event) =>
                      updateFilter("risk", event.target.value)
                    }
                  >
                    <option value="">{t("Все", "Барлығы")}</option>
                    {tiers.map((level) => (
                      <option key={level} value={level}>
                        {level === "CRITICAL"
                          ? t("Критический", "Сындарлы")
                          : t(...riskLabels[level])}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  {t("Статус", "Күй")}
                  <select
                    value={status}
                    onChange={(event) =>
                      updateFilter("status", event.target.value)
                    }
                  >
                    <option value="">{t("Все", "Барлығы")}</option>
                    {(source === "TRAP"
                      ? trapStates
                      : source === "TRANSFER"
                        ? transferStates
                        : [...transferStates, ...trapStates]
                    ).map((value) => (
                      <option key={value} value={value}>
                        {statusLabel(value)}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  {t("Период", "Кезең")}
                  <select
                    value={period ?? ""}
                    onChange={(event) =>
                      updateFilter("period", event.target.value)
                    }
                  >
                    <option value="">{t("Всё время", "Барлық уақыт")}</option>
                    <option value="24h">{t("24 часа", "24 сағат")}</option>
                    <option value="7d">{t("7 дней", "7 күн")}</option>
                    <option value="30d">{t("30 дней", "30 күн")}</option>
                  </select>
                </label>
              </div>
              <label className="analyst-test-filter">
                <input
                  type="checkbox"
                  checked={hideTest}
                  onChange={(event) =>
                    updateFilter("test", event.target.checked ? "" : "show")
                  }
                />
                {t("Скрыть тестовые", "Сынақ жазбаларын жасыру")}
              </label>
              <ErrorBox error={q.error} />
              {q.isPending && <Skeleton />}
              {q.data && !transfers.length && (
                <p className="analyst-empty">
                  {t(
                    "По выбранным фильтрам записей нет.",
                    "Таңдалған сүзгілер бойынша жазбалар жоқ.",
                  )}
                </p>
              )}
              {transfers.length > 0 && (
                <div className="analyst-table-wrap">
                  <table className="analyst-table">
                    <colgroup>
                      <col className="col-time" />
                      <col className="col-person" />
                      <col className="col-amount" />
                      <col className="col-payee" />
                      <col className="col-risk" />
                      <col className="col-state" />
                      <col className="col-signals" />
                    </colgroup>
                    <thead>
                      <tr>
                        {[
                          t("Время", "Уақыт"),
                          t("Клиент", "Клиент"),
                          t("Сумма", "Сома"),
                          t("Получатель", "Алушы"),
                          t("Риск", "Тәуекел"),
                          t("Статус", "Күй"),
                          t("Сигналы", "Белгілер"),
                        ].map((label) => (
                          <th key={label} scope="col">
                            {label}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {transfers.map((c) => (
                        <tr
                          key={c.transfer_id}
                          data-selected={entry?.transfer_id === c.transfer_id}
                          onClick={() => setSelected(c.transfer_id)}
                        >
                          <td>
                            <time dateTime={c.created_at}>
                              {clock.format(dateValue(c.created_at))}
                              <small>
                                {date.format(dateValue(c.created_at))}
                              </small>
                            </time>
                          </td>
                          <td>
                            {c.source === "TRAP"
                              ? "—"
                              : c.client_id === clientId
                                ? t(...displayName)
                                : t("Клиент", "Клиент")}
                          </td>
                          <td>
                            {c.source === "TRAP" ? (
                              "—"
                            ) : (
                              <Money amount={c.amount} />
                            )}
                          </td>
                          <td>
                            <button
                              type="button"
                              className="analyst-row-button"
                              aria-pressed={
                                entry?.transfer_id === c.transfer_id
                              }
                            >
                              {c.source === "TRAP"
                                ? t("Диалог-ловушка", "Тұзақ диалогы")
                                : c.recipient_name}
                            </button>
                          </td>
                          <td>
                            <Risk value={c.risk_tier} />
                          </td>
                          <td title={statusLabel(c.status)}>
                            <Status value={c.status} />
                          </td>
                          <td>
                            <SignalChips signals={c.signals ?? []} />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
          <Simulator />
        </div>
        {entry ? (
          <CasePanel
            key={entry.transfer_id}
            entry={entry}
            close={() => setSelected("")}
            openTrap={(trapId) => {
              select(trapId);
              document.getElementById("analyst-trap")?.scrollIntoView();
            }}
          />
        ) : (
          <aside className="analyst-case analyst-empty">
            {t(
              "Выберите операцию, чтобы открыть дело.",
              "Істі ашу үшін операцияны таңдаңыз.",
            )}
          </aside>
        )}
      </div>
      <div id="analyst-trap">
        <Trap id={id} select={select} />
      </div>
    </>
  );
}
