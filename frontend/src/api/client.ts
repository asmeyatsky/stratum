import type {
  Project,
  AnalysisReport,
  DimensionScore,
  ComponentRisk,
  FileHotspot,
  FeatureBugTrend,
  CreateProjectPayload,
} from '../types';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api';

class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const url = `${BASE_URL}${path}`;
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string>),
  };

  if (
    options.body &&
    !(options.body instanceof FormData) &&
    typeof options.body === 'string'
  ) {
    headers['Content-Type'] = 'application/json';
  }

  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const body = await response.text();
    throw new ApiError(response.status, body || response.statusText);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json();
}

export const api = {
  // Health
  health(): Promise<{ status: string }> {
    return request('/health');
  },

  // Projects
  getProjects(): Promise<Project[]> {
    return request('/projects');
  },

  getProject(id: string): Promise<Project> {
    return request(`/projects/${id}`);
  },

  createProject(payload: CreateProjectPayload): Promise<Project> {
    return request('/projects', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  deleteProject(id: string): Promise<void> {
    return request(`/projects/${id}`, { method: 'DELETE' });
  },

  // Analysis
  triggerAnalysis(
    projectId: string,
    gitLog: File,
    manifests?: File[],
    scenario?: string,
  ): Promise<{ status: string; message: string }> {
    const formData = new FormData();
    formData.append('git_log', gitLog);
    if (manifests) {
      manifests.forEach((file) => formData.append('manifests', file));
    }
    if (scenario) {
      formData.append('scenario', scenario);
    }
    return request(`/projects/${projectId}/analyze`, {
      method: 'POST',
      body: formData,
    });
  },

  // Report
  getReport(projectId: string): Promise<AnalysisReport> {
    return request(`/projects/${projectId}/report`);
  },

  getDimensions(projectId: string): Promise<DimensionScore[]> {
    return request(`/projects/${projectId}/report/dimensions`);
  },

  getComponents(projectId: string): Promise<ComponentRisk[]> {
    return request(`/projects/${projectId}/report/components`);
  },

  getHotspots(projectId: string): Promise<FileHotspot[]> {
    return request(`/projects/${projectId}/report/hotspots`);
  },

  getTrends(projectId: string): Promise<FeatureBugTrend[]> {
    return request(`/projects/${projectId}/report/trends`);
  },
};

export { ApiError };
export default api;
