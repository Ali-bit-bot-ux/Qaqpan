export function formatAmount(value: string) {
  const [whole, ...decimals] = value.replace(/[^0-9,.]/g, "").split(/[,.]/);
  const formatted = whole.replace(/\B(?=(\d{3})+(?!\d))/g, "\u00a0");
  return decimals.length
    ? formatted + "," + decimals.join("").slice(0, 2)
    : formatted;
}

export function parseAmount(value: string) {
  return Number(value.replace(/\s/g, "").replace(",", "."));
}

export function formatRecipient(value: string) {
  const compact = value.replace(/\s/g, "").toUpperCase();
  if (/^\+77\d{9}$/.test(compact)) {
    return compact.replace(
      /^(\+7)(\d{3})(\d{3})(\d{2})(\d{2})$/,
      "$1 $2 $3 $4 $5",
    );
  }
  if (/^KZ\d{2}[A-Z0-9]{16}$/.test(compact)) return compact;
  return null;
}
