import { useEffect, useState } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';
import { ChevronDown, ChevronUp } from 'lucide-react';
import api from '../../api/client';
import type { DimensionScore } from '../../types';
import SeverityBadge from '../../components/SeverityBadge';

function getScoreColor(score: number): string {
  if (score >= 7) return '#22c55e';
  if (score >= 4) return '#eab308';
  return '#ef4444';
}

function SkeletonChart() {
  return (
    <div className="animate-pulse">
      <div className="mb-6 h-72 rounded-xl bg-navy-800/40" />
      <div className="space-y-3">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="h-16 rounded-lg bg-navy-800/40" />
        ))}
      </div>
    </div>
  );
}

interface DimensionRowProps {
  dimension: DimensionScore;
}

function DimensionRow({ dimension }: DimensionRowProps) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="rounded-lg border border-navy-800 bg-navy-800/20 transition hover:bg-navy-800/40">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center gap-4 px-4 py-3 text-left"
      >
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3">
            <span className="text-sm font-medium text-navy-200">
              {dimension.name}
            </span>
            <SeverityBadge severity={dimension.severity} />
          </div>
          <p className="mt-0.5 truncate text-xs text-navy-500">
            {dimension.description}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="w-32">
            <div className="h-1.5 w-full overflow-hidden rounded-full bg-navy-700">
              <div
                className="h-full rounded-full transition-all duration-500"
                style={{
                  width: `${(dimension.score / 10) * 100}%`,
                  backgroundColor: getScoreColor(dimension.score),
                }}
              />
            </div>
          </div>
          <span
            className="w-10 text-right text-sm font-bold"
            style={{ color: getScoreColor(dimension.score) }}
          >
            {dimension.score.toFixed(1)}
          </span>
          {expanded ? (
            <ChevronUp className="h-4 w-4 text-navy-500" />
          ) : (
            <ChevronDown className="h-4 w-4 text-navy-500" />
          )}
        </div>
      </button>

      {expanded && (
        <div className="border-t border-navy-800 px-4 py-3">
          <div className="mb-2 flex items-center gap-4">
            <span className="text-xs text-navy-500">
              Weight: {dimension.weight}
            </span>
          </div>
          {dimension.evidence.length > 0 && (
            <div>
              <p className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-navy-500">
                Evidence
              </p>
              <ul className="space-y-1">
                {dimension.evidence.map((item, i) => (
                  <li
                    key={i}
                    className="flex items-start gap-2 text-xs text-navy-400"
                  >
                    <span className="mt-1.5 h-1 w-1 flex-shrink-0 rounded-full bg-navy-600" />
                    {item}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

interface CustomTooltipProps {
  active?: boolean;
  payload?: Array<{ payload: DimensionScore; value: number }>;
}

function CustomTooltip({ active, payload }: CustomTooltipProps) {
  if (!active || !payload?.length) return null;
  const dim = payload[0].payload;
  return (
    <div className="rounded-lg border border-navy-700 bg-navy-900 px-3 py-2 shadow-xl">
      <p className="text-sm font-medium text-white">{dim.name}</p>
      <p className="text-xs text-navy-400">
        Score:{' '}
        <span style={{ color: getScoreColor(dim.score) }}>
          {dim.score.toFixed(1)}
        </span>
      </p>
      <p className="text-xs text-navy-500">{dim.severity}</p>
    </div>
  );
}

export default function DimensionsView({
  projectId,
}: {
  projectId: string;
}) {
  const [dimensions, setDimensions] = useState<DimensionScore[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .getDimensions(projectId)
      .then((data) => {
        if (!cancelled) setDimensions(data);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  if (loading) return <SkeletonChart />;

  if (error) {
    return (
      <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-8 text-center text-sm text-red-400">
        {error}
      </div>
    );
  }

  if (dimensions.length === 0) {
    return (
      <div className="py-16 text-center text-sm text-navy-500">
        No dimension data available. Run an analysis first.
      </div>
    );
  }

  const sortedForChart = [...dimensions].sort(
    (a, b) => a.score - b.score,
  );

  return (
    <div className="space-y-6">
      {/* Bar Chart */}
      <div className="rounded-xl border border-navy-800 bg-navy-800/20 p-5">
        <h3 className="mb-4 text-sm font-semibold text-navy-200">
          Dimension Scores
        </h3>
        <ResponsiveContainer width="100%" height={320}>
          <BarChart
            data={sortedForChart}
            layout="vertical"
            margin={{ top: 0, right: 20, bottom: 0, left: 0 }}
          >
            <CartesianGrid
              strokeDasharray="3 3"
              stroke="#1e293b"
              horizontal={false}
            />
            <XAxis
              type="number"
              domain={[0, 10]}
              tick={{ fill: '#64748b', fontSize: 12 }}
              axisLine={{ stroke: '#334155' }}
              tickLine={{ stroke: '#334155' }}
            />
            <YAxis
              type="category"
              dataKey="name"
              width={160}
              tick={{ fill: '#94a3b8', fontSize: 11 }}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(30, 41, 59, 0.5)' }} />
            <Bar dataKey="score" radius={[0, 4, 4, 0]} barSize={18}>
              {sortedForChart.map((entry, index) => (
                <Cell
                  key={`cell-${index}`}
                  fill={getScoreColor(entry.score)}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Detail Table */}
      <div className="space-y-2">
        <h3 className="mb-2 text-sm font-semibold text-navy-200">
          Dimension Details
        </h3>
        {[...dimensions]
          .sort((a, b) => a.score - b.score)
          .map((dim) => (
            <DimensionRow key={dim.id} dimension={dim} />
          ))}
      </div>
    </div>
  );
}
