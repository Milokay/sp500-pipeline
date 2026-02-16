"use client";

export function formatValue(
  value: number | string | null | undefined,
  type: "percentage" | "currency" | "number" | "ratio" = "number",
  decimals: number = 2
): string {
  if (value === null || value === undefined || value === "" || (typeof value === "number" && isNaN(value))) {
    return "\u2014";
  }

  const num = typeof value === "string" ? parseFloat(value) : value;
  if (isNaN(num)) return "\u2014";

  switch (type) {
    case "percentage": {
      const pct = num * 100;
      const sign = pct > 0 ? "+" : "";
      return `${sign}${pct.toFixed(decimals)}%`;
    }
    case "currency":
      return `$${num.toLocaleString("en-US", { minimumFractionDigits: decimals, maximumFractionDigits: decimals })}`;
    case "ratio":
      return num.toFixed(decimals);
    case "number":
    default:
      return num.toLocaleString("en-US", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
  }
}

export function formatPercentageRaw(
  value: number | null | undefined,
  decimals: number = 1
): string {
  if (value === null || value === undefined || isNaN(value)) return "\u2014";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(decimals)}%`;
}

export function percentageColor(value: number | null | undefined): string {
  if (value === null || value === undefined || isNaN(value)) return "text-slate-600";
  if (value > 0) return "text-emerald-400";
  if (value < 0) return "text-red-400";
  return "text-slate-400";
}

export function percentageColorFromDecimal(value: number | null | undefined): string {
  if (value === null || value === undefined || isNaN(value)) return "text-slate-600";
  if (value > 0) return "text-emerald-400";
  if (value < 0) return "text-red-400";
  return "text-slate-400";
}

export function safeNumber(value: unknown): number | null {
  if (value === null || value === undefined || value === "") return null;
  const num = typeof value === "number" ? value : Number(value);
  return isNaN(num) ? null : num;
}
