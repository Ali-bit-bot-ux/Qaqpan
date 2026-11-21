"use client";

import { useEffect, useRef } from "react";
import { MessageSquare, Plus } from "lucide-react";
import { ApiError } from "../lib/api";
import { dateValue } from "../lib/account";
import {
  api,
  useAction,
  useData,
  useText,
  type Models,
  ErrorBox,
  Status,
} from "./shared";
import { Button, Skeleton } from "./ui";

export default function Trap({
  id,
  select,
}: {
  id: string;
  select: (id: string) => void;
}) {
  const t = useText();
  const action = useAction();
  const sessions = useData<Models["TrapSessionResponse"][]>("/trap/sessions");
  const path = "/trap/sessions/" + id;
  const detail = useData<Models["TrapSessionDetailResponse"]>(id ? path : "");
  const session = detail.data;
  const transcript = useRef<HTMLDivElement>(null);
  const messageCount = session?.messages?.length;
  useEffect(() => {
    const pane = transcript.current;
    if (pane) pane.scrollTop = pane.scrollHeight;
  }, [id, messageCount]);
  const newDialog = () =>
    action.mutate(async () => {
      const created = await api<Models["TrapSessionResponse"]>(
        "/trap/sessions",
        { language: t("ru", "kz") },
      );
      select(created.session_id);
    });
  const formatDate = new Intl.DateTimeFormat(t("ru-KZ", "kk-KZ"), {
    timeZone: "Asia/Almaty",
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
  const listedSessions = sessions.data ?? [];
  const activeIndex = listedSessions.findIndex(
    (item) => item.session_id === id,
  );
  const dialogTitle = (createdAt: string, number?: number) =>
    t("Диалог", "Диалог") +
    (number === undefined ? "" : " " + number) +
    " · " +
    formatDate.format(dateValue(createdAt));
  return (
    <section className="analyst-tool analyst-trap">
      <div className="analyst-tool-header">
        <h2>{t("Учебный диалог", "Оқу диалогы")}</h2>
        <Button
          type="button"
          data-variant="quiet"
          disabled={action.isPending}
          onClick={newDialog}
        >
          <Plus size={16} aria-hidden="true" />
          {t("Новый диалог", "Жаңа диалог")}
        </Button>
      </div>
      <div className="trap-layout">
        <aside
          className="trap-sidebar"
          aria-label={t("Список диалогов", "Диалогтар тізімі")}
        >
          <h3>{t("Диалоги", "Диалогтар")}</h3>
          {sessions.isPending && <Skeleton />}
          <ErrorBox error={sessions.error} />
          {sessions.data?.length === 0 && (
            <p>{t("Список пока пуст", "Тізім әзірге бос")}</p>
          )}
          <ul>
            {listedSessions.map((item, index) => (
              <li key={item.session_id}>
                <button
                  type="button"
                  className="trap-session"
                  aria-pressed={id === item.session_id}
                  onClick={() => {
                    action.reset();
                    select(item.session_id);
                  }}
                >
                  <MessageSquare size={15} aria-hidden="true" />
                  <span>
                    <strong>
                      {dialogTitle(
                        item.created_at,
                        listedSessions.length - index,
                      )}
                    </strong>
                    <Status value={item.status} />
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </aside>
        <div className="trap-chat">
          {!id ? (
            <div className="trap-empty">
              <MessageSquare size={24} aria-hidden="true" />
              <p>{t("Начните новый диалог", "Жаңа диалог бастаңыз")}</p>
              <Button
                type="button"
                disabled={action.isPending}
                onClick={newDialog}
              >
                {t("Новый диалог", "Жаңа диалог")}
              </Button>
            </div>
          ) : detail.isPending ? (
            <Skeleton />
          ) : session ? (
            <>
              <header className="trap-chat-header">
                <div>
                  <strong>
                    {dialogTitle(
                      session.created_at,
                      activeIndex < 0
                        ? undefined
                        : listedSessions.length - activeIndex,
                    )}
                  </strong>
                  <Status value={session.status} />
                </div>
                {session.status === "ACTIVE" && (
                  <Button
                    type="button"
                    data-variant="quiet"
                    disabled={action.isPending}
                    onClick={() =>
                      action.mutate(async () => {
                        await api(path + "/stop", {});
                      })
                    }
                  >
                    {t("Завершить", "Аяқтау")}
                  </Button>
                )}
              </header>
              <div
                className="trap-transcript"
                ref={transcript}
                role="log"
                aria-label={t("Сообщения диалога", "Диалог хабарламалары")}
                tabIndex={0}
              >
                {!session.messages?.length && (
                  <p className="trap-hint">
                    {t(
                      "Введите первое тестовое сообщение от лица мошенника.",
                      "Алаяқ атынан алғашқы сынақ хабарламасын жазыңыз.",
                    )}
                  </p>
                )}
                {session.messages?.map((message) => (
                  <div
                    key={message.id}
                    className="trap-bubble"
                    data-side={message.sender === "SCAMMER" ? "left" : "right"}
                  >
                    <strong>
                      {message.sender === "SCAMMER"
                        ? t("Мошенник", "Алаяқ")
                        : t("Qaqpan в роли клиента", "Qaqpan клиент рөлінде")}
                    </strong>
                    <p>{message.text}</p>
                  </div>
                ))}
                {session.recipients?.map((recipient) => (
                  <article key={recipient.id} className="trap-recipient">
                    <div>
                      <strong>
                        {t("Найденный реквизит", "Табылған деректеме")}
                      </strong>
                      <Status value={recipient.status} />
                    </div>
                    <b>{recipient.value}</b>
                    <blockquote>{recipient.quote}</blockquote>
                    {recipient.status === "NEW" && (
                      <div className="trap-recipient-actions">
                        {(["CONFIRMED", "REJECTED"] as const).map(
                          (decision) => (
                            <Button
                              type="button"
                              data-variant="quiet"
                              key={decision}
                              disabled={action.isPending}
                              onClick={() =>
                                action.mutate(async () => {
                                  await api(
                                    "/trap/recipients/" +
                                      recipient.id +
                                      "/decision",
                                    { decision },
                                  );
                                })
                              }
                            >
                              {decision === "CONFIRMED"
                                ? t("Подтвердить", "Растау")
                                : t("Отклонить", "Қабылдамау")}
                            </Button>
                          ),
                        )}
                      </div>
                    )}
                  </article>
                ))}
              </div>
              {session.status === "ACTIVE" && (
                <form
                  className="trap-composer"
                  onSubmit={(event) => {
                    event.preventDefault();
                    const form = event.currentTarget;
                    const text = new FormData(form).get("text");
                    action.mutate(async () => {
                      await api(path + "/messages", { text });
                      form.reset();
                    });
                  }}
                >
                  <textarea
                    aria-label={t("Тестовое сообщение", "Сынақ хабарламасы")}
                    placeholder={t(
                      "Сообщение от лица мошенника",
                      "Алаяқ атынан хабарлама",
                    )}
                    aria-invalid={
                      action.error instanceof ApiError &&
                      action.error.field("text")
                    }
                    name="text"
                    required
                    maxLength={2000}
                    rows={2}
                  />
                  <Button
                    disabled={
                      action.isPending ||
                      session.message_count >= session.max_messages
                    }
                  >
                    {t("Отправить", "Жіберу")}
                  </Button>
                </form>
              )}
            </>
          ) : null}
        </div>
      </div>
      <ErrorBox error={action.error || detail.error} />
    </section>
  );
}
