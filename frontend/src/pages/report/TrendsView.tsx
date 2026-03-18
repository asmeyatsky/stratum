import { useState, useMemo } from 'react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  LineChart,
  Line,
  Legend,
} from 'recharts';
import type { FeatureBugTrend } from '../../types';
import ExportButton from '../../components/ExportButton';
import { useProjectContext } from '../ProjectDetail';

type TimeRange = '30' | '90' | '180';

interface CustomTooltipProps {
  active?: boolean;
  payload?: Array<{ name: string; value: number; color: string }>;
  label?: string;
}

function AreaTooltip({ active, payload, label }: CustomTooltipProps) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-navy-700 bg-navy-900 px-3 py-2 shadow-xl">
      <p className="mb-1.5 text-xs font-medium text-navy-400">{label}</p>
      {payload.map((entry, i) => (
        <p key={i} className="text-xs" style={{ color: entry.color }}>
          {entry.name}: {entry.value}
        </p>
      ))}
    </div>
  );
}

function RatioTooltip({ active, payload, label }: CustomTooltipProps) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-navy-700 bg-navy-900 px-3 py-2 shadow-xl">
      <p className="mb-1 text-xs font-medium text-navy-400">{label}</p>
      <p className="text-xs text-accent-cyan">
        Bug-fix ratio: {(payload[0].value * 100).toFixed(1)}%
      </p>
    </div>
  );
}

export default function TrendsView() {
  const { report } = useProjectContext();
  const trends = report?.trends ?? [];
  const [timeRange, setTimeRange] = useState<TimeRange>('180');

  const filteredTrends = useMemo(() => {
    if (trends.length === 0) return [];
    const days = parseInt(timeRange);
    const cutoff = new Date();
    cutoff.setDate(cutoff.getDate() - days);

    const filtered = trends.filter(
      (t) => new Date(t.period) >= cutoff,
    );

    return filtered.length > 0 ? filtered : trends;
  }, [trends, timeRange]);

  const totals = useMemo(() => {
    return filteredTrends.reduce(
      (acc, t) => ({
        features: acc.features + t.features,
        bugs: acc.bugs + t.bugs,
        refactors: acc.refactors + t.refactors,
        commits: acc.commits + t.total_commits,
      }),
      { features: 0, bugs: 0, refactors: 0, commits: 0 },
    );
  }, [filteredTrends]);

  const avgBugRatio = useMemo(() => {
    if (filteredTrends.length === 0) return 0;
    return (
      filteredTrends.reduce((acc, t) => acc + t.bug_fix_ratio, 0) /
      filteredTrends.length
    );
  }, [filteredTrends]);

  if (trends.length === 0) {
    return (
      <div className="py-16 text-center text-sm text-navy-500">
        No trend data available. Run an analysis first.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Controls */}
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-navy-200">
          Feature / Bug Trends
        </h3>
        <div className="flex items-center gap-3">
          <ExportButton
            data={filteredTrends.map((t) => ({
              period: t.period,
              features: t.features,
              bugs: t.bugs,
              refactors: t.refactors,
              bug_fix_ratio: t.bug_fix_ratio,
              total_commits: t.total_commits,
            }))}
            filename="trends"
          />
          <div className="flex rounded-lg border border-navy-800 bg-navy-800/40 p-0.5">
            {(['30', '90', '180'] as TimeRange[]).map((range) => (
              <button
                key={range}
                onClick={() => setTimeRange(range)}
                className={`rounded-md px-3 py-1 text-xs font-medium transition ${
                  timeRange === range
                    ? 'bg-navy-700 text-white'
                    : 'text-navy-400 hover:text-navy-200'
                }`}
              >
                {range}d
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div className="rounded-lg border border-navy-800 bg-navy-800/30 px-4 py-3">
          <p className="text-[10px] font-medium uppercase tracking-wider text-navy-500">
            Features
          </p>
          <p className="mt-1 text-xl font-bold text-accent-blue">
            {totals.features}
          </p>
        </div>
        <div className="rounded-lg border border-navy-800 bg-navy-800/30 px-4 py-3">
          <p className="text-[10px] font-medium uppercase tracking-wider text-navy-500">
            Bug Fixes
          </p>
          <p className="mt-1 text-xl font-bold text-risk-critical">
            {totals.bugs}
          </p>
        </div>
        <div className="rounded-lg border border-navy-800 bg-navy-800/30 px-4 py-3">
          <p className="text-[10px] font-medium uppercase tracking-wider text-navy-500">
            Refactors
          </p>
          <p className="mt-1 text-xl font-bold text-accent-indigo">
            {totals.refactors}
          </p>
        </div>
        <div className="rounded-lg border border-navy-800 bg-navy-800/30 px-4 py-3">
          <p className="text-[10px] font-medium uppercase tracking-wider text-navy-500">
            Avg Bug Ratio
          </p>
          <p
            className={`mt-1 text-xl font-bold ${
              avgBugRatio > 0.5 ? 'text-risk-critical' : avgBugRatio > 0.3 ? 'text-risk-medium' : 'text-risk-low'
            }`}
          >
            {(avgBugRatio * 100).toFixed(0)}%
          </p>
        </div>
      </div>

      {/* Stacked Area Chart */}
      <div className="rounded-xl border border-navy-800 bg-navy-800/20 p-5">
        <h4 className="mb-4 text-xs font-semibold text-navy-300">
          Commit Activity Over Time
        </h4>
        <ResponsiveContainer width="100%" height={320}>
          <AreaChart data={filteredTrends}>
            <defs>
              <linearGradient id="featureGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="bugGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#ef4444" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="refactorGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid
              strokeDasharray="3 3"
              stroke="#1e293b"
              vertical={false}
            />
            <XAxis
              dataKey="period"
              tick={{ fill: '#64748b', fontSize: 11 }}
              axisLine={{ stroke: '#334155' }}
              tickLine={false}
            />
            <YAxis
              tick={{ fill: '#64748b', fontSize: 11 }}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip content={<AreaTooltip />} />
            <Legend
              verticalAlign="top"
              height={36}
              iconType="circle"
              iconSize={8}
              formatter={(value: string) => (
                <span className="text-xs text-navy-400">{value}</span>
              )}
            />
            <Area
              type="monotone"
              dataKey="features"
              name="Features"
              stackId="1"
              stroke="#3b82f6"
              fill="url(#featureGrad)"
              strokeWidth={2}
            />
            <Area
              type="monotone"
              dataKey="bugs"
              name="Bugs"
              stackId="1"
              stroke="#ef4444"
              fill="url(#bugGrad)"
              strokeWidth={2}
            />
            <Area
              type="monotone"
              dataKey="refactors"
              name="Refactors"
              stackId="1"
              stroke="#6366f1"
              fill="url(#refactorGrad)"
              strokeWidth={2}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* Bug-fix Ratio Trend */}
      <div className="rounded-xl border border-navy-800 bg-navy-800/20 p-5">
        <h4 className="mb-4 text-xs font-semibold text-navy-300">
          Bug-Fix Ratio Trend
        </h4>
        <ResponsiveContainer width="100%" height={200}>
          <LineChart data={filteredTrends}>
            <CartesianGrid
              strokeDasharray="3 3"
              stroke="#1e293b"
              vertical={false}
            />
            <XAxis
              dataKey="period"
              tick={{ fill: '#64748b', fontSize: 11 }}
              axisLine={{ stroke: '#334155' }}
              tickLine={false}
            />
            <YAxis
              tick={{ fill: '#64748b', fontSize: 11 }}
              axisLine={false}
              tickLine={false}
              domain={[0, 1]}
              tickFormatter={(value: number) => `${(value * 100).toFixed(0)}%`}
            />
            <Tooltip content={<RatioTooltip />} />
            <Line
              type="monotone"
              dataKey="bug_fix_ratio"
              name="Bug-fix Ratio"
              stroke="#06b6d4"
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4, fill: '#06b6d4' }}
            />
          </LineChart>
        </ResponsiveContainer>
        <div className="mt-3 flex items-center gap-4 text-xs text-navy-500">
          <span>
            Lower is better. A ratio above 50% indicates more time fixing bugs
            than building features.
          </span>
        </div>
      </div>
    </div>
  );
}
