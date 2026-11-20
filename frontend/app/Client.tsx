"use client";

import { useState, type FormEvent } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, ShieldCheck } from "lucide-react";
import { dateValue } from "../lib/account";
import { ApiError, capabilities, type Transfer } from "../lib/api";
import {
  formatAmount,
  formatRecipient,
  parseAmount,
} from "../lib/transfer-input";
import { useProfile } from "../lib/profile";
import { useAccount } from "../lib/useAccount";
import AccountHome, { Protection } from "./AccountHome";
import TransferHistory from "./TransferHistory";
import {
  api,
  money,
  Status,
  Sync,
  useAction,
  useData,
  useSaved,
  useText,
} from "./shared";
import {
  Button,
  Card,
  Chip,
  ErrorState,
  Money,
  Skeleton,
  Stepper,
  Timer,
} from "./ui";

const blank = { name: "", account: "", amount: "" };
const terminalStates = new Set(["COMPLETED", "BLOCKED", "CANCELLED"]);

function ClientError({ error }: { error: Error | null }) {
  const t = useText();
  if (!error) return null;
  const messages: Record<number, string> = {
    400: t(
      "Проверьте данные формы и попробуйте ещё раз.",
      "Нысан деректерін тексеріп, қайталап көріңіз.",
    ),
    404: t(
      "Перевод не найден. Вернитесь к своим счетам.",
      "Аударым табылмады. Шоттарыңызға оралыңыз.",
    ),
    409: t(
      "Статус перевода изменился. Проверьте актуальные данные.",
      "Аударым күйі өзгерді. Ағымдағы деректерді тексеріңіз.",
    ),
    422: t(
      "Проверьте выделенные поля и отправьте форму снова.",
      "Белгіленген өрістерді тексеріп, нысанды қайта жіберіңіз.",
    ),
  };
  const message =
    error instanceof ApiError && error.expiredAnswer
      ? t(
          "Время вышло, деньги остались на счёте.",
          "Уақыт аяқталды, ақша шотта қалды.",
        )
      : (messages[Number(error.message)] ??
        t(
          "Не удалось связаться с банком. Повторите попытку.",
          "Банкпен байланысу мүмкін болмады. Қайталап көріңіз.",
        ));
  return <ErrorState>{message}</ErrorState>;
}

export default function Client() {
  const t = useText();
  const cache = useQueryClient();
  const [id, save] = useSaved("qaqpan-transfer");
  const query = useData<Transfer>(id ? "/transfers/" + id : "");
  const action = useAction();
  const transfer = query.data;
  const { lastFour, exampleAccount, trustedName, contacts, clientId } =
    useProfile(transfer?.trusted_contact);
  const account = useAccount(transfer);
  const [view, setView] = useState<"home" | "transfer" | null>(null);
  const [draft, setDraft] = useState(blank);
  const [step, setStep] = useState(0);
  const [inputError, setInputError] = useState("");
  const [read, setRead] = useState(false);
  const terminal = Boolean(transfer && terminalStates.has(transfer.status));
  const home = view === "home" || (view === null && !id);
  const setField = (key: keyof typeof draft, value: string) => {
    action.reset();
    setInputError("");
    setDraft((current) => ({ ...current, [key]: value }));
  };
  const openTransfer = (name = "", number = "") => {
    if (!id || terminal || query.error?.message === "404") {
      save("");
      setStep(name ? 1 : 0);
      setInputError("");
      setDraft({ ...blank, name, account: number });
      setRead(false);
      action.reset();
    }
    setView("transfer");
  };
  const goHome = () => {
    if (query.error?.message === "404") save("");
    action.reset();
    setView("home");
  };
  const apply = (result: Transfer) => {
    cache.setQueryData(["/transfers/" + result.transfer_id], result);
  };
  const create = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (step < 2) {
      const recipient = formatRecipient(draft.account);
      if (step === 0 && !recipient) {
        setInputError("account");
        return;
      }
      if (step === 1 && !(parseAmount(draft.amount) > 0)) {
        setInputError("amount");
        return;
      }
      if (step === 0 && recipient) setDraft({ ...draft, account: recipient });
      setInputError("");
      setStep(step + 1);
      return;
    }
    action.mutate(async () => {
      const result = await api<Transfer>("/transfers", {
        client_id: clientId,
        recipient_name: draft.name.trim(),
        recipient_account: draft.account.replace(/\s/g, ""),
        amount: parseAmount(draft.amount),
        currency: "KZT",
        language: t("ru", "kz"),
      });
      apply(result);
      save(result.transfer_id);
    });
  };
  const invalid = (name: string) =>
    action.error instanceof ApiError &&
    (action.error.status === 400 || action.error.field(name));
  const failureStep =
    invalid("recipient_name") || invalid("recipient_account") ? 0 : 1;
  const status = transfer?.status;
  const reserved =
    status === "TRUSTED_PENDING" ||
    status === "COOLING_OFF" ||
    status === "MANUAL_BANK_REVIEW";
  const reviewState =
    status === "COOLING_OFF" ||
    (status === "TRUSTED_PENDING" && capabilities.verifyWhileWaiting);
  const update = (path: string, payload: object) =>
    action.mutate(async () => {
      apply(await api<Transfer>("/transfers/" + id + path, payload));
      setRead(false);
    });
  return (
    <>
      {id && !terminal && <Sync />}
      {home ? (
        <>
          {id && !terminal && query.error?.message !== "404" && (
            <Button className="resume" onClick={() => setView("transfer")}>
              {t("Вернуться к текущему переводу", "Ағымдағы аударымға оралу")}
            </Button>
          )}
          <AccountHome
            account={account}
            trustedName={trustedName}
            onTransfer={openTransfer}
          />
        </>
      ) : (
        <div className="client-transfer">
          <button type="button" className="bank-back" onClick={goHome}>
            <ArrowLeft size={18} aria-hidden="true" />
            {t("Мои счета", "Менің шоттарым")}
          </button>
          <h1>
            {id
              ? t("Статус перевода", "Аударым күйі")
              : t("Новый перевод", "Жаңа аударым")}
          </h1>
          <div className="client-columns">
            <Card className="client-transfer-panel">
              {!id ? (
                <>
                  <Stepper
                    current={step}
                    label={t("Шаги перевода", "Аударым қадамдары")}
                    steps={[
                      t("Получатель", "Алушы"),
                      t("Сумма", "Сома"),
                      t("Подтверждение", "Растау"),
                    ]}
                  />
                  <form onSubmit={create} key={step}>
                    {step === 0 && (
                      <>
                        <div className="client-chips">
                          {contacts.map((contact) => (
                            <Chip
                              key={contact.account}
                              onClick={() => {
                                action.reset();
                                setInputError("");
                                setDraft({
                                  ...draft,
                                  name: t(contact.name[0], contact.name[1]),
                                  account: contact.account,
                                });
                              }}
                            >
                              {t(contact.name[0], contact.name[1])}
                            </Chip>
                          ))}
                        </div>
                        <label>
                          {t("Имя получателя", "Алушының аты")}
                          <input
                            autoComplete="off"
                            aria-invalid={invalid("recipient_name")}
                            maxLength={128}
                            required
                            pattern=".*\S.*"
                            name="name"
                            value={draft.name}
                            onChange={(event) =>
                              setField("name", event.target.value)
                            }
                          />
                        </label>
                        <label>
                          {t("Реквизиты получателя", "Алушының деректемелері")}
                          <input
                            autoComplete="off"
                            aria-invalid={
                              inputError === "account" ||
                              invalid("recipient_account")
                            }
                            maxLength={28}
                            required
                            pattern=".*\S.*"
                            name="account"
                            value={draft.account}
                            onChange={(event) =>
                              setField("account", event.target.value)
                            }
                            placeholder={t(
                              "+7 7XX XXX XX XX или IBAN KZ…",
                              "+7 7XX XXX XX XX немесе IBAN KZ…",
                            )}
                          />
                        </label>
                        <Chip
                          onClick={() => {
                            action.reset();
                            setInputError("");
                            setDraft({
                              name: t("Данияр Садыков", "Данияр Садықов"),
                              account: exampleAccount,
                              amount: formatAmount("250000"),
                            });
                          }}
                        >
                          {t("Заполнить пример", "Мысалды толтыру")}
                        </Chip>
                      </>
                    )}
                    {step === 1 && (
                      <>
                        <label>
                          {t("Сумма, ₸", "Сома, ₸")}
                          <input
                            name="amount"
                            inputMode="decimal"
                            type="text"
                            maxLength={24}
                            required
                            aria-invalid={
                              inputError === "amount" || invalid("amount")
                            }
                            value={draft.amount}
                            onChange={(event) =>
                              setField(
                                "amount",
                                formatAmount(event.target.value),
                              )
                            }
                          />
                        </label>
                        {account.snapshot && (
                          <p className="transfer-available">
                            {t("Доступно", "Қолжетімді")}{" "}
                            <Money amount={account.snapshot.available} />
                          </p>
                        )}
                      </>
                    )}
                    {step === 2 && (
                      <>
                        <p className="transfer-amount">
                          <Money amount={parseAmount(draft.amount)} />
                        </p>
                        <dl className="bank-receipt">
                          <div>
                            <dt>{t("Получатель", "Алушы")}</dt>
                            <dd>{draft.name}</dd>
                          </div>
                          <div>
                            <dt>{t("Реквизиты", "Деректемелер")}</dt>
                            <dd>{draft.account}</dd>
                          </div>
                          <div>
                            <dt>{t("Со счёта", "Қай шоттан")}</dt>
                            <dd>
                              {t("Карта", "Карта")} •• {lastFour}
                              <small>
                                {t("Доступно", "Қолжетімді")}{" "}
                                {account.snapshot ? (
                                  <Money amount={account.snapshot.available} />
                                ) : (
                                  "—"
                                )}
                              </small>
                            </dd>
                          </div>
                        </dl>
                        <p>
                          {t(
                            "Банк проверит операцию перед отправкой денег.",
                            "Банк ақша жібермес бұрын операцияны тексереді.",
                          )}
                        </p>
                      </>
                    )}
                    {inputError && (
                      <ErrorState>
                        {inputError === "account"
                          ? t(
                              "Укажите телефон +7 7XX XXX XX XX или IBAN из 20 символов, начиная с KZ.",
                              "+7 7XX XXX XX XX телефонын немесе KZ-ден басталатын 20 таңбалы IBAN нөмірін енгізіңіз.",
                            )
                          : t(
                              "Введите сумму больше нуля.",
                              "Нөлден үлкен соманы енгізіңіз.",
                            )}
                      </ErrorState>
                    )}
                    <ClientError error={action.error} />
                    {step === 2 &&
                      action.error instanceof ApiError &&
                      [400, 422].includes(action.error.status) && (
                        <Chip onClick={() => setStep(failureStep)}>
                          {t("Исправить данные", "Деректерді түзету")}
                        </Chip>
                      )}
                    <div className="bank-form-actions">
                      <Button disabled={action.isPending}>
                        {step === 2
                          ? t("Перевести", "Аудару") +
                            " " +
                            money(parseAmount(draft.amount))
                          : t("Продолжить", "Жалғастыру")}
                      </Button>
                      {step > 0 && (
                        <Button
                          type="button"
                          data-variant="quiet"
                          disabled={action.isPending}
                          onClick={() => setStep(step - 1)}
                        >
                          {t("Назад", "Артқа")}
                        </Button>
                      )}
                    </div>
                  </form>
                </>
              ) : transfer ? (
                <>
                  <Stepper
                    current={terminal ? 3 : reserved ? 2 : 1}
                    label={t("Этапы обработки", "Өңдеу кезеңдері")}
                    steps={[
                      t("Создан", "Жасалды"),
                      t("Проверка", "Тексеру"),
                      t("Решение близкого", "Жақыныңыздың шешімі"),
                      t("Итог", "Нәтиже"),
                    ]}
                  />
                  <div className="transfer-total">
                    <span className="transfer-amount">
                      <Money amount={transfer.amount} />
                    </span>
                    <span>{transfer.recipient_name}</span>
                    <small>{transfer.recipient_account}</small>
                  </div>
                  <div
                    className="client-status"
                    data-status={status}
                    role="status"
                  >
                    <ShieldCheck aria-hidden="true" />
                    <div>
                      <Status value={transfer.status} />
                      {status === "COMPLETED" && (
                        <p>
                          {t(
                            "Проверка пройдена. Деньги отправлены получателю.",
                            "Тексеру аяқталды. Ақша алушыға жіберілді.",
                          )}
                        </p>
                      )}
                      {status === "AWAITING_ANSWER" && (
                        <p>
                          {t(
                            "Деньги ещё на счёте. Ответ поможет банку проверить перевод.",
                            "Ақша әлі шотта. Жауабыңыз банкке аударымды тексеруге көмектеседі.",
                          )}
                        </p>
                      )}
                      {status === "TRUSTED_PENDING" && (
                        <p>
                          {t(
                            `${money(transfer.amount)} пока не отправлены. Ждём решения: ${trustedName}.`,
                            `${money(transfer.amount)} әлі жіберілген жоқ. ${trustedName} шешімін күтеміз.`,
                          )}
                        </p>
                      )}
                      {status === "BLOCKED" && (
                        <p>
                          {t(
                            `${trustedName} отклонила перевод. Деньги остались на счёте.`,
                            `${trustedName} аударымды қабылдамады. Ақша шотта қалды.`,
                          )}{" "}
                          {transfer.updated_at && (
                            <time>
                              {dateValue(
                                transfer.updated_at,
                              ).toLocaleTimeString(t("ru-KZ", "kk-KZ"), {
                                hour: "2-digit",
                                minute: "2-digit",
                                timeZone: "Asia/Almaty",
                              })}
                            </time>
                          )}
                        </p>
                      )}
                      {status === "MANUAL_BANK_REVIEW" && (
                        <p>
                          {t(
                            "Банк получил запрос. Деньги ещё не отправлены.",
                            "Банк сұрауды алды. Ақша әлі жіберілген жоқ.",
                          )}
                        </p>
                      )}
                      {status === "CANCELLED" && (
                        <p>
                          {t("Деньги остались на счёте.", "Ақша шотта қалды.")}
                        </p>
                      )}
                    </div>
                  </div>
                  {status === "TRUSTED_PENDING" &&
                    transfer.updated_at &&
                    transfer.timeout_seconds != null && (
                      <Timer
                        deadline={
                          +dateValue(transfer.updated_at) +
                          transfer.timeout_seconds * 1000
                        }
                        duration={transfer.timeout_seconds}
                      />
                    )}
                  {status === "AWAITING_ANSWER" && (
                    <form
                      onSubmit={(event) => {
                        event.preventDefault();
                        update("/answer", {
                          answer_text: new FormData(event.currentTarget).get(
                            "answer",
                          ),
                        });
                      }}
                    >
                      <label>
                        {t(
                          transfer.challenge_question ||
                            "Для чего этот перевод?",
                          transfer.challenge_question_kz ||
                            "Бұл аударымды не үшін жасайсыз?",
                        )}
                        <textarea
                          name="answer"
                          required
                          aria-invalid={invalid("answer_text")}
                        />
                      </label>
                      <Button disabled={action.isPending}>
                        {t("Отправить ответ", "Жауап жіберу")}
                      </Button>
                    </form>
                  )}
                  {reviewState && (
                    <div className="client-cooling">
                      <p>
                        {t(
                          transfer.cooling_warning_ru ||
                            "Деньги ещё не отправлены.",
                          transfer.cooling_warning_kz ||
                            "Ақша әлі жіберілген жоқ.",
                        )}
                      </p>
                      {capabilities.coolingTimer(transfer) !== null && (
                        <p>
                          {t("Осталось секунд", "Қалған секунд")}{" "}
                          <b>{capabilities.coolingTimer(transfer)}</b>
                        </p>
                      )}
                      <label>
                        <input
                          type="checkbox"
                          checked={read}
                          onChange={(event) => setRead(event.target.checked)}
                        />
                        {t("Я прочитал предупреждение", "Ескертуді оқыдым")}
                      </label>
                      <Button
                        disabled={!read || action.isPending}
                        onClick={() =>
                          update("/manual-review", {
                            warning_acknowledged: true,
                          })
                        }
                      >
                        {t("Запросить проверку банка", "Банк тексерісін сұрау")}
                      </Button>
                    </div>
                  )}
                  <ClientError error={action.error || query.error} />
                  <div className="bank-form-actions">
                    {terminal ? (
                      <Button onClick={() => openTransfer()}>
                        {t("Новый перевод", "Жаңа аударым")}
                      </Button>
                    ) : (
                      <Button
                        data-variant="quiet"
                        disabled={action.isPending}
                        onClick={() => update("/cancel", {})}
                      >
                        {t("Отменить перевод", "Аударымнан бас тарту")}
                      </Button>
                    )}
                  </div>
                  <TransferHistory
                    id={transfer.transfer_id}
                    status={transfer.status}
                  />
                </>
              ) : query.isPending ? (
                <Skeleton />
              ) : (
                <>
                  <ClientError error={query.error} />
                  {query.error?.message !== "404" && (
                    <Button onClick={() => void query.refetch()}>
                      {t("Проверить снова", "Қайта тексеру")}
                    </Button>
                  )}
                </>
              )}
            </Card>
            <Protection contact={trustedName} />
          </div>
        </div>
      )}
    </>
  );
}
