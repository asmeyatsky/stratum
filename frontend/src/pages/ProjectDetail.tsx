import { useEffect, useState, useCallback, createContext, useContext } from 'react';
import { useParams, NavLink, Outlet } from 'react-router-dom';
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
import type { Project, AnalysisReport, FeatureBugTrend, Scenario } from '../types';
import HealthScore from '../components/HealthScore';
import ErrorBoundary from '../components/ErrorBoundary';
import { useAnalysisProgress } from '../hooks/useAnalysisProgress';

// --- Context for sharing project data with child routes ---

interface ProjectContextValue {
  project: Project | null;
  report: AnalysisReport | null;
  loading: boolean;
  onAnalyze: (gitLog: File, manifests: File[], scenario: Scenario) => Promise<void>;
}

const ProjectContext = createContext<ProjectContextValue>({
  project: null,
  report: null,
  loading: true,
  onAnalyze: async () => {},
});

export function useProjectContext() {
  return useContext(ProjectContext);
}

// --- Tab config ---

const tabs = [
  { path: '', label: 'Overview', icon: Layers, end: true },
  { path: 'dimensions', label: 'Dimensions', icon: BarChart3, end: false },
  { path: 'components', label: 'Components', icon: Grid3x3, end: false },
  { path: 'hotspots', label: 'Hotspots', icon: Flame, end: false },
  { path: 'trends', label: 'Trends', icon: TrendingUp, end: false },
];

// --- Layout component ---

export default function ProjectDetail() {
  const { id } = useParams<{ id: string }>();
  const [project, setProject] = useState<Project | null>(null);
  const [report, setReport] = useState<AnalysisReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Real-time analysis progress via WebSocket
  const isRunning = project?.status === 'running';
  const { progress: analysisProgress } = useAnalysisProgress(
    isRunning && id ? id : null,
  );

  const loadData = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError(null);

    try {
      const proj = await api.getProject(id);
      setProject(proj);

      if (proj.status === 'completed') {
        try {
          const [rep, trends] = await Promise.all([
            api.getReport(id),
            api.getTrends(id).catch(() => [] as FeatureBugTrend[]),
          ]);
          setReport({ ...rep, trends });
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

  // Auto-refresh when WebSocket reports analysis completion
  useEffect(() => {
    if (analysisProgress?.status === 'completed') {
      loadData();
    }
  }, [analysisProgress?.status, loadData]);

  const handleAnalyze = useCallback(async (
    gitLog: File,
    manifests: File[],
    scenario: Scenario,
  ) => {
    if (!id) return;
    await api.triggerAnalysis(id, gitLog, manifests.length > 0 ? manifests : undefined, scenario);
    await loadData();
  }, [id, loadData]);

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
    <ProjectContext.Provider value={{ project, report, loading, onAnalyze: handleAnalyze }}>
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
                        : project.status === 'running'
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

        {/* Analysis progress (shown while running) */}
        {isRunning && analysisProgress && (
          <div className="mb-6 rounded-lg border border-navy-800 bg-navy-900/50 p-4">
            <div className="mb-2 flex items-center justify-between text-sm">
              <span className="font-medium text-navy-200">
                {analysisProgress.step}
              </span>
              <span className="text-navy-400">
                {Math.round(analysisProgress.progress)}%
              </span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-navy-800">
              <div
                className="h-full rounded-full bg-accent-blue transition-all duration-500"
                style={{ width: `${analysisProgress.progress}%` }}
              />
            </div>
            {analysisProgress.message && (
              <p className="mt-2 text-xs text-navy-500">
                {analysisProgress.message}
              </p>
            )}
          </div>
        )}

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

        {/* Tab Content — rendered by React Router via Outlet */}
        <ErrorBoundary>
          <Outlet />
        </ErrorBoundary>
      </div>
    </ProjectContext.Provider>
  );
}
