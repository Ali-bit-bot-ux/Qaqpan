"use client";

import {
  useEffect,
  useState,
  type ComponentProps,
  type ReactNode,
} from "react";
import { money, useText } from "./shared";

export function Button({ className = "", ...props }: ComponentProps<"button">) {
  return <button className={"bank-button " + className} {...props} />;
}

export function Card({ className = "", ...props }: ComponentProps<"section">) {
  return <section className={"bank-surface " + className} {...props} />;
}

export function Badge({ children }: { children: ReactNode }) {
  return <span className="bank-badge">{children}</span>;
}

export function Chip({ className = "", ...props }: ComponentProps<"button">) {
  return (
    <button type="button" className={"bank-chip " + className} {...props} />
  );
}

export function Money({ amount }: { amount: number }) {
  return <span className="bank-money">{money(amount)}</span>;
}

export function Timer({
  deadline,
  duration,
}: {
  deadline: number;
  duration: number;
}) {
  const t = useText();
  const [now, setNow] = useState(Date.now);
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);
  const left = Math.max(0, Math.ceil((deadline - now) / 1000));
  const progress = Math.min(1, left / Math.max(1, duration));
  return (
    <div
      className="bank-timer"
      role="timer"
      aria-label={t("До окончания ожидания", "Күту аяқталғанға дейін")}
    >
      <svg viewBox="0 0 68 68" aria-hidden="true">
        <circle cx="34" cy="34" r="30" />
        <circle
          cx="34"
          cy="34"
          r="30"
          pathLength={1}
          strokeDasharray={1}
          strokeDashoffset={1 - progress}
        />
      </svg>
      <time>
        {Math.floor(left / 60)}:{String(left % 60).padStart(2, "0")}
      </time>
    </div>
  );
}

export function Stepper({
  steps,
  current,
  label,
}: {
  steps: string[];
  current: number;
  label: string;
}) {
  return (
    <ol className="bank-steps" aria-label={label}>
      {steps.map((step, index) => (
        <li
          key={step}
          data-reached={index <= current}
          aria-current={index === current ? "step" : undefined}
        >
          {step}
        </li>
      ))}
    </ol>
  );
}

export function ErrorState({ children }: { children: ReactNode }) {
  return (
    <p className="bank-error" role="alert">
      {children}
    </p>
  );
}

export function Skeleton() {
  const t = useText();
  return (
    <div className="bank-skeleton" role="status" aria-busy="true">
      {t("Загрузка данных", "Деректер жүктелуде")}
    </div>
  );
}
