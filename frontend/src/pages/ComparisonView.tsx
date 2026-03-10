import { useEffect, useState, useMemo } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';
import { ArrowUp, ArrowDown, Minus, Loader2 } from 'lucide-react';
import api from '../api/client';
import type { Project, AnalysisReport } from '../types';
import HealthScore from '../components/HealthScore';

interface CustomTooltipProps {
  active?: boolean;
  payload?: Array<{ name: string; value: number; fill: string }>;
  label?: string;
}

function ChartTooltip({ active, payload, label }: CustomTooltipProps) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-navy-700 bg-navy-900 px-3 py-2 shadow-xl">
      <p className="mb-1.5 text-xs font-medium text-navy-300">{label}</p>
      {payload.map((entry, i) => (
        <p key={i} className="text-xs" style={{ color: entry.fill }}>
          {entry.name}: {entry.value.toFixed(1)}
        </p>
      ))}
    </div>
  );
}

function DeltaIndicator({ delta }: { delta: number }) {
  if (Math.abs(delta) < 0.1) {
    return (
      <span className="inline-flex items-center gap-0.5 text-xs text-navy-500">
        <Minus className="h-3 w-3" />
        {delta.toFixed(1)}
      </span>
    );
  }
  if (delta > 0) {
    return (
      <span className="inline-flex items-center gap-0.5 text-xs text-green-400">
        <ArrowUp className="h-3 w-3" />
        +{delta.toFixed(1)}
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-0.5 text-xs text-red-400">
      <ArrowDown className="h-3 w-3" />
      {delta.toFixed(1)}
    </span>
  );
}

export default function ComparisonView() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loadingProjects, setLoadingProjects] = useState(true);
  const [projectAId, setProjectAId] = useState('');
  const [projectBId, setProjectBId] = useState('');
  const [reportA, setReportA] = useState<AnalysisReport | null>(null);
  const [reportB, setReportB] = useState<AnalysisReport | null>(null);
  const [loadingReports, setLoadingReports] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .getProjects()
      .then(setProjects)
      .catch((err) => setError(err.message))
      .finally(() => setLoadingProjects(false));
  }, []);

  useEffect(() => {
    if (!projectAId || !projectBId) {
      setReportA(null);
      setReportB(null);
      return;
    }

    let cancelled = false;
    setLoadingReports(true);
    setError(null);

    Promise.all([api.getReport(projectAId), api.getReport(projectBId)])
      .then(([a, b]) => {
        if (!cancelled) {
          setReportA(a);
          setReportB(b);
        }
      })
      .catch((err) => {
        if (!cancelled) setError(err.message);
      })
      .finally(() => {
        if (!cancelled) setLoadingReports(false);
      });

    return () => {
      cancelled = true;
    };
  }, [projectAId, projectBId]);

  const chartData = useMemo(() => {
    if (!reportA || !reportB) return [];

    const allDimNames = new Set<string>();
    reportA.dimensions.forEach((d) => allDimNames.add(d.name));
    reportB.dimensions.forEach((d) => allDimNames.add(d.name));

    return Array.from(allDimNames).map((name) => {
      const dimA = reportA.dimensions.find((d) => d.name === name);
      const dimB = reportB.dimensions.find((d) => d.name === name);
      return {
        name,
        projectA: dimA?.score ?? 0,
        projectB: dimB?.score ?? 0,
      };
    });
  }, [reportA, reportB]);

  const projectAName =
    projects.find((p) => p.id === projectAId)?.name ?? 'Project A';
  const projectBName =
    projects.find((p) => p.id === projectBId)?.name ?? 'Project B';

  return (
    <div>
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-white">Compare Projects</h1>
        <p className="mt-1 text-sm text-navy-400">
          Side-by-side comparison of project health and dimensions
        </p>
      </div>

      {error && (
        <div className="mb-6 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-400">
          {error}
        </div>
      )}

      {/* Project Selectors */}
      <div className="mb-8 grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div>
          <label className="mb-1.5 block text-sm font-medium text-navy-300">
            Project A
          </label>
          <select
            value={projectAId}
            onChange={(e) => setProjectAId(e.target.value)}
            disabled={loadingProjects}
            className="w-full rounded-lg border border-navy-700 bg-navy-800 px-3 py-2 text-sm text-navy-200 outline-none transition focus:border-accent-blue focus:ring-1 focus:ring-accent-blue disabled:opacity-50"
          >
            <option value="">Select a project...</option>
            {projects
              .filter((p) => p.status === 'completed')
              .map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
          </select>
        </div>
        <div>
          <label className="mb-1.5 block text-sm font-medium text-navy-300">
            Project B
          </label>
          <select
            value={projectBId}
            onChange={(e) => setProjectBId(e.target.value)}
            disabled={loadingProjects}
            className="w-full rounded-lg border border-navy-700 bg-navy-800 px-3 py-2 text-sm text-navy-200 outline-none transition focus:border-accent-blue focus:ring-1 focus:ring-accent-blue disabled:opacity-50"
          >
            <option value="">Select a project...</option>
            {projects
              .filter((p) => p.status === 'completed')
              .map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
          </select>
        </div>
      </div>

      {/* Loading state */}
      {loadingReports && (
        <div className="flex items-center justify-center py-16">
          <Loader2 className="h-8 w-8 animate-spin text-accent-blue" />
        </div>
      )}

      {/* No selection prompt */}
      {!loadingReports && (!projectAId || !projectBId) && (
        <div className="rounded-xl border border-dashed border-navy-700 bg-navy-900/50 py-20 text-center">
          <p className="text-sm text-navy-500">
            Select two projects above to compare their reports
          </p>
        </div>
      )}

      {/* Comparison Content */}
      {!loadingReports && reportA && reportB && (
        <div className="space-y-6">
          {/* Side-by-side Health Scores */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="rounded-xl border border-navy-800 bg-navy-800/30 p-6">
              <p className="mb-4 text-center text-xs font-medium uppercase tracking-wider text-navy-500">
                {projectAName}
              </p>
              <div className="flex justify-center">
                <HealthScore score={reportA.health_score} size="lg" />
              </div>
            </div>
            <div className="rounded-xl border border-navy-800 bg-navy-800/30 p-6">
              <p className="mb-4 text-center text-xs font-medium uppercase tracking-wider text-navy-500">
                {projectBName}
              </p>
              <div className="flex justify-center">
                <HealthScore score={reportB.health_score} size="lg" />
              </div>
            </div>
          </div>

          {/* Dimension Comparison Table */}
          <div className="rounded-xl border border-navy-800 bg-navy-800/20 p-5">
            <h3 className="mb-4 text-sm font-semibold text-navy-200">
              Dimension Comparison
            </h3>
            <div className="space-y-2">
              {chartData.map((row) => {
                const delta = row.projectB - row.projectA;
                return (
                  <div
                    key={row.name}
                    className="flex items-center gap-4 rounded-lg bg-navy-800/40 px-4 py-3"
                  >
                    <span className="flex-1 min-w-0 truncate text-sm text-navy-300">
                      {row.name}
                    </span>
                    <div className="flex items-center gap-6">
                      <span
                        className="w-12 text-right text-sm font-semibold"
                        style={{
                          color:
                            row.projectA >= 7
                              ? '#22c55e'
                              : row.projectA >= 4
                                ? '#eab308'
                                : '#ef4444',
                        }}
                      >
                        {row.projectA.toFixed(1)}
                      </span>
                      <span
                        className="w-12 text-right text-sm font-semibold"
                        style={{
                          color:
                            row.projectB >= 7
                              ? '#22c55e'
                              : row.projectB >= 4
                                ? '#eab308'
                                : '#ef4444',
                        }}
                      >
                        {row.projectB.toFixed(1)}
                      </span>
                      <div className="w-16 text-right">
                        <DeltaIndicator delta={delta} />
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
            {/* Legend row for table columns */}
            <div className="mt-3 flex items-center justify-end gap-6 text-[10px] uppercase tracking-wider text-navy-500">
              <span className="w-12 text-right">{projectAName}</span>
              <span className="w-12 text-right">{projectBName}</span>
              <span className="w-16 text-right">Delta</span>
            </div>
          </div>

          {/* Bar Chart */}
          <div className="rounded-xl border border-navy-800 bg-navy-800/20 p-5">
            <h3 className="mb-4 text-sm font-semibold text-navy-200">
              Visual Comparison
            </h3>
            <ResponsiveContainer width="100%" height={360}>
              <BarChart
                data={chartData}
                margin={{ top: 0, right: 20, bottom: 0, left: 0 }}
              >
                <CartesianGrid
                  strokeDasharray="3 3"
                  stroke="#1e293b"
                  vertical={false}
                />
                <XAxis
                  dataKey="name"
                  tick={{ fill: '#94a3b8', fontSize: 11 }}
                  axisLine={{ stroke: '#334155' }}
                  tickLine={false}
                  interval={0}
                  angle={-25}
                  textAnchor="end"
                  height={80}
                />
                <YAxis
                  domain={[0, 10]}
                  tick={{ fill: '#64748b', fontSize: 12 }}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip content={<ChartTooltip />} cursor={{ fill: 'rgba(30, 41, 59, 0.5)' }} />
                <Legend
                  verticalAlign="top"
                  height={36}
                  iconType="circle"
                  iconSize={8}
                  formatter={(value: string) => (
                    <span className="text-xs text-navy-400">{value}</span>
                  )}
                />
                <Bar
                  dataKey="projectA"
                  name={projectAName}
                  fill="#3b82f6"
                  radius={[4, 4, 0, 0]}
                  barSize={24}
                />
                <Bar
                  dataKey="projectB"
                  name={projectBName}
                  fill="#6366f1"
                  radius={[4, 4, 0, 0]}
                  barSize={24}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </div>
  );
}
