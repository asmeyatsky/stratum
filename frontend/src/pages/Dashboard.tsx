import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  AlertTriangle,
  Activity,
  FolderKanban,
  Clock,
  ArrowRight,
} from 'lucide-react';
import api from '../api/client';
import type { Project } from '../types';
import HealthScore from '../components/HealthScore';

function SkeletonCard() {
  return (
    <div className="animate-pulse rounded-xl border border-navy-800 bg-navy-800/40 p-5">
      <div className="mb-3 h-4 w-24 rounded bg-navy-700" />
      <div className="h-8 w-16 rounded bg-navy-700" />
    </div>
  );
}

function SkeletonRow() {
  return (
    <div className="flex animate-pulse items-center gap-4 rounded-lg bg-navy-800/40 px-4 py-3">
      <div className="h-4 w-4 rounded bg-navy-700" />
      <div className="h-4 flex-1 rounded bg-navy-700" />
      <div className="h-5 w-16 rounded-full bg-navy-700" />
    </div>
  );
}

export default function Dashboard() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .getProjects()
      .then((data) => {
        if (!cancelled) setProjects(data);
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
  }, []);

  const analyzedProjects = projects.filter(
    (p) => p.status === 'completed' && p.health_score !== null,
  );

  const avgHealth =
    analyzedProjects.length > 0
      ? analyzedProjects.reduce((sum, p) => sum + (p.health_score ?? 0), 0) /
        analyzedProjects.length
      : null;

  const atRiskProjects = analyzedProjects.filter(
    (p) => (p.health_score ?? 10) < 7,
  );

  const lastAnalysis = analyzedProjects
    .filter((p) => p.last_analysis_at)
    .sort(
      (a, b) =>
        new Date(b.last_analysis_at!).getTime() -
        new Date(a.last_analysis_at!).getTime(),
    )[0];

  return (
    <div>
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-white">Dashboard</h1>
        <p className="mt-1 text-sm text-navy-400">
          Overview of your codebase health and active projects
        </p>
      </div>

      {error && (
        <div className="mb-6 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-400">
          Failed to load data: {error}
        </div>
      )}

      {/* Stats Cards */}
      <div className="mb-8 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {loading ? (
          <>
            <SkeletonCard />
            <SkeletonCard />
            <SkeletonCard />
            <SkeletonCard />
          </>
        ) : (
          <>
            {/* Health Score */}
            <div className="rounded-xl border border-navy-800 bg-gradient-to-br from-navy-800/60 to-navy-900 p-5">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs font-medium uppercase tracking-wider text-navy-500">
                    Avg Health
                  </p>
                  <div className="mt-2">
                    <HealthScore score={avgHealth} size="sm" />
                  </div>
                </div>
                <div className="rounded-lg bg-accent-blue/10 p-2.5">
                  <Activity className="h-5 w-5 text-accent-blue" />
                </div>
              </div>
            </div>

            {/* Total Projects */}
            <div className="rounded-xl border border-navy-800 bg-gradient-to-br from-navy-800/60 to-navy-900 p-5">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs font-medium uppercase tracking-wider text-navy-500">
                    Projects
                  </p>
                  <p className="mt-2 text-3xl font-bold text-white">
                    {projects.length}
                  </p>
                </div>
                <div className="rounded-lg bg-accent-indigo/10 p-2.5">
                  <FolderKanban className="h-5 w-5 text-accent-indigo" />
                </div>
              </div>
            </div>

            {/* At Risk */}
            <div className="rounded-xl border border-navy-800 bg-gradient-to-br from-navy-800/60 to-navy-900 p-5">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs font-medium uppercase tracking-wider text-navy-500">
                    At Risk
                  </p>
                  <p className="mt-2 text-3xl font-bold text-white">
                    {atRiskProjects.length}
                  </p>
                </div>
                <div className="rounded-lg bg-risk-high/10 p-2.5">
                  <AlertTriangle className="h-5 w-5 text-risk-high" />
                </div>
              </div>
            </div>

            {/* Last Analysis */}
            <div className="rounded-xl border border-navy-800 bg-gradient-to-br from-navy-800/60 to-navy-900 p-5">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs font-medium uppercase tracking-wider text-navy-500">
                    Last Analysis
                  </p>
                  <p className="mt-2 text-sm font-medium text-navy-200">
                    {lastAnalysis?.last_analysis_at
                      ? new Date(
                          lastAnalysis.last_analysis_at,
                        ).toLocaleDateString('en-US', {
                          month: 'short',
                          day: 'numeric',
                          hour: '2-digit',
                          minute: '2-digit',
                        })
                      : 'No analyses yet'}
                  </p>
                </div>
                <div className="rounded-lg bg-accent-cyan/10 p-2.5">
                  <Clock className="h-5 w-5 text-accent-cyan" />
                </div>
              </div>
            </div>
          </>
        )}
      </div>

      {/* Top Risks Section */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* At-Risk Projects */}
        <div className="rounded-xl border border-navy-800 bg-navy-800/30 p-5">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-navy-200">
              Top Risks
            </h2>
            <Link
              to="/projects"
              className="flex items-center gap-1 text-xs font-medium text-accent-blue hover:text-blue-400"
            >
              View all <ArrowRight className="h-3 w-3" />
            </Link>
          </div>
          {loading ? (
            <div className="space-y-2">
              <SkeletonRow />
              <SkeletonRow />
              <SkeletonRow />
            </div>
          ) : atRiskProjects.length === 0 ? (
            <div className="py-8 text-center text-sm text-navy-500">
              {projects.length === 0
                ? 'No projects yet. Create one to get started.'
                : 'All projects are healthy.'}
            </div>
          ) : (
            <div className="space-y-2">
              {atRiskProjects.slice(0, 5).map((project) => (
                <Link
                  key={project.id}
                  to={`/projects/${project.id}`}
                  className="flex items-center gap-3 rounded-lg px-3 py-2.5 transition hover:bg-navy-800"
                >
                  <div
                    className={`h-2 w-2 rounded-full ${
                      (project.health_score ?? 10) < 4
                        ? 'bg-risk-critical'
                        : 'bg-risk-medium'
                    }`}
                  />
                  <span className="flex-1 truncate text-sm text-navy-300">
                    {project.name}
                  </span>
                  <span
                    className={`text-sm font-semibold ${
                      (project.health_score ?? 10) < 4
                        ? 'text-risk-critical'
                        : 'text-risk-medium'
                    }`}
                  >
                    {project.health_score?.toFixed(1)}
                  </span>
                </Link>
              ))}
            </div>
          )}
        </div>

        {/* Recent Projects */}
        <div className="rounded-xl border border-navy-800 bg-navy-800/30 p-5">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-navy-200">
              Recent Projects
            </h2>
            <Link
              to="/projects"
              className="flex items-center gap-1 text-xs font-medium text-accent-blue hover:text-blue-400"
            >
              View all <ArrowRight className="h-3 w-3" />
            </Link>
          </div>
          {loading ? (
            <div className="space-y-2">
              <SkeletonRow />
              <SkeletonRow />
              <SkeletonRow />
            </div>
          ) : projects.length === 0 ? (
            <div className="py-8 text-center text-sm text-navy-500">
              No projects yet.
            </div>
          ) : (
            <div className="space-y-2">
              {projects
                .sort(
                  (a, b) =>
                    new Date(b.updated_at).getTime() -
                    new Date(a.updated_at).getTime(),
                )
                .slice(0, 5)
                .map((project) => (
                  <Link
                    key={project.id}
                    to={`/projects/${project.id}`}
                    className="flex items-center gap-3 rounded-lg px-3 py-2.5 transition hover:bg-navy-800"
                  >
                    <FolderKanban className="h-4 w-4 text-navy-600" />
                    <span className="flex-1 truncate text-sm text-navy-300">
                      {project.name}
                    </span>
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
                  </Link>
                ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
