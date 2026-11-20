"use client";
import TransferHistory from "./TransferHistory";
import { useState } from "react";
import {
  api,
  useData,
  useAction,
  useText,
  useSaved,
  Models,
  Status,
  Sync,
  Clock,
  ErrorBox,
  money,
} from "./shared";
import {
  ArrowUpRight,
  ShieldCheck,
  CircleCheck,
  CircleHelp,
  Clock3,
  ShieldX,
  Ban,
  Hourglass,
} from "lucide-react";

import AccountHome from "./AccountHome";
export default function Client() {
  const t = useText(),
    [id, save] = useSaved("qaqpan-transfer"),
    query = useData<Models["TransferResponse"]>(id ? "/transfers/" + id : ""),
    action = useAction(),
    r = query.data,
    [ack, setAck] = useState(false);
  const [draft, setDraft] = useState({ name: "", account: "", amount: "" });
  const [view, setView] = useState<"home" | "transfer" | null>(null);
  const terminal =
    r && ["COMPLETED", "BLOCKED", "CANCELLED"].includes(r.status);
  const stateIcons = {
    COMPLETED: CircleCheck,
    AWAITING_ANSWER: CircleHelp,
    TRUSTED_PENDING: Clock3,
    BLOCKED: ShieldX,
    CANCELLED: Ban,
    COOLING_OFF: Hourglass,
  };
  const StateIcon =
    r && r.status in stateIcons
      ? stateIcons[r.status as keyof typeof stateIcons]
      : ShieldCheck;
  const openTransfer = (name: string, account: string) => {
    if (!id || terminal) {
      save("");
      setAck(false);
      setDraft({ name, account, amount: "" });
    }
    setView("transfer");
  };
  if (view === "home" || (view === null && !id))
    return (
      <>
        {id && !terminal && (
          <button className="resume" onClick={() => setView("transfer")}>
            {t("Вернуться к текущему переводу", "Ағымдағы аударымға оралу")}
          </button>
        )}
        <AccountHome onTransfer={openTransfer} />
      </>
    );
  return (
    <>
      <button className="back-account" onClick={() => setView("home")}>
        {t("← Мои счета", "← Менің шоттарым")}
      </button>
      <div className="transfer-layout">
        {id && !terminal && <Sync />}
        <section>
          <h2>
            {id
              ? t("Сведения о переводе", "Аударым туралы мәлімет")
              : t("Реквизиты перевода", "Аударым деректемелері")}
          </h2>
          {!id ? (
            <form
              onChange={(event) => {
                const f = new FormData(event.currentTarget);
                setDraft({
                  name: String(f.get("name") || ""),
                  account: String(f.get("account") || ""),
                  amount: String(f.get("amount") || ""),
                });
              }}
              onSubmit={(e) => {
                e.preventDefault();
                const f = new FormData(e.currentTarget);
                action.mutate(async () => {
                  const result = await api<Models["TransferResponse"]>(
                    "/transfers",
                    {
                      client_id: "demo-client",
                      recipient_account: f.get("account"),
                      recipient_name: f.get("name"),
                      amount: Number(f.get("amount")),
                      currency: "KZT",
                      language: t("ru", "kz"),
                    },
                  );
                  save(result.transfer_id);
                });
              }}
            >
              <label>
                {t("Имя получателя", "Алушының аты")}
                <input
                  name="name"
                  defaultValue={draft.name}
                  placeholder={t("Имя и фамилия", "Аты-жөні")}
                  required
                />
              </label>
              <label>
                {t("Реквизиты получателя", "Алушының деректемелері")}
                <input
                  name="account"
                  defaultValue={draft.account}
                  placeholder={t(
                    "Карта, IBAN или телефон",
                    "Карта, IBAN немесе телефон",
                  )}
                  required
                />
              </label>
              <label>
                {t("Сумма, ₸", "Сома, ₸")}
                <input
                  type="number"
                  name="amount"
                  defaultValue={draft.amount}
                  placeholder="0,00"
                  min=".01"
                  step=".01"
                  required
                />
              </label>
              <div className="actions">
                {" "}
                <button disabled={action.isPending}>
                  {t("Перевести", "Аудару")}
                </button>{" "}
                <button
                  type="button"
                  className="secondary"
                  onClick={(e) => {
                    const form = e.currentTarget.form;
                    if (!form) return;
                    const preset = {
                      name: t("Демо-получатель", "Сынақ алушы"),
                      account: "TEST-QAQPAN",
                      amount: "250000",
                    };
                    setDraft(preset);
                    for (const [name, value] of Object.entries(preset)) {
                      const input = form.elements.namedItem(name);
                      if (input instanceof HTMLInputElement)
                        input.value = value;
                    }
                  }}
                >
                  {t("Заполнить пример", "Мысалды толтыру")}
                </button>
              </div>
            </form>
          ) : r ? (
            <>
              <h3>{money(r.amount)}</h3>
              <p>
                {r.recipient_name} · {r.recipient_account}
              </p>
              <div role="status" className={"state-panel state-" + r.status}>
                <StateIcon aria-hidden="true" />
                <Status value={r.status} />
                {r.status === "TRUSTED_PENDING" && (
                  <p>
                    {t(
                      "Деньги ещё не отправлены. Ждём решения Айгерим. Вы можете отменить перевод.",
                      "Ақша әлі жіберілген жоқ. Айгерімнің шешімін күтеміз. Аударымнан бас тарта аласыз.",
                    )}
                  </p>
                )}
                {r.status === "BLOCKED" && (
                  <p>
                    {t(
                      "Близкий отклонил перевод. Деньги не отправлены.",
                      "Жақыныңыз аударымды қабылдамады. Ақша жіберілген жоқ.",
                    )}
                  </p>
                )}
              </div>
              {r.status === "AWAITING_ANSWER" && (
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    const answer = new FormData(e.currentTarget).get("answer");
                    action.mutate(async () => {
                      await api("/transfers/" + id + "/answer", {
                        answer_text: answer,
                      });
                    });
                  }}
                >
                  <label>
                    {t(
                      r.challenge_question || "Цель перевода",
                      r.challenge_question_kz || "Аударым мақсаты",
                    )}
                    <textarea name="answer" required />
                  </label>
                  <button disabled={action.isPending}>
                    {t("Отправить ответ", "Жауап жіберу")}
                  </button>
                </form>
              )}
              {r.status === "TRUSTED_PENDING" && (
                <p>
                  {r.trusted_contact?.name} ·{" "}
                  <Clock
                    updated={r.updated_at!}
                    seconds={r.timeout_seconds ?? 30}
                  />
                </p>
              )}
              {r.status === "COOLING_OFF" && (
                <>
                  <p>
                    {t(r.cooling_warning_ru || "", r.cooling_warning_kz || "")}
                  </p>
                  <label>
                    <input
                      type="checkbox"
                      checked={ack}
                      onChange={(e) => setAck(e.target.checked)}
                    />
                    {t("Я прочитал предупреждение", "Ескертуді оқыдым")}
                  </label>
                  <button
                    disabled={!ack || action.isPending}
                    onClick={() =>
                      action.mutate(async () => {
                        await api("/transfers/" + id + "/manual-review", {
                          warning_acknowledged: true,
                        });
                        setAck(false);
                      })
                    }
                  >
                    {t("Запросить проверку банка", "Банк тексерісін сұрау")}
                  </button>
                </>
              )}
              <TransferHistory id={r.transfer_id} status={r.status} expanded />
              {terminal ? (
                <button
                  onClick={() => {
                    save("");
                    setDraft({ name: "", account: "", amount: "" });
                    setAck(false);
                  }}
                >
                  {t("Новый перевод", "Жаңа аударым")}
                </button>
              ) : (
                <button
                  className="secondary"
                  disabled={action.isPending}
                  onClick={() =>
                    action.mutate(async () => {
                      await api("/transfers/" + id + "/cancel", {});
                    })
                  }
                >
                  {t("Отменить перевод", "Аударымды жою")}
                </button>
              )}
            </>
          ) : query.isLoading ? (
            <p>…</p>
          ) : (
            <button
              onClick={() => {
                save("");
                setDraft({ name: "", account: "", amount: "" });
              }}
            >
              {t("К форме", "Нысанға оралу")}
            </button>
          )}
          <ErrorBox error={query.error || action.error} />
        </section>
        <aside className="receipt">
          <div className="receipt-top">
            <ArrowUpRight aria-hidden="true" />
            <span>{t("Детали перевода", "Аударым мәліметтері")}</span>
          </div>
          <div className="receipt-amount">
            {r
              ? money(r.amount)
              : draft.amount
                ? money(Number(draft.amount))
                : "0 ₸"}
          </div>
          <dl>
            <dt>{t("Получатель", "Алушы")}</dt>
            <dd>{r?.recipient_name || draft.name || "—"}</dd>
            <dt>{t("Реквизиты", "Деректемелер")}</dt>
            <dd>{r?.recipient_account || draft.account || "—"}</dd>
          </dl>
          <div className="receipt-foot">
            <ShieldCheck size={22} aria-hidden="true" />
            <span>
              {r
                ? t(
                    "Текущий результат проверки указан в сведениях о переводе.",
                    "Тексеру нәтижесі аударым мәліметтерінде көрсетілген.",
                  )
                : t(
                    "До отправки Қақпан проверит перевод. Если потребуется, попросим уточнить его цель.",
                    "Ақша жіберілмес бұрын Қақпан аударымды тексереді. Қажет болса, мақсатын нақтылауды сұраймыз.",
                  )}
            </span>
          </div>
        </aside>
      </div>
    </>
  );
}
