import { useEffect, useState, useMemo } from 'react';
import api from '../../api/client';
import type { ComponentRisk, Severity } from '../../types';
import SeverityBadge from '../../components/SeverityBadge';
import { ArrowUpDown, AlertTriangle } from 'lucide-react';

function getSeverityForScore(score: number): Severity {
  if (score >= 8) return 'critical';
  if (score >= 6) return 'high';
  if (score >= 4) return 'medium';
  if (score >= 2) return 'low';
  return 'minimal';
}

function getHeatColor(value: number): string {
  if (value >= 8) return 'bg-red-500/70';
  if (value >= 6) return 'bg-orange-500/50';
  if (value >= 4) return 'bg-yellow-500/40';
  if (value >= 2) return 'bg-green-500/20';
  return 'bg-navy-700/40';
}

function getHeatTextColor(value: number): string {
  if (value >= 8) return 'text-red-200';
  if (value >= 6) return 'text-orange-200';
  if (value >= 4) return 'text-yellow-200';
  return 'text-navy-400';
}

function Skeleton() {
  return (
    <div className="animate-pulse space-y-4">
      <div className="h-8 w-48 rounded bg-navy-800" />
      <div className="h-96 rounded-xl bg-navy-800/40" />
    </div>
  );
}

export default function ComponentsView({
  projectId,
}: {
  projectId: string;
}) {
  const [components, setComponents] = useState<ComponentRisk[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sortBy, setSortBy] = useState<'score' | 'name'>('score');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');

  useEffect(() => {
    let cancelled = false;
    api
      .getComponents(projectId)
      .then((data) => {
        if (!cancelled) setComponents(data);
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

  const allDimensionKeys = useMemo(() => {
    const keys = new Set<string>();
    components.forEach((c) => {
      Object.keys(c.dimension_scores).forEach((k) => keys.add(k));
    });
    return Array.from(keys).sort();
  }, [components]);

  const sorted = useMemo(() => {
    return [...components].sort((a, b) => {
      let comparison: number;
      if (sortBy === 'score') {
        comparison = a.composite_score - b.composite_score;
      } else {
        comparison = a.name.localeCompare(b.name);
      }
      return sortDir === 'desc' ? -comparison : comparison;
    });
  }, [components, sortBy, sortDir]);

  const toggleSort = (key: 'score' | 'name') => {
    if (sortBy === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortBy(key);
      setSortDir('desc');
    }
  };

  if (loading) return <Skeleton />;

  if (error) {
    return (
      <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-8 text-center text-sm text-red-400">
        {error}
      </div>
    );
  }

  if (components.length === 0) {
    return (
      <div className="py-16 text-center text-sm text-navy-500">
        No component data available. Run an analysis first.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Heatmap */}
      <div className="rounded-xl border border-navy-800 bg-navy-800/20 p-5">
        <h3 className="mb-4 text-sm font-semibold text-navy-200">
          Component x Dimension Heatmap
        </h3>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[700px]">
            <thead>
              <tr>
                <th className="sticky left-0 bg-navy-800/80 px-3 py-2 text-left text-xs font-semibold text-navy-500 backdrop-blur-sm">
                  Component
                </th>
                {allDimensionKeys.map((key) => (
                  <th
                    key={key}
                    className="px-2 py-2 text-center text-[10px] font-medium text-navy-500"
                    title={key}
                  >
                    <span className="block max-w-[60px] truncate">
                      {key.replace(/_/g, ' ')}
                    </span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sorted.map((comp) => (
                <tr key={comp.name}>
                  <td className="sticky left-0 bg-navy-900/90 px-3 py-1.5 backdrop-blur-sm">
                    <span className="text-xs font-medium text-navy-300">
                      {comp.name}
                    </span>
                  </td>
                  {allDimensionKeys.map((key) => {
                    const value = comp.dimension_scores[key] ?? 0;
                    return (
                      <td key={key} className="px-1 py-1">
                        <div
                          className={`flex h-8 items-center justify-center rounded ${getHeatColor(value)} ${getHeatTextColor(value)}`}
                          title={`${comp.name} - ${key}: ${value.toFixed(1)}`}
                        >
                          <span className="text-[10px] font-medium">
                            {value > 0 ? value.toFixed(1) : ''}
                          </span>
                        </div>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Legend */}
        <div className="mt-4 flex items-center gap-4">
          <span className="text-xs text-navy-500">Risk:</span>
          <div className="flex items-center gap-1.5">
            <div className="h-3 w-8 rounded bg-navy-700/40" />
            <span className="text-[10px] text-navy-500">Low</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="h-3 w-8 rounded bg-green-500/20" />
            <span className="text-[10px] text-navy-500">Mild</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="h-3 w-8 rounded bg-yellow-500/40" />
            <span className="text-[10px] text-navy-500">Medium</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="h-3 w-8 rounded bg-orange-500/50" />
            <span className="text-[10px] text-navy-500">High</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="h-3 w-8 rounded bg-red-500/70" />
            <span className="text-[10px] text-navy-500">Critical</span>
          </div>
        </div>
      </div>

      {/* Component Table */}
      <div className="rounded-xl border border-navy-800 bg-navy-800/20">
        <table className="w-full">
          <thead>
            <tr className="border-b border-navy-800">
              <th
                className="cursor-pointer px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-navy-500"
                onClick={() => toggleSort('name')}
              >
                <span className="inline-flex items-center gap-1">
                  Component
                  <ArrowUpDown className="h-3 w-3" />
                </span>
              </th>
              <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-navy-500">
                Path
              </th>
              <th
                className="cursor-pointer px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-navy-500"
                onClick={() => toggleSort('score')}
              >
                <span className="inline-flex items-center gap-1">
                  Score
                  <ArrowUpDown className="h-3 w-3" />
                </span>
              </th>
              <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-navy-500">
                Severity
              </th>
              <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-navy-500">
                Files
              </th>
              <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-navy-500">
                Systemic Risks
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-navy-800/60">
            {sorted.map((comp) => (
              <tr
                key={comp.name}
                className="transition hover:bg-navy-800/30"
              >
                <td className="px-4 py-3 text-sm font-medium text-navy-200">
                  {comp.name}
                </td>
                <td className="px-4 py-3">
                  <span className="font-mono text-xs text-navy-400">
                    {comp.path}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <span
                    className="text-sm font-bold"
                    style={{
                      color:
                        comp.composite_score >= 7
                          ? '#ef4444'
                          : comp.composite_score >= 4
                            ? '#eab308'
                            : '#22c55e',
                    }}
                  >
                    {comp.composite_score.toFixed(1)}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <SeverityBadge
                    severity={getSeverityForScore(comp.composite_score)}
                  />
                </td>
                <td className="px-4 py-3 text-sm text-navy-400">
                  {comp.file_count}
                </td>
                <td className="px-4 py-3">
                  {comp.systemic_risks.length > 0 ? (
                    <div className="flex flex-wrap gap-1">
                      {comp.systemic_risks.map((risk, i) => (
                        <span
                          key={i}
                          className="inline-flex items-center gap-1 rounded-full bg-red-500/10 px-2 py-0.5 text-[10px] font-medium text-red-400"
                        >
                          <AlertTriangle className="h-2.5 w-2.5" />
                          {risk}
                        </span>
                      ))}
                    </div>
                  ) : (
                    <span className="text-xs text-navy-600">None</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
