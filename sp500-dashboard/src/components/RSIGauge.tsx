"use client";

interface RSIGaugeProps {
  value: number | null | undefined;
  size?: number;
}

export default function RSIGauge({ value, size = 120 }: RSIGaugeProps) {
  if (value === null || value === undefined || isNaN(value)) {
    return (
      <div className="flex flex-col items-center">
        <div style={{ width: size, height: size / 2 + 10 }} className="flex items-center justify-center">
          <span className="text-slate-600 text-sm">{"\u2014"}</span>
        </div>
      </div>
    );
  }

  const clampedRSI = Math.max(0, Math.min(100, value));
  const radius = size / 2 - 8;
  const cx = size / 2;
  const cy = size / 2;

  // Semicircle from 180 to 0 degrees (left to right)
  const angle = Math.PI - (clampedRSI / 100) * Math.PI;
  const needleX = cx + radius * 0.75 * Math.cos(angle);
  const needleY = cy - radius * 0.75 * Math.sin(angle);

  // Determine color zones
  let valueColor = "text-slate-300";
  let zoneLabel = "Neutral";
  if (clampedRSI >= 70) {
    valueColor = "text-red-400";
    zoneLabel = "Overbought";
  } else if (clampedRSI <= 30) {
    valueColor = "text-emerald-400";
    zoneLabel = "Oversold";
  }

  // Arc path helper
  function arcPath(startAngle: number, endAngle: number, r: number): string {
    const startX = cx + r * Math.cos(startAngle);
    const startY = cy - r * Math.sin(startAngle);
    const endX = cx + r * Math.cos(endAngle);
    const endY = cy - r * Math.sin(endAngle);
    const largeArc = endAngle - startAngle > Math.PI ? 1 : 0;
    return `M ${startX} ${startY} A ${r} ${r} 0 ${largeArc} 0 ${endX} ${endY}`;
  }

  return (
    <div className="flex flex-col items-center">
      <svg width={size} height={size / 2 + 20} viewBox={`0 0 ${size} ${size / 2 + 20}`}>
        {/* Oversold zone (0-30): green */}
        <path
          d={arcPath(Math.PI, Math.PI * 0.7, radius)}
          fill="none"
          stroke="#064e3b"
          strokeWidth={8}
          strokeLinecap="round"
        />
        {/* Neutral zone (30-70): gray */}
        <path
          d={arcPath(Math.PI * 0.7, Math.PI * 0.3, radius)}
          fill="none"
          stroke="#1e293b"
          strokeWidth={8}
          strokeLinecap="round"
        />
        {/* Overbought zone (70-100): red */}
        <path
          d={arcPath(Math.PI * 0.3, 0, radius)}
          fill="none"
          stroke="#7f1d1d"
          strokeWidth={8}
          strokeLinecap="round"
        />
        {/* Needle */}
        <line
          x1={cx}
          y1={cy}
          x2={needleX}
          y2={needleY}
          stroke="#f8fafc"
          strokeWidth={2}
          strokeLinecap="round"
        />
        <circle cx={cx} cy={cy} r={3} fill="#f8fafc" />
        {/* Labels */}
        <text x={4} y={cy + 14} className="fill-slate-500 text-[9px]">0</text>
        <text x={size - 14} y={cy + 14} className="fill-slate-500 text-[9px]">100</text>
      </svg>
      <div className="flex flex-col items-center -mt-1">
        <span className={`font-mono text-lg font-bold ${valueColor}`}>{clampedRSI.toFixed(1)}</span>
        <span className="text-[10px] text-slate-500">{zoneLabel}</span>
      </div>
    </div>
  );
}
