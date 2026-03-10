import { useState, useRef } from 'react';
import { Upload, FileText, X, Loader2 } from 'lucide-react';
import type { Scenario } from '../types';

interface AnalysisUploadFormProps {
  onSubmit: (gitLog: File, manifests: File[], scenario: Scenario) => Promise<void>;
  currentScenario?: Scenario;
}

const SCENARIOS: { value: Scenario; label: string; description: string }[] = [
  { value: 'default', label: 'Default', description: 'Standard analysis' },
  { value: 'pre-release', label: 'Pre-Release', description: 'Focus on stability risks' },
  { value: 'onboarding', label: 'Onboarding', description: 'Developer onboarding insights' },
  { value: 'tech-debt', label: 'Tech Debt', description: 'Technical debt assessment' },
  { value: 'post-incident', label: 'Post-Incident', description: 'Post-incident review' },
];

export default function AnalysisUploadForm({
  onSubmit,
  currentScenario = 'default',
}: AnalysisUploadFormProps) {
  const [gitLogFile, setGitLogFile] = useState<File | null>(null);
  const [manifestFiles, setManifestFiles] = useState<File[]>([]);
  const [scenario, setScenario] = useState<Scenario>(currentScenario);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const gitLogInputRef = useRef<HTMLInputElement>(null);
  const manifestInputRef = useRef<HTMLInputElement>(null);

  const handleGitLogChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setGitLogFile(file);
      setError(null);
    }
  };

  const handleManifestChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    setManifestFiles((prev) => [...prev, ...files]);
  };

  const removeManifest = (index: number) => {
    setManifestFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!gitLogFile) {
      setError('Git log file is required');
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      await onSubmit(gitLogFile, manifestFiles, scenario);
      setGitLogFile(null);
      setManifestFiles([]);
      if (gitLogInputRef.current) gitLogInputRef.current.value = '';
      if (manifestInputRef.current) manifestInputRef.current.value = '';
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Analysis failed');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      {error && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-400">
          {error}
        </div>
      )}

      {/* Scenario Selector */}
      <div>
        <label className="mb-1.5 block text-sm font-medium text-navy-300">
          Analysis Scenario
        </label>
        <select
          value={scenario}
          onChange={(e) => setScenario(e.target.value as Scenario)}
          className="w-full rounded-lg border border-navy-700 bg-navy-800 px-3 py-2 text-sm text-navy-200 outline-none transition focus:border-accent-blue focus:ring-1 focus:ring-accent-blue"
        >
          {SCENARIOS.map((s) => (
            <option key={s.value} value={s.value}>
              {s.label} — {s.description}
            </option>
          ))}
        </select>
      </div>

      {/* Git Log File */}
      <div>
        <label className="mb-1.5 block text-sm font-medium text-navy-300">
          Git Log File <span className="text-red-400">*</span>
        </label>
        <div
          onClick={() => gitLogInputRef.current?.click()}
          className={`flex cursor-pointer items-center gap-3 rounded-lg border-2 border-dashed px-4 py-4 transition ${
            gitLogFile
              ? 'border-accent-blue/50 bg-accent-blue/5'
              : 'border-navy-700 bg-navy-800/50 hover:border-navy-600'
          }`}
        >
          {gitLogFile ? (
            <>
              <FileText className="h-5 w-5 text-accent-blue" />
              <div className="flex-1">
                <p className="text-sm font-medium text-navy-200">
                  {gitLogFile.name}
                </p>
                <p className="text-xs text-navy-500">
                  {(gitLogFile.size / 1024).toFixed(1)} KB
                </p>
              </div>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  setGitLogFile(null);
                  if (gitLogInputRef.current) gitLogInputRef.current.value = '';
                }}
                className="rounded p-1 text-navy-500 hover:bg-navy-700 hover:text-navy-300"
              >
                <X className="h-4 w-4" />
              </button>
            </>
          ) : (
            <>
              <Upload className="h-5 w-5 text-navy-500" />
              <div>
                <p className="text-sm text-navy-400">
                  Click to upload git log file
                </p>
                <p className="text-xs text-navy-600">
                  Output of: git log --numstat --pretty=format:...
                </p>
              </div>
            </>
          )}
        </div>
        <input
          ref={gitLogInputRef}
          type="file"
          accept=".log,.txt,.csv"
          onChange={handleGitLogChange}
          className="hidden"
        />
      </div>

      {/* Manifest Files */}
      <div>
        <label className="mb-1.5 block text-sm font-medium text-navy-300">
          Manifest Files{' '}
          <span className="text-navy-500">(optional, multiple)</span>
        </label>
        <div
          onClick={() => manifestInputRef.current?.click()}
          className="flex cursor-pointer items-center gap-3 rounded-lg border-2 border-dashed border-navy-700 bg-navy-800/50 px-4 py-4 transition hover:border-navy-600"
        >
          <Upload className="h-5 w-5 text-navy-500" />
          <div>
            <p className="text-sm text-navy-400">
              Click to add manifest files
            </p>
            <p className="text-xs text-navy-600">
              package.json, requirements.txt, Cargo.toml, etc.
            </p>
          </div>
        </div>
        <input
          ref={manifestInputRef}
          type="file"
          multiple
          onChange={handleManifestChange}
          className="hidden"
        />

        {manifestFiles.length > 0 && (
          <div className="mt-2 space-y-1">
            {manifestFiles.map((file, i) => (
              <div
                key={`${file.name}-${i}`}
                className="flex items-center gap-2 rounded-md bg-navy-800 px-3 py-1.5"
              >
                <FileText className="h-3.5 w-3.5 text-navy-500" />
                <span className="flex-1 truncate text-xs text-navy-300">
                  {file.name}
                </span>
                <span className="text-xs text-navy-600">
                  {(file.size / 1024).toFixed(1)} KB
                </span>
                <button
                  type="button"
                  onClick={() => removeManifest(i)}
                  className="rounded p-0.5 text-navy-600 hover:bg-navy-700 hover:text-navy-400"
                >
                  <X className="h-3 w-3" />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Submit */}
      <button
        type="submit"
        disabled={isSubmitting || !gitLogFile}
        className="flex w-full items-center justify-center gap-2 rounded-lg bg-accent-blue px-4 py-2.5 text-sm font-medium text-white transition hover:bg-blue-600 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {isSubmitting ? (
          <>
            <Loader2 className="h-4 w-4 animate-spin" />
            Running Analysis...
          </>
        ) : (
          <>
            <Upload className="h-4 w-4" />
            Run Analysis
          </>
        )}
      </button>
    </form>
  );
}
