"use client";

interface SignalBadgeProps {
  signal: string | null | undefined;
  size?: "sm" | "md";
}

function getSignalConfig(signal: string | null | undefined) {
  if (!signal) return { bg: "bg-slate-700", text: "text-slate-400", label: "\u2014" };

  const upper = signal.toUpperCase();
  if (upper.includes("BUY")) {
    const lowConf = upper.includes("LOW CONFIDENCE");
    return {
      bg: lowConf ? "bg-emerald-900/50" : "bg-emerald-900/70",
      text: lowConf ? "text-emerald-300" : "text-emerald-400",
      label: signal,
    };
  }
  if (upper.includes("SELL")) {
    const lowConf = upper.includes("LOW CONFIDENCE");
    return {
      bg: lowConf ? "bg-red-900/50" : "bg-red-900/70",
      text: lowConf ? "text-red-300" : "text-red-400",
      label: signal,
    };
  }
  if (upper.includes("HOLD")) {
    return { bg: "bg-amber-900/50", text: "text-amber-400", label: signal };
  }
  return { bg: "bg-slate-700", text: "text-slate-400", label: signal };
}

export default function SignalBadge({ signal, size = "md" }: SignalBadgeProps) {
  const { bg, text, label } = getSignalConfig(signal);
  const padding = size === "sm" ? "px-1.5 py-0.5 text-xs" : "px-2.5 py-1 text-xs";

  return (
    <span className={`inline-flex items-center rounded-full font-semibold whitespace-nowrap ${bg} ${text} ${padding}`}>
      {label}
    </span>
  );
}
