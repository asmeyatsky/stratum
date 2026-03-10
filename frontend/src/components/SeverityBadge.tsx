import type { Severity } from '../types';

interface SeverityBadgeProps {
  severity: Severity;
  className?: string;
}

const severityConfig: Record<
  Severity,
  { bg: string; text: string; label: string }
> = {
  critical: {
    bg: 'bg-red-500/15',
    text: 'text-red-400',
    label: 'Critical',
  },
  high: {
    bg: 'bg-orange-500/15',
    text: 'text-orange-400',
    label: 'High',
  },
  medium: {
    bg: 'bg-yellow-500/15',
    text: 'text-yellow-400',
    label: 'Medium',
  },
  low: {
    bg: 'bg-green-500/15',
    text: 'text-green-400',
    label: 'Low',
  },
  minimal: {
    bg: 'bg-gray-500/15',
    text: 'text-gray-400',
    label: 'Minimal',
  },
};

export default function SeverityBadge({
  severity,
  className = '',
}: SeverityBadgeProps) {
  const config = severityConfig[severity];

  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${config.bg} ${config.text} ${className}`}
    >
      {config.label}
    </span>
  );
}
