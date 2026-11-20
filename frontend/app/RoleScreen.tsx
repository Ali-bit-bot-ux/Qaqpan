"use client";
import { useState, useEffect, type ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Fingerprint, Languages } from "lucide-react";
import { profile } from "../lib/profile-data";
import { useStoredValue } from "../lib/storage";
import { Language, Sync } from "./shared";
const screens = {
  client: [
    ["Личный кабинет", "Жеке кабинет"],
    ["Мой банк", "Менің банкім"],
  ],
  trusted: [
    ["Доверенное лицо", "Сенімді тұлға"],
    ["Запросы близких", "Жақындардың сұраулары"],
  ],
  analyst: [
    ["Банк · Антифрод", "Банк · Антифрод"],
    ["Мониторинг операций", "Операциялар мониторингі"],
  ],
};
export default function RoleScreen({
  role,
  children,
}: {
  role: keyof typeof screens;
  children: ReactNode;
}) {
  const [qc] = useState(() => new QueryClient());
  const [language, setLanguage] = useStoredValue("q-lang", "localStorage");
  const kz = language === "kz";
  const [label, title] = screens[role];
  const lang = kz ? 1 : 0;
  useEffect(() => {
    document.documentElement.lang = kz ? "kk" : "ru";
    document.title = title[lang] + " · Қақпан";
  }, [kz, lang, title]);
  return (
    <QueryClientProvider client={qc}>
      <Language.Provider value={kz}>
        {role !== "client" && <Sync />}
        <div className={"portal portal-" + role}>
          <header className="masthead">
            <b>
              <Fingerprint aria-hidden />
              Қақпан
            </b>
            <span>
              {label[lang]}
              {role === "trusted" && <> / {profile.trustedName[lang]}</>}
            </span>
            <button
              className="language"
              onClick={() => {
                setLanguage(kz ? "ru" : "kz");
              }}
            >
              <Languages size={17} aria-hidden="true" />
              {kz ? "Русский" : "Қазақша"}
            </button>
          </header>
          <main>
            {role !== "client" && <h1>{title[lang]}</h1>}
            {children}
          </main>
        </div>
      </Language.Provider>
    </QueryClientProvider>
  );
}
