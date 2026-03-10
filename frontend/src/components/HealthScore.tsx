import { useMemo } from 'react';

interface HealthScoreProps {
  score: number | null;
  size?: 'sm' | 'md' | 'lg';
  showLabel?: boolean;
}

export default function HealthScore({
  score,
  size = 'md',
  showLabel = true,
}: HealthScoreProps) {
  const { color, bgColor, label, radius, strokeWidth, fontSize } =
    useMemo(() => {
      const s = score ?? 0;
      let color: string;
      let bgColor: string;
      let label: string;

      if (score === null) {
        color = '#6b7280';
        bgColor = 'rgba(107, 114, 128, 0.1)';
        label = 'No data';
      } else if (s >= 7) {
        color = '#22c55e';
        bgColor = 'rgba(34, 197, 94, 0.1)';
        label = 'Healthy';
      } else if (s >= 4) {
        color = '#eab308';
        bgColor = 'rgba(234, 179, 8, 0.1)';
        label = 'At risk';
      } else {
        color = '#ef4444';
        bgColor = 'rgba(239, 68, 68, 0.1)';
        label = 'Critical';
      }

      const dimensions = {
        sm: { radius: 28, strokeWidth: 4, fontSize: 'text-sm' },
        md: { radius: 44, strokeWidth: 5, fontSize: 'text-2xl' },
        lg: { radius: 64, strokeWidth: 6, fontSize: 'text-4xl' },
      };

      return { color, bgColor, label, ...dimensions[size] };
    }, [score, size]);

  const circumference = 2 * Math.PI * radius;
  const normalizedScore = score !== null ? Math.min(10, Math.max(0, score)) : 0;
  const progress = (normalizedScore / 10) * circumference;
  const svgSize = (radius + strokeWidth) * 2;

  return (
    <div className="flex flex-col items-center gap-1">
      <div className="relative" style={{ width: svgSize, height: svgSize }}>
        <svg
          width={svgSize}
          height={svgSize}
          viewBox={`0 0 ${svgSize} ${svgSize}`}
          className="-rotate-90"
        >
          <circle
            cx={radius + strokeWidth}
            cy={radius + strokeWidth}
            r={radius}
            fill={bgColor}
            stroke="#1e293b"
            strokeWidth={strokeWidth}
          />
          {score !== null && (
            <circle
              cx={radius + strokeWidth}
              cy={radius + strokeWidth}
              r={radius}
              fill="none"
              stroke={color}
              strokeWidth={strokeWidth}
              strokeLinecap="round"
              strokeDasharray={circumference}
              strokeDashoffset={circumference - progress}
              className="transition-all duration-1000 ease-out"
            />
          )}
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <span className={`${fontSize} font-bold`} style={{ color }}>
            {score !== null ? score.toFixed(1) : '--'}
          </span>
        </div>
      </div>
      {showLabel && (
        <span
          className="text-xs font-medium uppercase tracking-wider"
          style={{ color }}
        >
          {label}
        </span>
      )}
    </div>
  );
}
