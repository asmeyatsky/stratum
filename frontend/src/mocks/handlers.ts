import { http, HttpResponse } from 'msw';
import type {
  Project,
  AnalysisReport,
  DimensionScore,
  ComponentRisk,
  FileHotspot,
  FeatureBugTrend,
} from '../types';

const mockProjects: Project[] = [
  {
    id: 'proj-1',
    name: 'Backend API',
    scenario: 'default',
    created_at: '2026-01-15T10:00:00Z',
    updated_at: '2026-03-01T14:30:00Z',
    last_analysis_at: '2026-03-01T14:30:00Z',
    health_score: 7.2,
    status: 'completed',
  },
  {
    id: 'proj-2',
    name: 'Frontend App',
    scenario: 'pre-release',
    created_at: '2026-02-20T09:00:00Z',
    updated_at: '2026-03-05T11:00:00Z',
    last_analysis_at: '2026-03-05T11:00:00Z',
    health_score: 5.4,
    status: 'completed',
  },
];

const mockDimensions: DimensionScore[] = [
  {
    id: 'dim-1',
    name: 'Code Complexity',
    score: 6.5,
    severity: 'medium',
    weight: 1.5,
    evidence: ['Average cyclomatic complexity: 12.3', 'Deeply nested functions found in 8 files'],
    description: 'Measures the structural complexity of the codebase',
  },
  {
    id: 'dim-2',
    name: 'Test Coverage',
    score: 8.1,
    severity: 'low',
    weight: 1.0,
    evidence: ['Overall coverage: 81%', 'Critical paths covered: 95%'],
    description: 'Evaluates the breadth and depth of test coverage',
  },
  {
    id: 'dim-3',
    name: 'Code Churn',
    score: 3.2,
    severity: 'high',
    weight: 1.2,
    evidence: ['High churn in auth module', '15 files changed more than 20 times'],
    description: 'Tracks the frequency of code changes over time',
  },
];

const mockComponents: ComponentRisk[] = [
  {
    name: 'auth-service',
    path: 'src/services/auth',
    composite_score: 7.8,
    severity: 'high',
    file_count: 12,
    dimension_scores: { code_complexity: 8.1, code_churn: 7.5, test_coverage: 3.2 },
    systemic_risks: ['Single point of failure', 'High coupling'],
  },
  {
    name: 'api-gateway',
    path: 'src/gateway',
    composite_score: 4.2,
    severity: 'medium',
    file_count: 8,
    dimension_scores: { code_complexity: 5.0, code_churn: 3.5, test_coverage: 6.1 },
    systemic_risks: [],
  },
];

const mockHotspots: FileHotspot[] = [
  {
    file_path: 'src/services/auth/handler.ts',
    risk_score: 8.9,
    severity: 'critical',
    churn_rate: 9.2,
    complexity: 7.8,
    bug_correlation: 8.5,
    ownership_fragmentation: 6.3,
    effort_estimate: 'large',
    indicators: ['god-file', 'high-churn', 'bus-factor-1'],
  },
  {
    file_path: 'src/gateway/router.ts',
    risk_score: 5.4,
    severity: 'medium',
    churn_rate: 4.1,
    complexity: 6.2,
    bug_correlation: 3.8,
    ownership_fragmentation: 2.1,
    effort_estimate: 'medium',
    indicators: ['moderate-complexity'],
  },
];

const mockTrends: FeatureBugTrend[] = [
  {
    period: '2026-01-01',
    features: 12,
    bugs: 5,
    refactors: 3,
    bug_fix_ratio: 0.25,
    total_commits: 20,
  },
  {
    period: '2026-01-15',
    features: 8,
    bugs: 7,
    refactors: 2,
    bug_fix_ratio: 0.41,
    total_commits: 17,
  },
  {
    period: '2026-02-01',
    features: 15,
    bugs: 4,
    refactors: 6,
    bug_fix_ratio: 0.16,
    total_commits: 25,
  },
  {
    period: '2026-02-15',
    features: 10,
    bugs: 9,
    refactors: 4,
    bug_fix_ratio: 0.39,
    total_commits: 23,
  },
  {
    period: '2026-03-01',
    features: 14,
    bugs: 3,
    refactors: 5,
    bug_fix_ratio: 0.14,
    total_commits: 22,
  },
];

const mockReport: AnalysisReport = {
  project_id: 'proj-1',
  generated_at: '2026-03-01T14:30:00Z',
  health_score: 7.2,
  dimensions: mockDimensions,
  components: mockComponents,
  hotspots: mockHotspots,
  trends: mockTrends,
  summary:
    'The codebase shows moderate health with key concerns in the auth-service module. Code churn is elevated, suggesting instability in core areas. Test coverage is strong overall but gaps exist in critical paths.',
};

export const handlers = [
  // Health
  http.get('/api/health', () => {
    return HttpResponse.json({ status: 'ok' });
  }),

  // Projects
  http.get('/api/projects', () => {
    return HttpResponse.json(mockProjects);
  }),

  http.get('/api/projects/:id', ({ params }) => {
    const project = mockProjects.find((p) => p.id === params.id);
    if (!project) {
      return new HttpResponse(null, { status: 404 });
    }
    return HttpResponse.json(project);
  }),

  http.post('/api/projects', async ({ request }) => {
    const body = (await request.json()) as { name: string; scenario: string };
    const newProject: Project = {
      id: 'proj-new',
      name: body.name,
      scenario: body.scenario as Project['scenario'],
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      last_analysis_at: null,
      health_score: null,
      status: 'pending',
    };
    return HttpResponse.json(newProject, { status: 201 });
  }),

  http.delete('/api/projects/:id', () => {
    return new HttpResponse(null, { status: 204 });
  }),

  // Report
  http.get('/api/projects/:id/report', ({ params }) => {
    const report = { ...mockReport, project_id: params.id as string };
    return HttpResponse.json(report);
  }),

  http.get('/api/projects/:id/report/dimensions', () => {
    return HttpResponse.json(mockDimensions);
  }),

  http.get('/api/projects/:id/report/components', () => {
    return HttpResponse.json(mockComponents);
  }),

  http.get('/api/projects/:id/report/hotspots', () => {
    return HttpResponse.json(mockHotspots);
  }),

  http.get('/api/projects/:id/report/trends', () => {
    return HttpResponse.json(mockTrends);
  }),
];
