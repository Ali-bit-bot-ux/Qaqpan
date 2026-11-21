"use client";
import { useEffect, type ReactNode } from "react";
import { useConnection } from "./AppProvider";
import { Languages } from "lucide-react";
import { useStoredValue } from "../lib/storage";
import { Language } from "./shared";
import Logo from "./Logo";

const systemLabel = ["Учебная система", "Оқу жүйесі"];
const screens = {
  client: ["Мой банк", "Менің банкім"],
  trusted: ["Запросы близких", "Жақындардың сұраулары"],
  analyst: ["Мониторинг операций", "Операциялар мониторингі"],
};
export default function RoleScreen({
  role,
  children,
}: {
  role: keyof typeof screens;
  children: ReactNode;
}) {
  const status = useConnection();
  const [language, setLanguage] = useStoredValue("q-lang", "localStorage");
  const kz = language === "kz";
  const title = screens[role];
  const lang = kz ? 1 : 0;
  useEffect(() => {
    document.documentElement.lang = kz ? "kk" : "ru";
    document.title =
      title[lang] + (role === "analyst" ? " · Qaqpan" : " · Қақпан");
  }, [kz, lang, role, title]);
  return (
    <Language.Provider value={kz}>
      <div className={"portal portal-" + role}>
        <header className="masthead">
          <div className="masthead-inner">
            <div className="qaqpan-brand">
              <Logo />
              <div>
                <strong>Qaqpan</strong>
                <small>{kz ? "Отбасылық қорғаныс" : "Семейная защита"}</small>
              </div>
            </div>
            <div className="masthead-tools">
              <small>{systemLabel[lang]}</small>
              <button
                className="language"
                onClick={() => {
                  setLanguage(kz ? "ru" : "kz");
                }}
              >
                <Languages size={17} aria-hidden="true" />
                {kz ? "Русский" : "Қазақша"}
              </button>
            </div>
          </div>
        </header>
        <main>
          {status === "offline" && (
            <p className="connection-notice" role="status">
              {kz
                ? "Байланыс жоқ, қайта қосылып жатырмыз"
                : "Нет связи, пробуем снова"}
            </p>
          )}
          {role !== "client" && <h1>{title[lang]}</h1>}
          {children}
        </main>
      </div>
    </Language.Provider>
  );
}
