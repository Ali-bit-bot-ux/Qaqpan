import { profile } from "./profile-data";
import type { components } from "../app/schema";

export type Entry = Pick<
  components["schemas"]["AnalystCard"],
  "transfer_id" | "recipient_name" | "created_at" | "amount" | "status"
> & {
  fixture?: true;
  category?: "income" | "groceries" | "utilities" | "qr" | "home" | "transfer";
  nameKz?: string;
};

const openingBalance = 920_000;
const fixtures: ReadonlyArray<
  [number, string, string, number, NonNullable<Entry["category"]>]
> = [
  [0, "Magnum", "Magnum", 15640, "groceries"],
  [1, "Алматы Су", "Алматы Су", 3180, "utilities"],
  [2, "Арман", "Арман", 12000, "transfer"],
  [3, "Kaspi QR", "Kaspi QR", 2850, "qr"],
  [4, "Пенсия", "Зейнетақы", -174500, "income"],
  [5, "Small", "Small", 9380, "groceries"],
  [6, "Beeline", "Beeline", 3490, "utilities"],
  [8, "Аренда квартиры", "Пәтер жалдау", 85000, "home"],
  [9, "Kaspi QR", "Kaspi QR", 4200, "qr"],
  [10, ...profile.trustedName, 20000, "transfer"],
  [12, "Kazakhtelecom", "Қазақтелеком", 7400, "utilities"],
  [14, "Magnum", "Magnum", 11460, "groceries"],
  [15, "Small", "Small", 6820, "groceries"],
  [17, "Kaspi QR", "Kaspi QR", 1700, "qr"],
  [18, "Арман", "Арман", 8500, "transfer"],
  [20, "Magnum", "Magnum", 10800, "groceries"],
  [22, "Kaspi QR", "Kaspi QR", 5600, "qr"],
  [24, "Алматы Су", "Алматы Су", 2940, "utilities"],
  [26, "Small", "Small", 12400, "groceries"],
  [28, "Magnum", "Magnum", 15120, "groceries"],
  [29, ...profile.trustedName, 10000, "transfer"],
  [31, "Kaspi QR", "Kaspi QR", 2800, "qr"],
  [33, "Beeline", "Beeline", 3490, "utilities"],
  [34, "Пенсия", "Зейнетақы", -174500, "income"],
  [35, "Аренда квартиры", "Пәтер жалдау", 85000, "home"],
  [37, "Small", "Small", 7720, "groceries"],
  [39, "Kazakhtelecom", "Қазақтелеком", 7400, "utilities"],
  [41, "Magnum", "Magnum", 13450, "groceries"],
  [43, "Арман", "Арман", 5000, "transfer"],
  [45, "Kaspi QR", "Kaspi QR", 4500, "qr"],
  [48, "Magnum", "Magnum", 11050, "groceries"],
  [50, ...profile.trustedName, 15000, "transfer"],
  [52, "Small", "Small", 6600, "groceries"],
  [55, "Kaspi QR", "Kaspi QR", 3200, "qr"],
  [58, "Magnum", "Magnum", 12460, "groceries"],
];
const pending = new Set<Entry["status"]>([
  "SUBMITTED",
  "EVALUATING",
  "AWAITING_ANSWER",
  "TRUSTED_PENDING",
  "COOLING_OFF",
  "MANUAL_BANK_REVIEW",
]);

export function dateValue(value: string) {
  return new Date(/Z$|[+-]\d\d:\d\d$/.test(value) ? value : value + "Z");
}

export function accountSnapshot(remote: Entry[], active?: Entry) {
  const sample = fixtures.map(
    ([days, recipient_name, nameKz, amount, category], index): Entry => ({
      transfer_id: "Q-" + (81000 - index),
      recipient_name,
      nameKz,
      amount,
      category,
      created_at: new Date(
        Date.now() - days * 86_400_000 - (index % 3) * 3_600_000,
      ).toISOString(),
      status: "COMPLETED",
      fixture: true,
    }),
  );
  const real = new Map(remote.map((entry) => [entry.transfer_id, entry]));
  if (active) {
    const recent = real.get(active.transfer_id);
    if (!recent || pending.has(recent.status))
      real.set(active.transfer_id, active);
  }
  const fixturesVisible = real.size < 15;
  const entries = real.size
    ? [...real.values(), ...(fixturesVisible ? sample : [])].sort(
        (a, b) => +dateValue(b.created_at) - +dateValue(a.created_at),
      )
    : sample;
  const seedNet = sample.reduce(
    (sum, row) => sum + Math.round(row.amount * 100),
    0,
  );
  const spent = [...real.values()].reduce(
    (sum, row) =>
      sum + (row.status === "COMPLETED" ? Math.round(row.amount * 100) : 0),
    0,
  );
  const reserved = [...real.values()].reduce(
    (sum, row) =>
      sum + (pending.has(row.status) ? Math.round(row.amount * 100) : 0),
    0,
  );
  const balance = (openingBalance * 100 - seedNet - spent) / 100;
  return {
    entries,
    balance,
    reserved: reserved / 100,
    available: balance - reserved / 100,
    fixture: fixturesVisible,
  };
}
