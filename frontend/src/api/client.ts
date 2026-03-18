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

// --- Auth token management ---

let authToken: string | null = null;

export function setAuthToken(token: string) {
  authToken = token;
}

export function clearAuthToken() {
  authToken = null;
}

export function getAuthToken(): string | null {
  return authToken;
}

// --- API response → frontend type mapping ---

interface ApiProject {
  project_id: string;
  name: string;
  description: string;
  scenario: string;
  created_at: string;
  updated_at: string;
  analysis_status: string;
  overall_health_score: number | null;
}

function mapProject(raw: ApiProject): Project {
  return {
    id: raw.project_id,
    name: raw.name,
    description: raw.description,
    scenario: raw.scenario as Project['scenario'],
    created_at: raw.created_at,
    updated_at: raw.updated_at,
    last_analysis_at: raw.analysis_status === 'completed' ? raw.updated_at : null,
    health_score: raw.overall_health_score,
    status: raw.analysis_status as Project['status'],
  };
}

function scoreSeverity(value: number): string {
  if (value >= 9) return 'critical';
  if (value >= 7) return 'high';
  if (value >= 4) return 'medium';
  if (value >= 2) return 'low';
  return 'minimal';
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function mapDimensionDict(dims: Record<string, any>): DimensionScore[] {
  return Object.entries(dims).map(([key, d]) => ({
    id: key,
    name: d.label || key,
    score: d.value,
    severity: (d.severity || scoreSeverity(d.value)) as DimensionScore['severity'],
    weight: 1,
    evidence: Array.isArray(d.evidence) ? d.evidence : [d.evidence || ''],
    description: d.label || key,
  }));
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function mapComponent(raw: any): ComponentRisk {
  const dimScores: Record<string, number> = {};
  for (const [key, val] of Object.entries(raw.dimension_scores || {})) {
    dimScores[key] = (val as { value: number }).value;
  }
  const score = raw.composite_score;
  return {
    name: raw.component_name,
    path: raw.component_name,
    composite_score: score,
    severity: scoreSeverity(score) as ComponentRisk['severity'],
    file_count: 0,
    dimension_scores: dimScores,
    systemic_risks: raw.systemic_risk ? ['Systemic risk: 3+ dimensions above 7'] : [],
  };
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function mapHotspot(raw: any): FileHotspot {
  const ri = raw.risk_indicators || {};
  const score = raw.composite_risk_score;
  return {
    file_path: raw.file_path,
    risk_score: score,
    severity: scoreSeverity(score) as FileHotspot['severity'],
    churn_rate: ri.churn ?? ri.churn_rate ?? 0,
    complexity: ri.complexity ?? 0,
    bug_correlation: ri.bug_density ?? ri.bug_correlation ?? 0,
    ownership_fragmentation: ri.ownership ?? ri.ownership_fragmentation ?? 0,
    effort_estimate: raw.effort_estimate || 'medium',
    indicators: Object.keys(ri),
  };
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function mapReport(raw: any): AnalysisReport {
  return {
    project_id: raw.project_id,
    generated_at: raw.analysis_timestamp,
    health_score: raw.overall_health_score,
    dimensions: mapDimensionDict(raw.dimension_scores || {}),
    components: (raw.component_risks || []).map(mapComponent),
    hotspots: (raw.file_hotspots || []).map(mapHotspot),
    trends: [],
    summary: raw.ai_narrative || '',
  };
}

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

  if (authToken) {
    headers['Authorization'] = `Bearer ${authToken}`;
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 30_000);

  try {
    const response = await fetch(url, {
      ...options,
      headers,
      signal: controller.signal,
    });

    if (!response.ok) {
      const body = await response.text();
      throw new ApiError(response.status, body || response.statusText);
    }

    if (response.status === 204) {
      return undefined as T;
    }

    return response.json();
  } finally {
    clearTimeout(timeoutId);
  }
}

export const api = {
  // Health
  health(): Promise<{ status: string }> {
    return request('/health');
  },

  // Projects
  async getProjects(): Promise<Project[]> {
    const data = await request<{ projects: ApiProject[]; total: number }>('/projects');
    return data.projects.map(mapProject);
  },

  async getProject(id: string): Promise<Project> {
    const raw = await request<ApiProject>(`/projects/${id}`);
    return mapProject(raw);
  },

  async createProject(payload: CreateProjectPayload): Promise<Project> {
    const raw = await request<ApiProject>('/projects', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    return mapProject(raw);
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
  async getReport(projectId: string): Promise<AnalysisReport> {
    const raw = await request<Record<string, unknown>>(`/projects/${projectId}/report`);
    return mapReport(raw);
  },

  async getDimensions(projectId: string): Promise<DimensionScore[]> {
    const raw = await request<{ dimensions: Record<string, unknown> }>(`/projects/${projectId}/report/dimensions`);
    return mapDimensionDict(raw.dimensions);
  },

  async getComponents(projectId: string): Promise<ComponentRisk[]> {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const raw = await request<{ components: any[] }>(`/projects/${projectId}/report/components`);
    return raw.components.map(mapComponent);
  },

  async getHotspots(projectId: string): Promise<FileHotspot[]> {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const raw = await request<{ hotspots: any[] }>(`/projects/${projectId}/report/hotspots`);
    return raw.hotspots.map(mapHotspot);
  },

  async getTrends(projectId: string): Promise<FeatureBugTrend[]> {
    const raw = await request<{ trends: FeatureBugTrend[] }>(`/projects/${projectId}/report/trends`);
    return raw.trends.map((t) => ({
      ...t,
      bug_fix_ratio: t.bug_fix_ratio ?? (t.total_commits > 0 ? t.bugs / t.total_commits : 0),
    }));
  },
};

export { ApiError };
export default api;
