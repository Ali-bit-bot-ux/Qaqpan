"use client";

import { useState } from "react";
import {
  ArrowLeftRight,
  ArrowUpRight,
  ArrowDownLeft,
  CreditCard,
  Eye,
  EyeOff,
  History,
  House,
  ReceiptText,
  ScanLine,
  ShieldCheck,
  ShoppingBasket,
  Wallet,
} from "lucide-react";
import { dateValue, type Entry } from "../lib/account";
import { useProfile } from "../lib/profile";
import type { useAccount } from "../lib/useAccount";
import { useText, Status, ErrorBox } from "./shared";
import { Badge, Button, Card, Chip, Money, Skeleton } from "./ui";
import TransferHistory from "./TransferHistory";

const icons = {
  income: ArrowDownLeft,
  groceries: ShoppingBasket,
  utilities: ReceiptText,
  qr: ScanLine,
  home: House,
  transfer: ArrowUpRight,
};
const timeZone = "Asia/Almaty";

export function Protection({ contact }: { contact: string }) {
  const t = useText();
  return (
    <Card className="protection-summary">
      <div className="protection-heading">
        <ShieldCheck aria-hidden="true" />
        <h2>{t("Семейная защита", "Отбасылық қорғаныс")}</h2>
        <Badge>{t("Активна", "Қосулы")}</Badge>
      </div>
      <dl>
        <div>
          <dt>{t("Доверенное лицо", "Сенімді тұлға")}</dt>
          <dd>{contact}</dd>
        </div>
        <div>
          <dt>{t("Когда придёт запрос", "Сұрау қашан келеді")}</dt>
          <dd>
            {t(
              "При высоком риске перевода",
              "Аударым тәуекелі жоғары болғанда",
            )}
          </dd>
        </div>
        <div>
          <dt>{t("Лимит семейной защиты", "Отбасылық қорғаныс лимиті")}</dt>
          <dd>
            {t("Зависит от риска операции", "Операция тәуекеліне байланысты")}
          </dd>
        </div>
      </dl>
    </Card>
  );
}

function Statement({ entries }: { entries: Entry[] }) {
  const t = useText();
  const [filter, setFilter] = useState("");
  const [full, showAll] = useState(false);
  const day = new Intl.DateTimeFormat(t("ru-KZ", "kk-KZ"), {
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone,
  });
  const clock = new Intl.DateTimeFormat(t("ru-KZ", "kk-KZ"), {
    hour: "2-digit",
    minute: "2-digit",
    timeZone,
  });
  const shown = entries.filter((entry) => !filter || entry.status === filter);
  const groups = new Map<string, Entry[]>();
  for (const entry of full ? shown : shown.slice(0, 8)) {
    const key = day.format(dateValue(entry.created_at));
    const group = groups.get(key) ?? [];
    group.push(entry);
    groups.set(key, group);
  }
  const names = {
    income: t("Пополнение", "Толықтыру"),
    groceries: t("Продукты", "Азық-түлік"),
    utilities: t(
      "Коммунальные услуги и связь",
      "Коммуналдық қызметтер және байланыс",
    ),
    qr: t("Оплата по QR", "QR арқылы төлем"),
    home: t("Жильё", "Тұрғын үй"),
    transfer: t("Перевод", "Аударым"),
  };
  return (
    <>
      <div className="statement-toolbar">
        <h2>{t("История операций", "Операциялар тарихы")}</h2>
        <select
          className="statement-filter"
          aria-label={t("Фильтр истории", "Тарих сүзгісі")}
          value={filter}
          onChange={(event) => setFilter(event.target.value)}
        >
          <option value="">{t("Все", "Барлығы")}</option>
          <option value="COMPLETED">{t("Выполненные", "Орындалған")}</option>
          <option value="BLOCKED">{t("Остановленные", "Тоқтатылған")}</option>
          <option value="CANCELLED">{t("Отменённые", "Бас тартылған")}</option>
        </select>
      </div>
      {!shown.length && (
        <p>
          {t(
            "По этому фильтру операций нет.",
            "Бұл сүзгі бойынша операциялар жоқ.",
          )}{" "}
          <Chip onClick={() => setFilter("")}>
            {t("Все операции", "Барлық операциялар")}
          </Chip>
        </p>
      )}
      {[...groups].map(([date, rows]) => (
        <div className="statement-day" key={date}>
          <h3>{date}</h3>
          {rows.map((row) => {
            const Icon = icons[row.category ?? "transfer"];
            const name = t(
              row.recipient_name,
              row.nameKz ?? row.recipient_name,
            );
            const debit = row.status === "COMPLETED" && row.amount > 0;
            return (
              <details key={row.transfer_id} className="bank-operation">
                <summary>
                  <span className="operation-icon">
                    <Icon size={18} aria-hidden="true" />
                  </span>
                  <span className="operation-label">
                    <strong>{name}</strong>
                    <small>
                      {row.fixture ? (
                        names[row.category ?? "transfer"] +
                        " / " +
                        t("Учебные данные", "Оқу деректері")
                      ) : (
                        <Status value={row.status} />
                      )}
                    </small>
                  </span>
                  <span
                    className={row.amount < 0 ? "operation-credit" : undefined}
                  >
                    {row.amount < 0 ? "+" : debit ? "−" : ""}
                    <Money amount={Math.abs(row.amount)} />
                  </span>
                </summary>
                <dl className="bank-receipt">
                  <div>
                    <dt>
                      {row.amount < 0
                        ? t("Источник", "Дереккөз")
                        : t("Получатель", "Алушы")}
                    </dt>
                    <dd>{name}</dd>
                  </div>
                  <div>
                    <dt>{t("Сумма", "Сома")}</dt>
                    <dd>
                      <Money amount={Math.abs(row.amount)} />
                    </dd>
                  </div>
                  <div>
                    <dt>{t("Время", "Уақыт")}</dt>
                    <dd>{clock.format(dateValue(row.created_at))}</dd>
                  </div>
                  <div>
                    <dt>{t("Номер операции", "Операция нөмірі")}</dt>
                    <dd>{row.transfer_id}</dd>
                  </div>
                  <div>
                    <dt>{t("Итог", "Нәтиже")}</dt>
                    <dd>
                      {row.fixture ? (
                        t("Проведено", "Орындалды")
                      ) : (
                        <Status value={row.status} />
                      )}
                    </dd>
                  </div>
                </dl>
                {!row.fixture && (
                  <TransferHistory id={row.transfer_id} status={row.status} />
                )}
              </details>
            );
          })}
        </div>
      ))}
      {shown.length > 8 && (
        <Button data-variant="quiet" onClick={() => showAll(!full)}>
          {full
            ? t("Свернуть историю", "Тарихты жинау")
            : t("Показать все операции", "Барлық операцияны көрсету")}
        </Button>
      )}
    </>
  );
}

export default function AccountHome({
  account,
  trustedName,
  onTransfer,
}: {
  account: ReturnType<typeof useAccount>;
  trustedName: string;
  onTransfer: (name: string, account: string) => void;
}) {
  const t = useText();
  const profile = useProfile();
  const { snapshot, history } = account;
  const [showNumber, setShowNumber] = useState(false);
  const [panel, selectPanel] = useState<
    "overview" | "cards" | "payments" | "history"
  >("overview");
  const [time] = useState(Date.now);
  const hour = Number(
    new Intl.DateTimeFormat("en-GB", {
      timeZone,
      hour: "2-digit",
      hourCycle: "h23",
    }).format(time),
  );
  const greeting =
    hour < 6
      ? t("Доброй ночи", "Қайырлы түн")
      : hour < 12
        ? t("Доброе утро", "Қайырлы таң")
        : hour < 18
          ? t("Добрый день", "Қайырлы күн")
          : t("Добрый вечер", "Қайырлы кеш");
  return (
    <div className="client-home">
      <h1 suppressHydrationWarning>
        {greeting}, {profile.firstName}
      </h1>
      <div className="client-columns">
        <div className="client-primary">
          <section className="balance-panel">
            <div className="balance-top">
              <span>{t("Доступно", "Қолжетімді")}</span>
              <ShieldCheck aria-hidden="true" />
            </div>
            <strong className="balance-amount" data-testid="available-amount">
              {snapshot ? <Money amount={snapshot.available} /> : "—"}
            </strong>
            <div className="balance-reserve">
              <span>
                {t("Заблокировано под проверку", "Тексеруге бұғатталған")}
              </span>
              <strong data-testid="reserved-amount">
                {snapshot ? <Money amount={snapshot.reserved} /> : "—"}
              </strong>
            </div>
            <div className="balance-card">
              <CreditCard size={20} aria-hidden="true" />
              <span>
                {t("Дебетовая карта", "Дебеттік карта")}{" "}
                <b>{showNumber ? "•••• " + profile.lastFour : "•••• ••••"}</b>
              </span>
              <button
                type="button"
                aria-label={
                  showNumber
                    ? t("Скрыть номер карты", "Карта нөмірін жасыру")
                    : t(
                        "Показать последние цифры карты",
                        "Картаның соңғы цифрларын көрсету",
                      )
                }
                onClick={() => setShowNumber(!showNumber)}
              >
                {showNumber ? (
                  <EyeOff size={18} aria-hidden="true" />
                ) : (
                  <Eye size={18} aria-hidden="true" />
                )}
              </button>
            </div>
          </section>
          <div className="client-actions">
            <Chip onClick={() => onTransfer("", "")}>
              <ArrowLeftRight aria-hidden="true" />
              {t("Перевод", "Аударым")}
            </Chip>
            <Chip
              aria-pressed={panel === "payments"}
              onClick={() =>
                selectPanel(panel === "payments" ? "overview" : "payments")
              }
            >
              <ReceiptText aria-hidden="true" />
              {t("Платежи", "Төлемдер")}
            </Chip>
            <Chip
              aria-pressed={panel === "cards"}
              onClick={() =>
                selectPanel(panel === "cards" ? "overview" : "cards")
              }
            >
              <CreditCard aria-hidden="true" />
              {t("Карты", "Карталар")}
            </Chip>
            <Chip
              aria-pressed={panel === "history"}
              onClick={() =>
                selectPanel(panel === "history" ? "overview" : "history")
              }
            >
              <History aria-hidden="true" />
              {t("История", "Тарих")}
            </Chip>
          </div>
          {panel === "payments" && (
            <Card className="client-subpanel">
              <h2>{t("Платежи", "Төлемдер")}</h2>
              <p>
                {t(
                  "Для учебного платежа выберите получателя и укажите сумму.",
                  "Оқу төлемі үшін алушыны таңдап, соманы көрсетіңіз.",
                )}
              </p>
              <div className="client-chips">
                {[
                  ["Алматы Су", "KZ000000000000000201"],
                  ["Beeline", "KZ000000000000000202"],
                  ["Kazakhtelecom", "KZ000000000000000203"],
                ].map(([name, number]) => (
                  <Chip key={number} onClick={() => onTransfer(name, number)}>
                    {name}
                  </Chip>
                ))}
              </div>
            </Card>
          )}
          {panel === "cards" && (
            <Card className="client-subpanel">
              <h2>{t("Дебетовая карта", "Дебеттік карта")}</h2>
              <p>{profile.cardholder} / KZT</p>
              <p>
                {t("Баланс карты", "Карта балансы")}{" "}
                <b>{snapshot ? <Money amount={snapshot.balance} /> : "—"}</b>
              </p>
            </Card>
          )}
          {panel === "overview" && (
            <div className="client-recipients">
              <h2>{t("Сохранённые получатели", "Сақталған алушылар")}</h2>
              <div className="client-chips">
                {profile.contacts.map((contact) => (
                  <Chip
                    key={contact.account}
                    onClick={() =>
                      onTransfer(
                        t(contact.name[0], contact.name[1]),
                        contact.account,
                      )
                    }
                  >
                    <span aria-hidden="true">
                      {t(contact.name[0], contact.name[1])[0]}
                    </span>
                    {t(contact.name[0], contact.name[1])}
                  </Chip>
                ))}
              </div>
            </div>
          )}
          <Card className="client-statement">
            <div className="statement-mode">
              <Wallet size={14} aria-hidden="true" />
              {t("Учебные данные", "Оқу деректері")}
            </div>
            {history.isPending && <Skeleton />}
            <ErrorBox error={history.error} />
            {snapshot && <Statement entries={snapshot.entries} />}
          </Card>
        </div>
        <Protection contact={trustedName} />
      </div>
    </div>
  );
}
