import { useEffect, useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import {
  Plus,
  Trash2,
  X,
  Loader2,
  FolderKanban,
  Search,
} from 'lucide-react';
import api from '../api/client';
import type { Project, Scenario } from '../types';
import HealthScore from '../components/HealthScore';

const SCENARIOS: { value: Scenario; label: string }[] = [
  { value: 'cto_onboarding', label: 'CTO Onboarding' },
  { value: 'ma_due_diligence', label: 'M&A Due Diligence' },
  { value: 'vendor_audit', label: 'Vendor Audit' },
  { value: 'post_merger', label: 'Post-Merger' },
  { value: 'decommission', label: 'Decommission' },
  { value: 'oss_assessment', label: 'OSS Assessment' },
];

function SkeletonRow() {
  return (
    <tr className="animate-pulse">
      <td className="px-4 py-3">
        <div className="h-4 w-40 rounded bg-navy-700" />
      </td>
      <td className="px-4 py-3">
        <div className="h-4 w-20 rounded bg-navy-700" />
      </td>
      <td className="px-4 py-3">
        <div className="h-4 w-24 rounded bg-navy-700" />
      </td>
      <td className="px-4 py-3">
        <div className="h-4 w-12 rounded bg-navy-700" />
      </td>
      <td className="px-4 py-3">
        <div className="h-4 w-16 rounded bg-navy-700" />
      </td>
      <td className="px-4 py-3">
        <div className="h-4 w-8 rounded bg-navy-700" />
      </td>
    </tr>
  );
}

export default function ProjectList() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showModal, setShowModal] = useState(false);
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState('');
  const [newScenario, setNewScenario] = useState<Scenario>('cto_onboarding');
  const [searchQuery, setSearchQuery] = useState('');
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);

  const loadProjects = useCallback(() => {
    setLoading(true);
    api
      .getProjects()
      .then(setProjects)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    loadProjects();
  }, [loadProjects]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newName.trim()) return;

    setCreating(true);
    try {
      await api.createProject({ name: newName.trim(), scenario: newScenario });
      setShowModal(false);
      setNewName('');
      setNewScenario('cto_onboarding');
      loadProjects();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create project');
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async (id: string) => {
    setDeleteConfirmId(null);
    setDeletingId(id);
    try {
      await api.deleteProject(id);
      setProjects((prev) => prev.filter((p) => p.id !== id));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete project');
    } finally {
      setDeletingId(null);
    }
  };

  const filtered = projects.filter((p) =>
    p.name.toLowerCase().includes(searchQuery.toLowerCase()),
  );

  return (
    <div>
      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Projects</h1>
          <p className="mt-1 text-sm text-navy-400">
            Manage your code analysis projects
          </p>
        </div>
        <button
          onClick={() => setShowModal(true)}
          className="flex items-center gap-2 rounded-lg bg-accent-blue px-4 py-2 text-sm font-medium text-white transition hover:bg-blue-600"
        >
          <Plus className="h-4 w-4" />
          New Project
        </button>
      </div>

      {error && (
        <div className="mb-4 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-400">
          {error}
          <button
            onClick={() => setError(null)}
            className="ml-2 text-red-300 underline hover:text-red-200"
          >
            dismiss
          </button>
        </div>
      )}

      {/* Search Bar */}
      <div className="mb-4 flex items-center gap-2 rounded-lg border border-navy-800 bg-navy-800/40 px-3 py-2">
        <Search className="h-4 w-4 text-navy-500" />
        <input
          type="text"
          placeholder="Search projects..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="flex-1 bg-transparent text-sm text-navy-200 outline-none placeholder:text-navy-600"
        />
      </div>

      {/* Table */}
      <div className="overflow-hidden rounded-xl border border-navy-800 bg-navy-800/20">
        <table className="w-full">
          <thead>
            <tr className="border-b border-navy-800 bg-navy-800/40">
              <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-navy-500">
                Name
              </th>
              <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-navy-500">
                Scenario
              </th>
              <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-navy-500">
                Last Analysis
              </th>
              <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-navy-500">
                Health
              </th>
              <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-navy-500">
                Status
              </th>
              <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wider text-navy-500">
                Actions
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-navy-800/60">
            {loading ? (
              <>
                <SkeletonRow />
                <SkeletonRow />
                <SkeletonRow />
              </>
            ) : filtered.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-4 py-16 text-center">
                  <FolderKanban className="mx-auto mb-3 h-8 w-8 text-navy-700" />
                  <p className="text-sm text-navy-500">
                    {searchQuery
                      ? 'No projects match your search.'
                      : 'No projects yet. Create one to get started.'}
                  </p>
                </td>
              </tr>
            ) : (
              filtered.map((project) => (
                <tr
                  key={project.id}
                  className="transition hover:bg-navy-800/30"
                >
                  <td className="px-4 py-3">
                    <Link
                      to={`/projects/${project.id}`}
                      className="text-sm font-medium text-navy-200 hover:text-accent-blue"
                    >
                      {project.name}
                    </Link>
                  </td>
                  <td className="px-4 py-3">
                    <span className="rounded-md bg-navy-800 px-2 py-0.5 text-xs text-navy-400">
                      {project.scenario}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-sm text-navy-400">
                    {project.last_analysis_at
                      ? new Date(project.last_analysis_at).toLocaleDateString(
                          'en-US',
                          {
                            month: 'short',
                            day: 'numeric',
                            year: 'numeric',
                          },
                        )
                      : '---'}
                  </td>
                  <td className="px-4 py-3">
                    <HealthScore
                      score={project.health_score}
                      size="sm"
                      showLabel={false}
                    />
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${
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
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button
                      onClick={() => setDeleteConfirmId(project.id)}
                      disabled={deletingId === project.id}
                      className="rounded p-1.5 text-navy-600 transition hover:bg-red-500/10 hover:text-red-400 disabled:opacity-50"
                      aria-label={`Delete project ${project.name}`}
                    >
                      {deletingId === project.id ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <Trash2 className="h-4 w-4" />
                      )}
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Delete Confirmation Modal */}
      {deleteConfirmId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div
            role="dialog"
            aria-modal="true"
            className="w-full max-w-sm rounded-xl border border-navy-700 bg-navy-900 p-6 shadow-2xl"
          >
            <div className="mb-5 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-white">
                Delete Project
              </h2>
              <button
                onClick={() => setDeleteConfirmId(null)}
                className="rounded p-1 text-navy-500 hover:bg-navy-800 hover:text-navy-300"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <p className="mb-6 text-sm text-navy-400">
              Are you sure you want to delete this project? This action cannot
              be undone.
            </p>
            <div className="flex gap-3">
              <button
                type="button"
                onClick={() => setDeleteConfirmId(null)}
                className="flex-1 rounded-lg border border-navy-700 px-4 py-2 text-sm font-medium text-navy-300 transition hover:bg-navy-800"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => handleDelete(deleteConfirmId)}
                className="flex-1 rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-red-700"
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Create Modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div
            role="dialog"
            aria-modal="true"
            className="w-full max-w-md rounded-xl border border-navy-700 bg-navy-900 p-6 shadow-2xl"
          >
            <div className="mb-5 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-white">
                New Project
              </h2>
              <button
                onClick={() => setShowModal(false)}
                className="rounded p-1 text-navy-500 hover:bg-navy-800 hover:text-navy-300"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <form onSubmit={handleCreate} className="space-y-4">
              <div>
                <label className="mb-1.5 block text-sm font-medium text-navy-300">
                  Project Name
                </label>
                <input
                  type="text"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  placeholder="e.g., Backend API"
                  autoFocus
                  className="w-full rounded-lg border border-navy-700 bg-navy-800 px-3 py-2 text-sm text-navy-200 outline-none transition placeholder:text-navy-600 focus:border-accent-blue focus:ring-1 focus:ring-accent-blue"
                />
              </div>

              <div>
                <label className="mb-1.5 block text-sm font-medium text-navy-300">
                  Scenario
                </label>
                <select
                  value={newScenario}
                  onChange={(e) =>
                    setNewScenario(e.target.value as Scenario)
                  }
                  className="w-full rounded-lg border border-navy-700 bg-navy-800 px-3 py-2 text-sm text-navy-200 outline-none transition focus:border-accent-blue focus:ring-1 focus:ring-accent-blue"
                >
                  {SCENARIOS.map((s) => (
                    <option key={s.value} value={s.value}>
                      {s.label}
                    </option>
                  ))}
                </select>
              </div>

              <div className="flex gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="flex-1 rounded-lg border border-navy-700 px-4 py-2 text-sm font-medium text-navy-300 transition hover:bg-navy-800"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={creating || !newName.trim()}
                  className="flex flex-1 items-center justify-center gap-2 rounded-lg bg-accent-blue px-4 py-2 text-sm font-medium text-white transition hover:bg-blue-600 disabled:opacity-50"
                >
                  {creating ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Creating...
                    </>
                  ) : (
                    'Create Project'
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
