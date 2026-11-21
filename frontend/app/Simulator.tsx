"use client";

import { useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  LabelList,
  Rectangle,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useBackendCapabilities } from "../lib/api";
import { api, ErrorBox, useAction, useText } from "./shared";
import { Badge, Button } from "./ui";

type Metrics = {
  stop_rate?: number;
  false_positive_rate?: number;
  stopped_scams?: number;
  legit_questioned_rate?: number;
  avg_delay_seconds?: number;
};
type Report = {
  total_scenarios: number;
  baseline: Metrics;
  qaqpan: Metrics;
  available_splits?: string[];
};
type SimulationResponse = {
  status: string;
  benchmark?: Report;
  available_splits?: string[];
};

export default function Simulator() {
  const t = useText();
  const action = useAction();
  const backend = useBackendCapabilities();
  const [split, setSplit] = useState("test");
  const [holdout, setHoldout] = useState(false);
  const [report, setReport] = useState<Report>();
  const fmt = new Intl.NumberFormat(t("ru-KZ", "kk-KZ"), {
    maximumFractionDigits: 1,
  });
  const baselineLabel = t("Лимит 500 000 ₸", "500 000 ₸ шегі");
  const formatRate = (value: number) => fmt.format(value * 100) + "%";
  const chartValue = (value: unknown) =>
    typeof value === "number" ? fmt.format(value) + "%" : "";
  const series = report
    ? (
        [
          ["stop_rate", t("Остановлены", "Тоқтатылды")],
          ["false_positive_rate", t("Ложные тревоги", "Жалған дабылдар")],
        ] as const
      ).flatMap(([key, name]) => {
        const baseline = report.baseline[key],
          qaqpan = report.qaqpan[key];
        const baselineValue =
          typeof baseline === "number" && Number.isFinite(baseline)
            ? baseline * 100
            : null;
        const qaqpanValue =
          typeof qaqpan === "number" && Number.isFinite(qaqpan)
            ? qaqpan * 100
            : null;
        if (baselineValue === null && qaqpanValue === null) {
          return key === "false_positive_rate"
            ? [
                {
                  name: name + " — " + t("нет данных", "дерек жоқ"),
                  baseline: null,
                  qaqpan: null,
                },
              ]
            : [];
        }
        return [{ name, baseline: baselineValue, qaqpan: qaqpanValue }];
      })
    : [];
  const metrics = [
    [
      t("Дополнительные вопросы", "Қосымша сұрақтар"),
      report?.qaqpan.legit_questioned_rate,
      formatRate,
    ],
    [
      t("Средняя задержка", "Орташа кідіріс"),
      report?.qaqpan.avg_delay_seconds,
      (value: number) => fmt.format(value) + " " + t("с", "с"),
    ],
    [
      t("Остановлено переводов", "Тоқтатылған аударымдар"),
      report?.qaqpan.stopped_scams,
      (value: number) => fmt.format(value),
    ],
  ] as const;
  return (
    <section className="analyst-tool analyst-simulator">
      <div className="analyst-tool-header">
        <div>
          <h2>
            {t(
              "Проверка на синтетических данных",
              "Синтетикалық деректердегі тексеріс",
            )}
          </h2>
          <p className="sim-note">
            {t(
              "Учебная модель, синтетические данные",
              "Оқу моделі, синтетикалық деректер",
            )}
          </p>
        </div>
        <div className="sim-controls">
          <label>
            {t("Выборка", "Іріктеме")}
            <select
              value={split}
              disabled={action.isPending}
              onChange={(event) => setSplit(event.target.value)}
            >
              <option value="test">test</option>
              {(holdout || backend.holdout3) && (
                <option value="holdout3">holdout3</option>
              )}
            </select>
          </label>
          <Button
            type="button"
            disabled={action.isPending}
            onClick={() =>
              action.mutate(async () => {
                const result = await api<SimulationResponse>(
                  "/benchmark/simulate?" +
                    new URLSearchParams({ split, count: "500" }),
                );
                if (!result.benchmark) throw Error("benchmark");
                const supportsHoldout =
                  (
                    result.available_splits ?? result.benchmark.available_splits
                  )?.includes("holdout3") ?? false;
                setHoldout(supportsHoldout);
                if (!supportsHoldout && !backend.holdout3) setSplit("test");
                setReport(result.benchmark);
              })
            }
          >
            {t("Запустить", "Іске қосу")}
          </Button>
        </div>
      </div>
      {action.isPending && (
        <div className="sim-running">
          <span role="status">
            {t("Сравниваем модели…", "Модельдер салыстырылуда…")}
          </span>
          <progress
            aria-label={t("Выполнение проверки", "Тексерудің орындалуы")}
          />
        </div>
      )}
      {report && (
        <div className="sim-results">
          <div className="sim-result-title">
            <h3>{t("До и после", "Дейін және кейін")}</h3>
            <span>
              {t("Сценариев", "Сценарий саны")} {report.total_scenarios}
            </span>
          </div>
          {series.length > 0 && (
            <div className="sim-chart">
              <ResponsiveContainer width="100%" height="100%" minWidth={0}>
                <BarChart
                  data={series}
                  barSize={37}
                  margin={{ top: 22, right: 6, left: 0, bottom: 0 }}
                >
                  <CartesianGrid
                    stroke="#e3ebe5"
                    strokeDasharray="3 4"
                    vertical={false}
                  />
                  <XAxis
                    dataKey="name"
                    tick={{ fontSize: 12 }}
                    tickLine={false}
                    axisLine={false}
                  />
                  <YAxis
                    domain={[0, 100]}
                    width={45}
                    tickFormatter={(value) => value + "%"}
                    tick={{ fontSize: 11 }}
                    tickLine={false}
                    axisLine={false}
                  />
                  <Tooltip formatter={chartValue} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Bar
                    dataKey="baseline"
                    name={baselineLabel}
                    fill="#779489"
                    radius={[5, 5, 0, 0]}
                    shape={<Rectangle />}
                    isAnimationActive={false}
                  >
                    <LabelList
                      position="top"
                      offset={4}
                      fill="var(--text)"
                      fontSize={11}
                      formatter={chartValue}
                    />
                  </Bar>
                  <Bar
                    dataKey="qaqpan"
                    name="Qaqpan"
                    fill="#176549"
                    radius={[5, 5, 0, 0]}
                    shape={<Rectangle />}
                    isAnimationActive={false}
                  >
                    <LabelList
                      position="top"
                      offset={4}
                      fill="var(--text)"
                      fontSize={11}
                      formatter={chartValue}
                    />
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
          <div className="sim-metrics">
            {metrics.map(([label, value, format]) =>
              typeof value === "number" && Number.isFinite(value) ? (
                <Badge key={label}>
                  {label} <b>{format(value)}</b>
                </Badge>
              ) : null,
            )}
          </div>
        </div>
      )}
      <ErrorBox error={action.error} />
    </section>
  );
}
