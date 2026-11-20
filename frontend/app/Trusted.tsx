"use client";
import TransferHistory from "./TransferHistory";
import { useState } from "react";
import { Bell, ShieldAlert } from "lucide-react";
import {
  api,
  useAction,
  useData,
  useText,
  Models,
  money,
  ErrorBox,
  Status,
  Clock,
} from "./shared";
function Request({
  id,
  answer,
  onDecision,
}: {
  id: string;
  answer?: string | null;
  onDecision: (result: Models["TransferResponse"]) => void;
}) {
  const t = useText(),
    q = useData<Models["TransferResponse"]>("/transfers/" + id),
    a = useAction(),
    r = q.data;
  return (
    <article>
      {r && (
        <>
          <strong className="alert-heading">
            <ShieldAlert aria-hidden="true" />
            {t("Тревожный перевод", "Күмәнді аударым")}
          </strong>
          <h3>{money(r.amount)}</h3>
          <b>
            {t("Получатель", "Алушы")} · {r.recipient_name}
          </b>
          {answer && (
            <blockquote>
              {t("Мама написала", "Анаңыздың жауабы")} · {answer}
            </blockquote>
          )}
          <p>{t(r.alert_reason_ru || "", r.alert_reason_kz || "")}</p>
          {r.updated_at && r.timeout_seconds != null && (
            <p>
              {t("До истечения запроса", "Сұраудың аяқталуына дейін")} ·{" "}
              <Clock updated={r.updated_at} seconds={r.timeout_seconds} />
            </p>
          )}
          <p>
            {t(
              "Перед решением позвоните маме по знакомому номеру и уточните, кому она переводит деньги.",
              "Шешім қабылдамас бұрын анаңызға өзіңіз білетін нөмірмен қоңырау шалып, ақшаны кімге аударып жатқанын нақтылаңыз.",
            )}
          </p>
          <TransferHistory id={id} status={r.status} />
          {(["DECLINE", "APPROVE"] as const).map((d) => (
            <button
              key={d}
              className={d === "APPROVE" ? "secondary" : ""}
              disabled={a.isPending || r.status !== "TRUSTED_PENDING"}
              onClick={() =>
                a.mutate(async () => {
                  const result = await api<Models["TransferResponse"]>(
                    "/transfers/" + id + "/trusted-decision",
                    {
                      trusted_user_id: "demo-trusted",
                      decision: d,
                    },
                  );
                  onDecision(result);
                })
              }
            >
              {d === "APPROVE"
                ? t("Разрешить перевод", "Аударымға рұқсат беру") +
                  " · " +
                  money(r.amount)
                : t("Отклонить перевод", "Аударымды қабылдамау")}
            </button>
          ))}
        </>
      )}
      <ErrorBox error={a.error || q.error} />
    </article>
  );
}
export default function Trusted() {
  const t = useText(),
    q = useData<Models["AnalystFeedResponse"]>(
      "/analyst/feed?source=TRANSFER&status=TRUSTED_PENDING",
    );
  const [decision, setDecision] = useState<Models["TransferResponse"]>();
  const requests = q.data?.cards.filter((c) => c.client_id === "demo-client");
  return (
    <>
      <section className="relationship">
        <span className="avatar tint1">С</span>
        <div>
          <small>{t("Вы помогаете", "Сіз көмектесесіз")}</small>
          <h2>{t("Сауле К. · мама", "Сәуле К. · анаңыз")}</h2>
        </div>
        <details>
          <summary>{t("Ваши полномочия", "Сіздің өкілеттігіңіз")}</summary>
          <p>
            {t(
              "Вы можете разрешить или остановить конкретный перевод, когда банк присылает запрос.",
              "Банк сұрау жібергенде нақты аударымға рұқсат бере аласыз немесе оны тоқтата аласыз.",
            )}
          </p>
        </details>
      </section>
      <section className="inbox">
        <h2>
          <Bell size={21} aria-hidden="true" />{" "}
          {t("Входящие запросы", "Кіріс сұраулар")}
        </h2>
        <p>
          {t(
            "Если перевод близкого потребует проверки, запрос появится здесь автоматически. Деньги ждут вашего решения.",
            "Жақыныңыздың аударымын тексеру қажет болса, сұрау осы жерде автоматты түрде пайда болады. Ақша шешіміңізге дейін жіберілмейді.",
          )}
        </p>
        {decision && (
          <div role="status">
            {t("Последнее решение", "Соңғы шешім")} · {money(decision.amount)} ·{" "}
            {decision.recipient_name} · <Status value={decision.status} />
            <TransferHistory
              id={decision.transfer_id}
              status={decision.status}
            />
          </div>
        )}
        {requests?.map((r) => (
          <Request
            key={r.transfer_id}
            id={r.transfer_id}
            answer={r.client_answer}
            onDecision={setDecision}
          />
        ))}
        {requests && !requests.length && (
          <p>
            {t(
              "Сейчас нет переводов на подтверждение.",
              "Қазір растауды күтетін аударым жоқ.",
            )}
          </p>
        )}
        <ErrorBox error={q.error} />
      </section>
    </>
  );
}
