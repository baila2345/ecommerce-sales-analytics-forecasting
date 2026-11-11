export const currencyFormatter = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
  maximumFractionDigits: 0,
});

export const numberFormatter = new Intl.NumberFormat("vi-VN");

export function compactCurrency(value: number): string {
  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(value);
}

export function displayPeriod(period: string): string {
  const [year, month] = period.split("-");
  return `${month}/${year.slice(2)}`;
}
