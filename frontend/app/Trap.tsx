"use client";
import {
  api,
  useAction,
  useData,
  useText,
  Models,
  ErrorBox,
  Status,
} from "./shared";
export default function Trap({
  id,
  select,
}: {
  id: string;
  select: (id: string) => void;
}) {
  const t = useText(),
    a = useAction(),
    q = useData<Models["TrapSessionDetailResponse"]>(
      id ? "/trap/sessions/" + id : "",
    ),
    s = q.data,
    path = "/trap/sessions/" + id;
  return (
    <section>
      <h2>{t("Учебный диалог", "Оқу диалогы")}</h2>
      <button
        disabled={a.isPending}
        onClick={() =>
          a.mutate(async () => {
            const r = await api<Models["TrapSessionResponse"]>(
              "/trap/sessions",
              { language: t("ru", "kz") },
            );
            select(r.session_id);
          })
        }
      >
        {t("Новый диалог", "Жаңа диалог")}
      </button>
      {s && (
        <article>
          <Status value={s.status} />
          {s.messages?.map((m) => (
            <p key={m.id}>
              <b>
                {m.sender === "BOT"
                  ? t("Бот", "Бот")
                  : t("Участник", "Қатысушы")}
              </b>{" "}
              · {m.text}
            </p>
          ))}
          {s.status === "ACTIVE" && (
            <>
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  const form = e.currentTarget,
                    text = new FormData(form).get("text");
                  a.mutate(async () => {
                    await api(path + "/messages", { text });
                    form.reset();
                  });
                }}
              >
                <label>
                  {t("Тестовое сообщение", "Сынақ хабарламасы")}
                  <textarea name="text" required maxLength={2000} />
                </label>
                <button
                  disabled={a.isPending || s.message_count >= s.max_messages}
                >
                  {t("Отправить", "Жіберу")}
                </button>
              </form>
              <button
                className="secondary"
                disabled={a.isPending}
                onClick={() =>
                  a.mutate(async () => {
                    await api(path + "/stop", {});
                  })
                }
              >
                {t("Завершить диалог", "Диалогты аяқтау")}
              </button>
            </>
          )}
          {s.recipients?.map((r) => (
            <article key={r.id}>
              <b>
                {r.recipient_type} · {r.value}
              </b>
              <blockquote>{r.quote}</blockquote>
              <Status value={r.status} />
              {r.status === "NEW" &&
                (["CONFIRMED", "REJECTED"] as const).map((d) => (
                  <button
                    disabled={a.isPending}
                    key={d}
                    onClick={() =>
                      a.mutate(async () => {
                        await api("/trap/recipients/" + r.id + "/decision", {
                          decision: d,
                        });
                      })
                    }
                  >
                    {d === "CONFIRMED"
                      ? t("Подтвердить реквизит", "Деректемені растау")
                      : t("Отклонить", "Қабылдамау")}
                  </button>
                ))}
            </article>
          ))}
        </article>
      )}
      <ErrorBox error={a.error || q.error} />
    </section>
  );
}
