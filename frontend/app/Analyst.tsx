"use client";
import TransferHistory from "./TransferHistory";
import { useState } from "react";
import {
  api,
  useAction,
  useData,
  useSaved,
  useText,
  Models,
  ErrorBox,
  money,
  Status,
} from "./shared";
import Trap from "./Trap";
type Metrics = { stop_rate: number; false_positive_rate: number };
type Report = { total_scenarios: number; baseline: Metrics; qaqpan: Metrics };
export default function Analyst() {
  const t = useText(),
    [source, set] = useState("ALL"),
    [risk, setRisk] = useState(""),
    [status, setStatus] = useState(""),
    [id, select] = useSaved("qaqpan-trap"),
    q = useData<Models["AnalystFeedResponse"]>(
      "/analyst/feed?" +
        new URLSearchParams({
          source,
          ...(source === "TRANSFER" && risk ? { risk_tier: risk } : {}),
          ...(source === "TRANSFER" && status ? { status } : {}),
        }),
    ),
    a = useAction(),
    [report, show] = useState<Report>();
  return (
    <>
      <div className="desk-summary">
        {[
          [
            t("Записей в выборке", "Іріктемедегі жазбалар"),
            q.data?.cards.length,
          ],
          [
            t("Высокий риск", "Жоғары тәуекел"),
            q.data?.cards.filter(
              (c) => c.risk_tier === "HIGH" || c.risk_tier === "CRITICAL",
            ).length,
          ],
          [
            t("Ждут близкого", "Жақынын күтуде"),
            q.data?.cards.filter((c) => c.status === "TRUSTED_PENDING").length,
          ],
          [
            t("Проверка банка", "Банк тексерісі"),
            q.data?.cards.filter((c) => c.status === "MANUAL_BANK_REVIEW")
              .length,
          ],
        ].map(([label, count]) => (
          <div key={label}>
            <span>{label}</span>
            <b>{count ?? "—"}</b>
          </div>
        ))}
      </div>
      <section>
        <h2>{t("Лента проверок", "Тексерулер тізімі")}</h2>
        <select
          aria-label={t("Источник", "Дереккөз")}
          value={source}
          onChange={(e) => set(e.target.value)}
        >
          <option value="ALL">{t("Все записи", "Барлық жазбалар")}</option>
          <option value="TRANSFER">{t("Переводы", "Аударымдар")}</option>
          <option value="TRAP">{t("Ловушка", "Тұзақ")}</option>
        </select>
        {source === "TRANSFER" && (
          <>
            <select
              aria-label={t("Риск", "Тәуекел")}
              value={risk}
              onChange={(e) => setRisk(e.target.value)}
            >
              <option value="">{t("Все риски", "Барлық тәуекелдер")}</option>
              {["LOW", "MEDIUM", "HIGH", "CRITICAL"].map((v) => (
                <option key={v}>{v}</option>
              ))}
            </select>
            <select
              aria-label={t("Статус", "Күй")}
              value={status}
              onChange={(e) => setStatus(e.target.value)}
            >
              <option value="">{t("Все статусы", "Барлық күйлер")}</option>
              {[
                "AWAITING_ANSWER",
                "TRUSTED_PENDING",
                "COOLING_OFF",
                "MANUAL_BANK_REVIEW",
                "COMPLETED",
                "BLOCKED",
                "CANCELLED",
              ].map((v) => (
                <option key={v}>{v}</option>
              ))}
            </select>
          </>
        )}
        {source !== "TRAP" && (
          <div className="feed-scroll" tabIndex={0}>
            <table className="feed">
              <caption>{t("Переводы", "Аударымдар")}</caption>
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
                  ].map((h) => (
                    <th key={h} scope="col">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {q.data?.cards
                  .filter((c) => c.source !== "TRAP")
                  .map((c) => (
                    <tr key={c.transfer_id}>
                      <td>
                        <time dateTime={c.created_at}>
                          {new Date(
                            /Z$|[+-]\d\d:\d\d$/.test(c.created_at)
                              ? c.created_at
                              : c.created_at + "Z",
                          ).toLocaleString(t("ru-KZ", "kk-KZ"), {
                            day: "2-digit",
                            month: "2-digit",
                            hour: "2-digit",
                            minute: "2-digit",
                          })}
                        </time>
                      </td>
                      <td>{c.client_id}</td>
                      <td>{money(c.amount)}</td>
                      <td>{c.recipient_name}</td>
                      <td>
                        <b className={"risk " + c.risk_tier}>
                          {c.risk_tier ?? "—"}
                        </b>
                      </td>
                      <td>
                        <Status value={c.status} />
                      </td>
                      <td>
                        {c.signals?.join(" · ") || "—"}
                        <TransferHistory id={c.transfer_id} status={c.status} />
                        {(c.client_answer || c.explanation) && (
                          <details>
                            <summary>{t("Подробности", "Толығырақ")}</summary>
                            <p>{c.explanation}</p>
                            {c.client_answer && (
                              <blockquote>{c.client_answer}</blockquote>
                            )}
                          </details>
                        )}
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        )}
        {q.data?.cards
          .filter((c) => c.source === "TRAP")
          .map((c) => (
            <article key={c.transfer_id}>
              <h3>{t("Диалог-ловушка", "Тұзақ диалогы")}</h3>
              <Status value={c.status} />
              <p>{c.dialogue_excerpt?.at(-1)}</p>
              <button onClick={() => select(c.session_id!)}>
                {t("Открыть диалог ниже", "Төмендегі диалогты ашу")}
              </button>
            </article>
          ))}
        {q.data && !q.data.cards.length && (
          <p>{t("Записей пока нет", "Әзірге жазба жоқ")}</p>
        )}
        <ErrorBox error={q.error} />
      </section>
      <Trap id={id} select={select} />
      <section>
        <h2>
          {t(
            "Проверка на синтетических данных",
            "Синтетикалық деректердегі тексеріс",
          )}
        </h2>
        <button
          disabled={a.isPending}
          onClick={() =>
            a.mutate(async () => {
              const r = await api<{ status: string; benchmark?: Report }>(
                "/benchmark/simulate?split=test&count=500",
              );
              if (!r.benchmark) throw Error("benchmark");
              show(r.benchmark);
            })
          }
        >
          {a.isPending ? "…" : t("Запустить сравнение", "Салыстыруды бастау")}
        </button>
        {report && (
          <>
            <p>
              {t("Сценариев", "Сценарий саны")}: {report.total_scenarios}
            </p>
            <table>
              <caption>
                {t("Результаты сравнения", "Салыстыру нәтижелері")}
              </caption>
              <thead>
                <tr>
                  <th scope="col">{t("Метод", "Әдіс")}</th>
                  <th scope="col">{t("Выявлено", "Анықталды")}</th>
                  <th scope="col">{t("Ложные тревоги", "Жалған дабылдар")}</th>
                </tr>
              </thead>
              <tbody>
                {(["baseline", "qaqpan"] as const).map((k) => (
                  <tr key={k}>
                    <th scope="row">
                      {k === "baseline"
                        ? t("Лимит суммы", "Сома шегі")
                        : "Қақпан"}
                    </th>
                    <td>{(report[k].stop_rate * 100).toFixed(1)}%</td>
                    <td>{(report[k].false_positive_rate * 100).toFixed(1)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
        <ErrorBox error={a.error} />
      </section>
    </>
  );
}
