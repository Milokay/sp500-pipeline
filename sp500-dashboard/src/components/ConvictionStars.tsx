"use client";

interface ConvictionStarsProps {
  level: number | null | undefined;
  size?: "sm" | "md" | "lg";
}

const sizeClasses = {
  sm: "text-xs",
  md: "text-sm",
  lg: "text-base",
};

export default function ConvictionStars({ level, size = "md" }: ConvictionStarsProps) {
  const safeLevel = typeof level === "number" && !isNaN(level) ? Math.max(0, Math.min(5, Math.round(level))) : 0;

  return (
    <span className={`inline-flex gap-0.5 ${sizeClasses[size]}`} aria-label={`Conviction: ${safeLevel} out of 5`}>
      {Array.from({ length: 5 }, (_, i) => (
        <span key={i} className={i < safeLevel ? "text-amber-400" : "text-slate-600"}>
          {"\u2605"}
        </span>
      ))}
    </span>
  );
}
