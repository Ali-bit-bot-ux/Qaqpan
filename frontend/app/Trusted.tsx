"use client";

import { useEffect, useState } from "react";
import { Bell, Clock3, Phone, ShieldCheck } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { dateValue } from "../lib/account";
import { useProfile } from "../lib/profile";
import { useStoredValue } from "../lib/storage";
import { api, useAction, useData, useText, type Models } from "./shared";
import { Badge, Button, Card, ErrorState, Money, Skeleton, Timer } from "./ui";
import TransferHistory from "./TransferHistory";

type Decision = Pick<
  Models["TransferResponse"],
  "transfer_id" | "updated_at" | "recipient_name" | "amount" | "status"
>;
const rules: [RegExp, string, string][] = [
  [
    /безопасн.*сч[её]т|резервн.*сч[её]т/i,
    "«Безопасный счёт»",
    "«Қауіпсіз шот»",
  ],
  [
    /по указанию.*телефону/i,
    "Указания по телефону",
    "Телефон арқылы берілген нұсқау",
  ],
  [/давление|запугивания/i, "Признаки давления", "Қысым белгілері"],
  [/спешка|срочност/i, "Просят поторопиться", "Асықтырып жатыр"],
  [/новому|неизвестному ранее/i, "Новый получатель", "Жаңа алушы"],
  [
    /выше привычной|превышает типичную|крупный перевод/i,
    "Необычная сумма",
    "Әдеттен тыс сома",
  ],
  [/ночное время/i, "Позднее время", "Түнгі уақыт"],
  [
    /дробления|повторный/i,
    "Несколько переводов подряд",
    "Қатарынан бірнеше аударым",
  ],
];

function loadDecisions(value: string): Decision[] {
  try {
    const data = JSON.parse(value);
    return Array.isArray(data) ? data : [];
  } catch {
    return [];
  }
}

function DecisionHistory({ entries }: { entries: Decision[] }) {
  const t = useText();
  const clock = new Intl.DateTimeFormat(t("ru-KZ", "kk-KZ"), {
    timeZone: "Asia/Almaty",
    hour: "2-digit",
    minute: "2-digit",
  });
  return (
    <section className="trusted-ledger">
      <h2>{t("История решений", "Шешімдер тарихы")}</h2>
      {!entries.length && (
        <p>
          {t(
            "Ваши решения появятся здесь.",
            "Шешімдеріңіз осы жерде көрсетіледі.",
          )}
        </p>
      )}
      {entries.map((entry) => {
        const [name, ...family] = entry.recipient_name.trim().split(/\s+/);
        const shortName = family[0] ? name + " " + family[0][0] + "." : name;
        return (
          <details key={entry.transfer_id} className="trusted-decision">
            <summary>
              <span>
                <b>
                  {entry.status === "BLOCKED"
                    ? t("Отклонено", "Қабылданбады")
                    : t("Разрешено", "Рұқсат берілді")}
                </b>
                {entry.updated_at && (
                  <time dateTime={entry.updated_at}>
                    {clock.format(dateValue(entry.updated_at))}
                  </time>
                )}
                <small>{shortName}</small>
              </span>
              <Money amount={entry.amount} />
            </summary>
            <TransferHistory id={entry.transfer_id} status={entry.status} />
          </details>
        );
      })}
    </section>
  );
}

function Request({
  id,
  answer,
  onDecision,
}: {
  id: string;
  answer?: string | null;
  onDecision: (decision: Decision) => void;
}) {
  const t = useText();
  const { motherPhone } = useProfile();
  const cache = useQueryClient();
  const path = "/transfers/" + id;
  const query = useData<Models["TransferResponse"]>(path);
  const action = useAction();
  const data = query.data;
  const deadline =
    data?.status === "TRUSTED_PENDING" &&
    data.updated_at &&
    data.timeout_seconds != null
      ? +dateValue(data.updated_at) + data.timeout_seconds * 1000
      : null;
  const [expiredDeadline, markExpired] = useState<number>();
  useEffect(() => {
    if (deadline === null) return;
    const timer = setTimeout(
      () => {
        markExpired(deadline);
        void cache.invalidateQueries({ queryKey: [path] });
      },
      Math.max(0, deadline - Date.now()),
    );
    return () => clearTimeout(timer);
  }, [cache, deadline, path]);
  if (query.isPending) return <Skeleton />;
  if (!data)
    return (
      <ErrorState>
        {t(
          "Не удалось открыть запрос. Обновите страницу и попробуйте снова.",
          "Сұрауды ашу мүмкін болмады. Бетті жаңартып, қайталап көріңіз.",
        )}
      </ErrorState>
    );

  const expired =
    data.status === "COOLING_OFF" ||
    data.status === "MANUAL_BANK_REVIEW" ||
    (deadline !== null && deadline === expiredDeadline);
  if (expired)
    return (
      <Card className="trusted-closed" role="status">
        <Clock3 aria-hidden="true" />
        <h2>
          {t(
            "Время вышло, деньги остались на счёте",
            "Уақыт аяқталды, ақша шотта қалды",
          )}
        </h2>
        <p>
          <Money amount={data.amount} /> / {data.recipient_name}
        </p>
      </Card>
    );
  if (data.status !== "TRUSTED_PENDING") {
    return (
      <Card className="trusted-closed" role="status">
        <ShieldCheck aria-hidden="true" />
        <h2>{t("Запрос закрыт", "Сұрау жабылды")}</h2>
        <p>
          {data.status === "CANCELLED"
            ? t(
                "Мама отменила перевод. Деньги остались на счёте.",
                "Анаңыз аударымнан бас тартты. Ақша шотта қалды.",
              )
            : t(
                "Решение по этому запросу уже принято.",
                "Бұл сұрау бойынша шешім қабылданды.",
              )}
        </p>
      </Card>
    );
  }
  const signals = data.detected_signals ?? [];
  const reasons = rules
    .filter(([pattern]) => signals.some((signal) => pattern.test(signal)))
    .slice(0, 3);
  const warning = t(data.alert_reason_ru || "", data.alert_reason_kz || "")
    .replace(/⚠\uFE0F?/gu, "")
    .split(
      /\n(?=(?:Срочно позвоните|Близкому дереу|Жақыныңызға дереу|Жақыныңызға қоңырау|Жақыныңызға бірден))/i,
    )[0]
    .trim();
  const decide = (decision: "APPROVE" | "DECLINE") =>
    action.mutate(async () => {
      const result = await api<Models["TransferResponse"]>(
        path + "/trusted-decision",
        {
          trusted_user_id: "demo-trusted",
          decision,
        },
      );
      onDecision({
        transfer_id: result.transfer_id,
        updated_at: result.updated_at,
        recipient_name: result.recipient_name,
        amount: result.amount,
        status: result.status,
      });
      cache.setQueryData([path], result);
    });
  return (
    <>
      <div className="trusted-push" role="status">
        <Bell size={18} aria-hidden="true" />
        <strong>{t("Новый запрос от мамы", "Анаңыздан жаңа сұрау")}</strong>
      </div>
      <article className="trusted-request">
        <div className="trusted-request-label">
          <ShieldCheck size={17} aria-hidden="true" />
          {t(
            "Перевод ждёт вашего решения",
            "Аударым сіздің шешіміңізді күтуде",
          )}
        </div>
        <h2 className="trusted-amount">
          <Money amount={data.amount} />
        </h2>
        <p className="trusted-recipient">
          {t("Получатель", "Алушы")} <b>{data.recipient_name}</b>
        </p>
        {answer && (
          <blockquote>
            <b>{t("Мама написала", "Анаңыздың жауабы")}</b>
            <p>{answer}</p>
          </blockquote>
        )}
        {reasons.length > 0 && (
          <div
            className="trusted-reasons"
            aria-label={t("Причины проверки", "Тексеру себептері")}
          >
            {reasons.map(([, ru, kz]) => (
              <Badge key={ru}>{t(ru, kz)}</Badge>
            ))}
          </div>
        )}
        {warning && (
          <details className="trusted-warning">
            <summary>{t("Подробнее", "Толығырақ")}</summary>
            <p>{warning}</p>
          </details>
        )}
        {deadline !== null && data.timeout_seconds != null && (
          <div className="trusted-countdown">
            <Timer deadline={deadline} duration={data.timeout_seconds} />
            <p>{t("На решение", "Шешім қабылдауға")}</p>
          </div>
        )}
        <div className="trusted-call">
          <p>
            {t(
              "Сначала позвоните маме по знакомому номеру.",
              "Алдымен анаңызға өзіңіз білетін нөмірмен қоңырау шалыңыз.",
            )}
          </p>
          <a
            className="bank-button"
            data-variant="quiet"
            href={"tel:" + motherPhone}
          >
            <Phone size={16} aria-hidden="true" />
            {t("Позвонить маме", "Анама қоңырау шалу")}
          </a>
        </div>
        <div className="trusted-actions">
          <Button disabled={action.isPending} onClick={() => decide("APPROVE")}>
            {t("Разрешить перевод", "Аударымға рұқсат беру")}{" "}
            <Money amount={data.amount} />
          </Button>
          <Button
            data-variant="quiet"
            disabled={action.isPending}
            onClick={() => decide("DECLINE")}
          >
            {t("Отклонить перевод", "Аударымды қабылдамау")}
          </Button>
        </div>
        {action.error && (
          <ErrorState>
            {action.error.message === "409"
              ? t(
                  "Запрос уже изменился. Проверьте его состояние.",
                  "Сұраудың күйі өзгерді. Ағымдағы күйін тексеріңіз.",
                )
              : t(
                  "Не удалось сохранить решение. Попробуйте снова.",
                  "Шешімді сақтау мүмкін болмады. Қайталап көріңіз.",
                )}
          </ErrorState>
        )}
      </article>
    </>
  );
}

export default function Trusted() {
  const t = useText();
  const { clientId } = useProfile();
  const feed = useData<Models["AnalystFeedResponse"]>(
    "/analyst/feed?source=TRANSFER&status=TRUSTED_PENDING",
  );
  const [lastId, saveId] = useStoredValue(
    "qaqpan-trusted-request",
    "sessionStorage",
  );
  const [saved, saveDecisions] = useStoredValue(
    "qaqpan-trusted-decisions",
    "localStorage",
  );
  const entries = loadDecisions(saved);
  const incoming = feed.data?.cards.find(
    (card) =>
      card.client_id === clientId &&
      !entries.some((entry) => entry.transfer_id === card.transfer_id),
  );
  const id = incoming?.transfer_id || lastId;
  const decided = entries.some((entry) => entry.transfer_id === id);
  useEffect(() => {
    if (incoming && incoming.transfer_id !== lastId)
      saveId(incoming.transfer_id);
  }, [incoming, lastId, saveId]);
  return (
    <div className="trusted-flow">
      {id && !decided ? (
        <Request
          key={id}
          id={id}
          answer={incoming?.client_answer}
          onDecision={(decision) => {
            const latest = loadDecisions(
              window.localStorage.getItem("qaqpan-trusted-decisions") ?? "",
            );
            saveDecisions(
              JSON.stringify(
                [
                  decision,
                  ...latest.filter(
                    (item) => item.transfer_id !== decision.transfer_id,
                  ),
                ].slice(0, 20),
              ),
            );
          }}
        />
      ) : feed.isPending ? (
        <Skeleton />
      ) : feed.isError ? (
        <ErrorState>
          {t(
            "Запросы недоступны. Обновите страницу.",
            "Сұраулар қолжетімсіз. Бетті жаңартыңыз.",
          )}
        </ErrorState>
      ) : (
        <Card className="trusted-closed">
          <Bell aria-hidden="true" />
          <h2>{t("Новых запросов нет", "Жаңа сұрау жоқ")}</h2>
          <p>
            {t(
              "Запрос появится здесь автоматически, если банк попросит вас проверить перевод мамы.",
              "Банк анаңыздың аударымын тексеруді сұраса, сұрау осы жерде автоматты түрде пайда болады.",
            )}
          </p>
        </Card>
      )}
      <details className="trusted-rights" open>
        <summary>{t("Ваши полномочия", "Сіздің өкілеттігіңіз")}</summary>
        <p>
          {t(
            "Вы решаете только по этому переводу. Мама может отменить его сама.",
            "Шешімді тек осы аударым бойынша қабылдайсыз. Анаңыз аударымнан өзі бас тарта алады.",
          )}
        </p>
      </details>
      <DecisionHistory entries={entries} />
    </div>
  );
}
