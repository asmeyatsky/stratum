import { useEffect, useState, useCallback } from 'react';
import { useParams, NavLink, Routes, Route, Navigate } from 'react-router-dom';
import {
  ArrowLeft,
  BarChart3,
  Grid3x3,
  Flame,
  TrendingUp,
  Layers,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import api from '../api/client';
import type { Project, AnalysisReport, Scenario } from '../types';
import HealthScore from '../components/HealthScore';
import SeverityBadge from '../components/SeverityBadge';
import AnalysisUploadForm from '../components/AnalysisUploadForm';
import DimensionsView from './report/DimensionsView';
import ComponentsView from './report/ComponentsView';
import HotspotsView from './report/HotspotsView';
import TrendsView from './report/TrendsView';

const tabs = [
  { path: '', label: 'Overview', icon: Layers, end: true },
  { path: 'dimensions', label: 'Dimensions', icon: BarChart3, end: false },
  { path: 'components', label: 'Components', icon: Grid3x3, end: false },
  { path: 'hotspots', label: 'Hotspots', icon: Flame, end: false },
  { path: 'trends', label: 'Trends', icon: TrendingUp, end: false },
];

function OverviewSkeleton() {
  return (
    <div className="animate-pulse space-y-6">
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <div className="h-32 rounded-xl bg-navy-800/40" />
        <div className="h-32 rounded-xl bg-navy-800/40" />
        <div className="h-32 rounded-xl bg-navy-800/40" />
      </div>
      <div className="h-64 rounded-xl bg-navy-800/40" />
    </div>
  );
}

function OverviewTab({
  project,
  report,
  loading,
  onAnalyze,
}: {
  project: Project | null;
  report: AnalysisReport | null;
  loading: boolean;
  onAnalyze: (gitLog: File, manifests: File[], scenario: Scenario) => Promise<void>;
}) {
  if (loading) return <OverviewSkeleton />;

  if (!report) {
    return (
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div className="rounded-xl border border-navy-800 bg-navy-800/30 p-6">
          <h3 className="mb-1 text-lg font-semibold text-white">
            Run Your First Analysis
          </h3>
          <p className="mb-5 text-sm text-navy-400">
            Upload your git log and optional manifest files to generate a
            comprehensive code health report.
          </p>
          <AnalysisUploadForm
            onSubmit={onAnalyze}
            currentScenario={project?.scenario}
          />
        </div>
        <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-navy-700 bg-navy-900/50 p-12">
          <BarChart3 className="mb-4 h-12 w-12 text-navy-700" />
          <p className="text-sm text-navy-500">
            Report data will appear here after analysis
          </p>
        </div>
      </div>
    );
  }

  const topDimensions = [...report.dimensions]
    .sort((a, b) => a.score - b.score)
    .slice(0, 5);

  const topHotspots = [...report.hotspots]
    .sort((a, b) => b.risk_score - a.risk_score)
    .slice(0, 5);

  return (
    <div className="space-y-6">
      {/* Summary Cards */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <div className="rounded-xl border border-navy-800 bg-navy-800/30 p-5">
          <p className="mb-3 text-xs font-medium uppercase tracking-wider text-navy-500">
            Health Score
          </p>
          <HealthScore score={report.health_score} size="md" />
        </div>
        <div className="rounded-xl border border-navy-800 bg-navy-800/30 p-5">
          <p className="mb-3 text-xs font-medium uppercase tracking-wider text-navy-500">
            Dimensions Analyzed
          </p>
          <p className="text-3xl font-bold text-white">
            {report.dimensions.length}
          </p>
          <p className="mt-1 text-sm text-navy-400">
            {report.dimensions.filter((d) => d.severity === 'critical' || d.severity === 'high').length}{' '}
            need attention
          </p>
        </div>
        <div className="rounded-xl border border-navy-800 bg-navy-800/30 p-5">
          <p className="mb-3 text-xs font-medium uppercase tracking-wider text-navy-500">
            File Hotspots
          </p>
          <p className="text-3xl font-bold text-white">
            {report.hotspots.length}
          </p>
          <p className="mt-1 text-sm text-navy-400">
            {report.hotspots.filter((h) => h.severity === 'critical').length}{' '}
            critical files
          </p>
        </div>
      </div>

      {/* Summary */}
      {report.summary && (
        <div className="rounded-xl border border-navy-800 bg-navy-800/30 p-5">
          <h3 className="mb-2 text-sm font-semibold text-navy-200">
            Analysis Summary
          </h3>
          <p className="text-sm leading-relaxed text-navy-400">
            {report.summary}
          </p>
        </div>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Lowest Dimensions */}
        <div className="rounded-xl border border-navy-800 bg-navy-800/30 p-5">
          <h3 className="mb-4 text-sm font-semibold text-navy-200">
            Lowest Scoring Dimensions
          </h3>
          <div className="space-y-3">
            {topDimensions.map((dim) => (
              <div key={dim.id} className="flex items-center gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="truncate text-sm text-navy-300">
                      {dim.name}
                    </span>
                    <SeverityBadge severity={dim.severity} />
                  </div>
                  <div className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-navy-700">
                    <div
                      className="h-full rounded-full transition-all duration-500"
                      style={{
                        width: `${(dim.score / 10) * 100}%`,
                        backgroundColor:
                          dim.score >= 7
                            ? '#22c55e'
                            : dim.score >= 4
                              ? '#eab308'
                              : '#ef4444',
                      }}
                    />
                  </div>
                </div>
                <span className="text-sm font-semibold text-navy-300 w-10 text-right">
                  {dim.score.toFixed(1)}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Top Hotspots */}
        <div className="rounded-xl border border-navy-800 bg-navy-800/30 p-5">
          <h3 className="mb-4 text-sm font-semibold text-navy-200">
            Riskiest Files
          </h3>
          <div className="space-y-2">
            {topHotspots.map((hotspot) => (
              <div
                key={hotspot.file_path}
                className="flex items-center gap-3 rounded-lg bg-navy-800/50 px-3 py-2"
              >
                <div
                  className={`h-2 w-2 rounded-full ${
                    hotspot.severity === 'critical'
                      ? 'bg-risk-critical'
                      : hotspot.severity === 'high'
                        ? 'bg-risk-high'
                        : 'bg-risk-medium'
                  }`}
                />
                <span className="flex-1 truncate font-mono text-xs text-navy-300">
                  {hotspot.file_path}
                </span>
                <span className="text-xs font-medium text-navy-400">
                  {hotspot.risk_score.toFixed(1)}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Run New Analysis */}
      <div className="rounded-xl border border-navy-800 bg-navy-800/30 p-5">
        <h3 className="mb-1 text-sm font-semibold text-navy-200">
          Run New Analysis
        </h3>
        <p className="mb-4 text-xs text-navy-500">
          Upload updated files to refresh the report
        </p>
        <AnalysisUploadForm
          onSubmit={onAnalyze}
          currentScenario={project?.scenario}
        />
      </div>
    </div>
  );
}

export default function ProjectDetail() {
  const { id } = useParams<{ id: string }>();
  const [project, setProject] = useState<Project | null>(null);
  const [report, setReport] = useState<AnalysisReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError(null);

    try {
      const proj = await api.getProject(id);
      setProject(proj);

      if (proj.status === 'completed') {
        try {
          const rep = await api.getReport(id);
          setReport(rep);
        } catch {
          // Report may not exist yet
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load project');
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleAnalyze = async (
    gitLog: File,
    manifests: File[],
    scenario: Scenario,
  ) => {
    if (!id) return;
    await api.triggerAnalysis(id, gitLog, manifests.length > 0 ? manifests : undefined, scenario);
    await loadData();
  };

  if (loading && !project) {
    return (
      <div className="animate-pulse space-y-6">
        <div className="h-8 w-64 rounded bg-navy-800" />
        <div className="h-4 w-48 rounded bg-navy-800" />
        <div className="h-12 rounded bg-navy-800" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="py-16 text-center">
        <p className="text-sm text-red-400">{error}</p>
        <Link
          to="/projects"
          className="mt-3 inline-flex items-center gap-1 text-sm text-accent-blue hover:text-blue-400"
        >
          <ArrowLeft className="h-4 w-4" /> Back to projects
        </Link>
      </div>
    );
  }

  return (
    <div>
      {/* Header */}
      <div className="mb-6">
        <Link
          to="/projects"
          className="mb-3 inline-flex items-center gap-1 text-xs text-navy-500 hover:text-navy-300"
        >
          <ArrowLeft className="h-3 w-3" /> Back to projects
        </Link>
        <div className="flex items-center gap-4">
          <div className="flex-1">
            <h1 className="text-2xl font-bold text-white">
              {project?.name}
            </h1>
            <div className="mt-1 flex items-center gap-3">
              <span className="rounded-md bg-navy-800 px-2 py-0.5 text-xs text-navy-400">
                {project?.scenario}
              </span>
              {project?.status && (
                <span
                  className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                    project.status === 'completed'
                      ? 'bg-green-500/10 text-green-400'
                      : project.status === 'analyzing'
                        ? 'bg-blue-500/10 text-blue-400'
                        : project.status === 'failed'
                          ? 'bg-red-500/10 text-red-400'
                          : 'bg-navy-700 text-navy-400'
                  }`}
                >
                  {project.status}
                </span>
              )}
            </div>
          </div>
          {project?.health_score !== null && project?.health_score !== undefined && (
            <HealthScore score={project.health_score} size="md" />
          )}
        </div>
      </div>

      {/* Tabs */}
      <div className="mb-6 flex gap-1 overflow-x-auto rounded-lg border border-navy-800 bg-navy-800/30 p-1">
        {tabs.map((tab) => (
          <NavLink
            key={tab.path}
            to={tab.path}
            end={tab.end}
            className={({ isActive }) =>
              `flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition ${
                isActive
                  ? 'bg-navy-700 text-white'
                  : 'text-navy-400 hover:bg-navy-800 hover:text-navy-200'
              }`
            }
          >
            <tab.icon className="h-4 w-4" />
            {tab.label}
          </NavLink>
        ))}
      </div>

      {/* Tab Content */}
      <Routes>
        <Route
          index
          element={
            <OverviewTab
              project={project}
              report={report}
              loading={loading}
              onAnalyze={handleAnalyze}
            />
          }
        />
        <Route
          path="dimensions"
          element={<DimensionsView projectId={id!} />}
        />
        <Route
          path="components"
          element={<ComponentsView projectId={id!} />}
        />
        <Route
          path="hotspots"
          element={<HotspotsView projectId={id!} />}
        />
        <Route
          path="trends"
          element={<TrendsView projectId={id!} />}
        />
        <Route path="report" element={<Navigate to=".." replace />} />
      </Routes>
    </div>
  );
}
