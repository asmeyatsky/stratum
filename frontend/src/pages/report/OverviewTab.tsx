import { BarChart3 } from 'lucide-react';
import { useProjectContext } from '../ProjectDetail';
import HealthScore from '../../components/HealthScore';
import SeverityBadge from '../../components/SeverityBadge';
import AnalysisUploadForm from '../../components/AnalysisUploadForm';
import { getScoreColor } from '../../utils/scores';

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

export default function OverviewTab() {
  const { project, report, loading, onAnalyze } = useProjectContext();

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
                        backgroundColor: getScoreColor(dim.score),
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
