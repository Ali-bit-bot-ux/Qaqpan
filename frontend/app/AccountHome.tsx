"use client";
import TransferHistory from "./TransferHistory";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowUpRight,
  ArrowLeftRight,
  History,
  ShieldCheck,
  Radio,
  ChevronDown,
  Eye,
  EyeOff,
} from "lucide-react";
import { useText, money, Status, ErrorBox, type Models } from "./shared";
type Entry = Pick<
  Models["AnalystCard"],
  "transfer_id" | "recipient_name" | "created_at" | "amount" | "status"
>;
const people = [
  { name: "Айгерим", kk: "Айгерім", account: "TEST-FAMILY-01" },
  { name: "Арман", kk: "Арман", account: "TEST-FAMILY-02" },
];
export default function AccountHome({
  onTransfer,
}: {
  onTransfer: (name: string, account: string) => void;
}) {
  const t = useText();
  const [hidden, hide] = useState(false),
    [filter, setFilter] = useState("ALL");
  const history = useQuery<Entry[]>({
    queryKey: ["account-history"],
    queryFn: async () => {
      const res = await fetch("/api/account", { cache: "no-store" });
      if (!res.ok) throw Error(String(res.status));
      return res.json();
    },
    refetchInterval: 15000,
    retry: false,
  });
  const entries = history.data || [];
  const shown = entries.filter((e) => filter === "ALL" || e.status === filter);
  return (
    <div className="bankhome">
      <div className="home-grid">
        <div className="bank-card">
          <div className="card-lines" aria-hidden="true" />
          <div className="bank-card-head">
            <b>Қақпан</b>
            <Radio aria-hidden="true" />
          </div>
          <p>{t("Дебетовая карта", "Дебеттік карта")} · KZT</p>
          <div className="card-number">
            {hidden ? "•••• ••••" : "•••• 4821"}{" "}
            <button
              aria-label={
                hidden
                  ? t("Показать номер", "Нөмірді көрсету")
                  : t("Скрыть номер", "Нөмірді жасыру")
              }
              onClick={() => hide(!hidden)}
            >
              {hidden ? <Eye size={17} /> : <EyeOff size={17} />}
            </button>
          </div>
          <div className="bank-card-end">
            <span>SAULE K.</span>
            <span>{t("Учебный счёт", "Оқу шоты")}</span>
          </div>
        </div>
        <section className="quick">
          <h2>{t("Перевести деньги", "Ақша аудару")}</h2>
          <button className="send-money" onClick={() => onTransfer("", "")}>
            <ArrowLeftRight />
            {t("Новый перевод", "Жаңа аударым")}
            <ArrowUpRight size={17} />
          </button>
          <h3>{t("Сохранённые получатели", "Сақталған алушылар")}</h3>
          <div className="persons">
            {people.map((p, i) => (
              <button
                key={p.account}
                onClick={() => onTransfer(t(p.name, p.kk), p.account)}
              >
                <i className={"avatar tint" + i}>{p.name[0]}</i>
                {t(p.name, p.kk)}
              </button>
            ))}
          </div>
        </section>
      </div>
      <div className="home-grid lower">
        <section>
          <h2>
            <History size={20} /> {t("Последние переводы", "Соңғы аударымдар")}
          </h2>
          <select
            aria-label={t("Фильтр истории", "Тарих сүзгісі")}
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          >
            <option value="ALL">
              {t("Все операции", "Барлық операциялар")}
            </option>
            <option value="COMPLETED">{t("Выполненные", "Орындалған")}</option>
            <option value="BLOCKED">{t("Остановленные", "Тоқтатылған")}</option>
          </select>
          {history.isLoading && <p>…</p>}
          <ErrorBox error={history.error} />
          {history.isSuccess && !shown.length && (
            <p>
              {t("Таких переводов пока нет.", "Мұндай аударым әзірге жоқ.")}
            </p>
          )}
          {shown.slice(0, 20).map((e) => (
            <details key={e.transfer_id} className="statement">
              <summary>
                <span className="opicon">
                  <ArrowUpRight size={18} />
                </span>
                <b>{e.recipient_name}</b>
                <strong>{money(e.amount)}</strong>
                <ChevronDown size={14} />
              </summary>
              <Status value={e.status} />
              <p>
                {new Date(
                  /Z$|[+-]\d\d:\d\d$/.test(e.created_at)
                    ? e.created_at
                    : e.created_at + "Z",
                ).toLocaleString(t("ru-KZ", "kk-KZ"))}{" "}
                · {e.transfer_id}
              </p>
              <TransferHistory id={e.transfer_id} status={e.status} />
            </details>
          ))}
        </section>
        <section className="family">
          <ShieldCheck />
          <h2>{t("Семейная защита", "Отбасылық қорғаныс")}</h2>
          <div className="who">
            <i className="avatar tint0">А</i>
            <div>
              <b>{t("Айгерим", "Айгерім")}</b>
              <small>
                {t("Дочь · доверенное лицо", "Қызы · сенімді тұлға")}
              </small>
            </div>
          </div>
          <details>
            <summary>
              {t("Когда дочь получит запрос?", "Қызыңызға сұрау қашан келеді?")}
            </summary>
            <p>
              {t(
                "При высоком риске Айгерим увидит сумму, получателя и причину проверки. Пока она решает, деньги остаются на счёте.",
                "Тәуекел жоғары болса, Айгерім соманы, алушыны және тексеру себебін көреді. Шешім қабылданғанша ақша шотта қалады.",
              )}
            </p>
          </details>
        </section>
      </div>
    </div>
  );
}
