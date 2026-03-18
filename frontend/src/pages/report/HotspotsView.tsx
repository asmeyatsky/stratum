import { useState, useMemo } from 'react';
import { ArrowUpDown, Clock, GitBranch, Bug, Users } from 'lucide-react';
import type { FileHotspot } from '../../types';
import SeverityBadge from '../../components/SeverityBadge';
import ExportButton from '../../components/ExportButton';
import { useProjectContext } from '../ProjectDetail';
import { getScoreColor } from '../../utils/scores';

function getEffortColor(effort: string): { bg: string; text: string } {
  switch (effort) {
    case 'large':
      return { bg: 'bg-red-500/10', text: 'text-red-400' };
    case 'medium':
      return { bg: 'bg-yellow-500/10', text: 'text-yellow-400' };
    default:
      return { bg: 'bg-green-500/10', text: 'text-green-400' };
  }
}

function IndicatorBar({
  value,
  max,
  color,
}: {
  value: number;
  max: number;
  color: string;
}) {
  const pct = Math.min(100, (value / max) * 100);
  return (
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-navy-700">
      <div
        className="h-full rounded-full transition-all duration-500"
        style={{ width: `${pct}%`, backgroundColor: color }}
      />
    </div>
  );
}

type SortKey = 'risk_score' | 'churn_rate' | 'complexity' | 'bug_correlation' | 'ownership_fragmentation';

export default function HotspotsView() {
  const { report } = useProjectContext();
  const hotspots = report?.hotspots ?? [];
  const [sortBy, setSortBy] = useState<SortKey>('risk_score');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');

  const sorted = useMemo(() => {
    return [...hotspots]
      .sort((a, b) => {
        const comparison = (a[sortBy] as number) - (b[sortBy] as number);
        return sortDir === 'desc' ? -comparison : comparison;
      })
      .slice(0, 25);
  }, [hotspots, sortBy, sortDir]);

  const maxValues = useMemo(() => {
    if (hotspots.length === 0) return { churn: 1, complexity: 1, bug: 1, ownership: 1 };
    return {
      churn: Math.max(...hotspots.map((h) => h.churn_rate), 1),
      complexity: Math.max(...hotspots.map((h) => h.complexity), 1),
      bug: Math.max(...hotspots.map((h) => h.bug_correlation), 1),
      ownership: Math.max(...hotspots.map((h) => h.ownership_fragmentation), 1),
    };
  }, [hotspots]);

  const toggleSort = (key: SortKey) => {
    if (sortBy === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortBy(key);
      setSortDir('desc');
    }
  };

  if (hotspots.length === 0) {
    return (
      <div className="py-16 text-center text-sm text-navy-500">
        No hotspot data available. Run an analysis first.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-navy-200">
          Top 25 File Hotspots
        </h3>
        <div className="flex items-center gap-3">
          <span className="text-xs text-navy-500">
            {hotspots.length} files analyzed
          </span>
          <ExportButton
            data={hotspots.map((h) => ({
              file_path: h.file_path,
              risk_score: h.risk_score,
              severity: h.severity,
              churn_rate: h.churn_rate,
              complexity: h.complexity,
              bug_correlation: h.bug_correlation,
              ownership_fragmentation: h.ownership_fragmentation,
              effort_estimate: h.effort_estimate,
              indicators: h.indicators.join('; '),
            }))}
            filename="hotspots"
          />
        </div>
      </div>

      <div className="overflow-hidden rounded-xl border border-navy-800 bg-navy-800/20">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[900px]">
            <thead>
              <tr className="border-b border-navy-800 bg-navy-800/40">
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-navy-500">
                  #
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-navy-500">
                  File
                </th>
                <th
                  className="cursor-pointer px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-navy-500"
                  onClick={() => toggleSort('risk_score')}
                >
                  <span className="inline-flex items-center gap-1">
                    Risk <ArrowUpDown className="h-3 w-3" />
                  </span>
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-navy-500">
                  Severity
                </th>
                <th
                  className="cursor-pointer px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-navy-500"
                  onClick={() => toggleSort('churn_rate')}
                >
                  <span className="inline-flex items-center gap-1">
                    <GitBranch className="h-3 w-3" />
                    Churn <ArrowUpDown className="h-3 w-3" />
                  </span>
                </th>
                <th
                  className="cursor-pointer px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-navy-500"
                  onClick={() => toggleSort('complexity')}
                >
                  <span className="inline-flex items-center gap-1">
                    <Clock className="h-3 w-3" />
                    Complexity <ArrowUpDown className="h-3 w-3" />
                  </span>
                </th>
                <th
                  className="cursor-pointer px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-navy-500"
                  onClick={() => toggleSort('bug_correlation')}
                >
                  <span className="inline-flex items-center gap-1">
                    <Bug className="h-3 w-3" />
                    Bugs <ArrowUpDown className="h-3 w-3" />
                  </span>
                </th>
                <th
                  className="cursor-pointer px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-navy-500"
                  onClick={() => toggleSort('ownership_fragmentation')}
                >
                  <span className="inline-flex items-center gap-1">
                    <Users className="h-3 w-3" />
                    Ownership <ArrowUpDown className="h-3 w-3" />
                  </span>
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-navy-500">
                  Effort
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-navy-800/60">
              {sorted.map((hotspot, idx) => {
                const effortColors = getEffortColor(hotspot.effort_estimate);
                return (
                  <tr
                    key={hotspot.file_path}
                    className="transition hover:bg-navy-800/30"
                  >
                    <td className="px-4 py-3 text-xs text-navy-600">
                      {idx + 1}
                    </td>
                    <td className="max-w-[280px] px-4 py-3">
                      <span
                        className="block truncate font-mono text-xs text-navy-300"
                        title={hotspot.file_path}
                      >
                        {hotspot.file_path}
                      </span>
                      {hotspot.indicators.length > 0 && (
                        <div className="mt-1 flex flex-wrap gap-1">
                          {hotspot.indicators.slice(0, 3).map((ind, i) => (
                            <span
                              key={i}
                              className="rounded bg-navy-800 px-1.5 py-0.5 text-[9px] text-navy-500"
                            >
                              {ind}
                            </span>
                          ))}
                          {hotspot.indicators.length > 3 && (
                            <span className="rounded bg-navy-800 px-1.5 py-0.5 text-[9px] text-navy-500">
                              +{hotspot.indicators.length - 3}
                            </span>
                          )}
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className="text-sm font-bold"
                        style={{
                          color: getScoreColor(hotspot.risk_score),
                        }}
                      >
                        {hotspot.risk_score.toFixed(1)}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <SeverityBadge severity={hotspot.severity} />
                    </td>
                    <td className="w-28 px-4 py-3">
                      <div className="space-y-1">
                        <span className="text-xs text-navy-400">
                          {hotspot.churn_rate.toFixed(1)}
                        </span>
                        <IndicatorBar
                          value={hotspot.churn_rate}
                          max={maxValues.churn}
                          color="#3b82f6"
                        />
                      </div>
                    </td>
                    <td className="w-28 px-4 py-3">
                      <div className="space-y-1">
                        <span className="text-xs text-navy-400">
                          {hotspot.complexity.toFixed(1)}
                        </span>
                        <IndicatorBar
                          value={hotspot.complexity}
                          max={maxValues.complexity}
                          color="#8b5cf6"
                        />
                      </div>
                    </td>
                    <td className="w-28 px-4 py-3">
                      <div className="space-y-1">
                        <span className="text-xs text-navy-400">
                          {hotspot.bug_correlation.toFixed(1)}
                        </span>
                        <IndicatorBar
                          value={hotspot.bug_correlation}
                          max={maxValues.bug}
                          color="#ef4444"
                        />
                      </div>
                    </td>
                    <td className="w-28 px-4 py-3">
                      <div className="space-y-1">
                        <span className="text-xs text-navy-400">
                          {hotspot.ownership_fragmentation.toFixed(1)}
                        </span>
                        <IndicatorBar
                          value={hotspot.ownership_fragmentation}
                          max={maxValues.ownership}
                          color="#f97316"
                        />
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${effortColors.bg} ${effortColors.text}`}
                      >
                        {hotspot.effort_estimate}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
