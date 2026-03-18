import { useState, useMemo } from 'react';
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
import type { DimensionScore } from '../../types';
import SeverityBadge from '../../components/SeverityBadge';
import ExportButton from '../../components/ExportButton';
import { useProjectContext } from '../ProjectDetail';
import { getScoreColor } from '../../utils/scores';

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

function ChartTooltip({ active, payload }: CustomTooltipProps) {
  if (!active || !payload?.length) return null;
  const dim = payload[0].payload;
  return (
    <div className="rounded-lg border border-navy-700 bg-navy-900 px-3 py-2 shadow-xl">
      <p className="text-xs font-medium text-navy-200">{dim.name}</p>
      <p className="text-lg font-bold" style={{ color: getScoreColor(dim.score) }}>
        {dim.score.toFixed(1)}
      </p>
      <p className="text-xs text-navy-500">{dim.severity}</p>
    </div>
  );
}

export default function DimensionsView() {
  const { report } = useProjectContext();
  const dimensions = report?.dimensions ?? [];

  if (dimensions.length === 0) {
    return (
      <div className="py-16 text-center text-sm text-navy-500">
        No dimension data available. Run an analysis first.
      </div>
    );
  }

  const chartData = useMemo(
    () => [...dimensions].sort((a, b) => b.score - a.score),
    [dimensions],
  );

  return (
    <div className="space-y-6">
      {/* Bar Chart */}
      <div className="rounded-xl border border-navy-800 bg-navy-800/20 p-5">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-navy-200">
            Dimension Scores
          </h3>
          <ExportButton
            data={dimensions.map((d) => ({
              dimension: d.name,
              score: d.score,
              severity: d.severity,
              weight: d.weight,
              evidence: d.evidence.join('; '),
            }))}
            filename="dimensions"
          />
        </div>
        <ResponsiveContainer width="100%" height={Math.max(280, dimensions.length * 32)}>
          <BarChart data={chartData} layout="vertical" margin={{ left: 120 }}>
            <CartesianGrid
              strokeDasharray="3 3"
              stroke="#1e293b"
              horizontal={false}
            />
            <XAxis
              type="number"
              domain={[0, 10]}
              tick={{ fill: '#64748b', fontSize: 11 }}
              axisLine={{ stroke: '#334155' }}
              tickLine={false}
            />
            <YAxis
              type="category"
              dataKey="name"
              tick={{ fill: '#94a3b8', fontSize: 11 }}
              axisLine={false}
              tickLine={false}
              width={110}
            />
            <Tooltip content={<ChartTooltip />} />
            <Bar dataKey="score" radius={[0, 4, 4, 0]} barSize={18}>
              {chartData.map((entry, index) => (
                <Cell key={index} fill={getScoreColor(entry.score)} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Dimension List */}
      <div className="space-y-2">
        {[...dimensions]
          .sort((a, b) => a.score - b.score)
          .map((dim) => (
            <DimensionRow key={dim.id} dimension={dim} />
          ))}
      </div>
    </div>
  );
}
