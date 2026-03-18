import { http, HttpResponse } from 'msw';

// All mock data uses the API response format.
// The client.ts mapping layer converts to frontend types.

const mockApiProjects = [
  {
    project_id: 'proj-1',
    name: 'Backend API',
    description: 'Main backend service',
    scenario: 'cto_onboarding',
    created_at: '2026-01-15T10:00:00Z',
    updated_at: '2026-03-01T14:30:00Z',
    analysis_status: 'completed',
    overall_health_score: 7.2,
  },
  {
    project_id: 'proj-2',
    name: 'Frontend App',
    description: 'React frontend',
    scenario: 'ma_due_diligence',
    created_at: '2026-02-20T09:00:00Z',
    updated_at: '2026-03-05T11:00:00Z',
    analysis_status: 'completed',
    overall_health_score: 5.4,
  },
];

// API-format dimension scores (dict, not array)
const mockDimensionScores: Record<string, { value: number; severity: string; label: string; evidence: string }> = {
  code_complexity: { value: 6.5, severity: 'medium', label: 'Code Complexity', evidence: 'Average cyclomatic complexity: 12.3' },
  test_coverage: { value: 8.1, severity: 'low', label: 'Test Coverage', evidence: 'Overall coverage: 81%' },
  code_churn: { value: 3.2, severity: 'high', label: 'Code Churn', evidence: 'High churn in auth module' },
};

// API-format component risks
const mockApiComponents = [
  {
    component_name: 'auth-service',
    composite_score: 7.8,
    systemic_risk: true,
    dimension_scores: {
      code_complexity: { value: 8.1, severity: 'high', label: 'Code Complexity', evidence: 'High' },
      code_churn: { value: 7.5, severity: 'high', label: 'Code Churn', evidence: 'Elevated' },
      test_coverage: { value: 3.2, severity: 'low', label: 'Test Coverage', evidence: 'Low' },
    },
  },
  {
    component_name: 'api-gateway',
    composite_score: 4.2,
    systemic_risk: false,
    dimension_scores: {
      code_complexity: { value: 5.0, severity: 'medium', label: 'Code Complexity', evidence: 'Moderate' },
    },
  },
];

// API-format hotspots
const mockApiHotspots = [
  {
    file_path: 'src/services/auth/handler.ts',
    composite_risk_score: 8.9,
    risk_indicators: { churn: 9.2, complexity: 7.8, bug_density: 8.5, ownership: 6.3 },
    refactoring_recommendation: 'Split into smaller services',
    effort_estimate: 'large',
  },
  {
    file_path: 'src/gateway/router.ts',
    composite_risk_score: 5.4,
    risk_indicators: { churn: 4.1, complexity: 6.2, bug_density: 3.8 },
    refactoring_recommendation: 'Reduce complexity',
    effort_estimate: 'medium',
  },
];

// API-format trends
const mockApiTrends = [
  { period: '2026-01-01', features: 12, bugs: 5, refactors: 3, bug_fix_ratio: 0.25, total_commits: 20 },
  { period: '2026-01-15', features: 8, bugs: 7, refactors: 2, bug_fix_ratio: 0.41, total_commits: 17 },
  { period: '2026-02-01', features: 15, bugs: 4, refactors: 6, bug_fix_ratio: 0.16, total_commits: 25 },
];

// API-format full report
const mockApiReport = {
  project_id: 'proj-1',
  project_name: 'Backend API',
  scenario: 'cto_onboarding',
  analysis_timestamp: '2026-03-01T14:30:00Z',
  overall_health_score: 7.2,
  dimension_scores: mockDimensionScores,
  top_risks: [
    { dimension: 'code_churn', value: 3.2, severity: 'high', label: 'Code Churn', evidence: 'High churn' },
  ],
  component_risks: mockApiComponents,
  file_hotspots: mockApiHotspots,
  ai_narrative: 'The codebase shows moderate health with key concerns in the auth-service module.',
  pdf_output_path: '',
};

export const handlers = [
  // Health
  http.get('/api/health', () => {
    return HttpResponse.json({ status: 'ok' });
  }),

  // Projects
  http.get('/api/projects', () => {
    return HttpResponse.json({ projects: mockApiProjects, total: mockApiProjects.length });
  }),

  http.get('/api/projects/:id', ({ params }) => {
    const project = mockApiProjects.find((p) => p.project_id === params.id);
    if (!project) {
      return new HttpResponse(null, { status: 404 });
    }
    return HttpResponse.json(project);
  }),

  http.post('/api/projects', async ({ request }) => {
    const body = (await request.json()) as { name: string; scenario: string };
    return HttpResponse.json(
      {
        project_id: 'proj-new',
        name: body.name,
        description: '',
        scenario: body.scenario || 'cto_onboarding',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        analysis_status: 'pending',
        overall_health_score: null,
      },
      { status: 201 },
    );
  }),

  http.delete('/api/projects/:id', () => {
    return new HttpResponse(null, { status: 204 });
  }),

  // Report endpoints — all return API format
  http.get('/api/projects/:id/report', ({ params }) => {
    return HttpResponse.json({ ...mockApiReport, project_id: params.id as string });
  }),

  http.get('/api/projects/:id/report/dimensions', () => {
    return HttpResponse.json({ project_id: 'proj-1', overall_health_score: 7.2, dimensions: mockDimensionScores });
  }),

  http.get('/api/projects/:id/report/components', () => {
    return HttpResponse.json({ project_id: 'proj-1', components: mockApiComponents });
  }),

  http.get('/api/projects/:id/report/hotspots', () => {
    return HttpResponse.json({ project_id: 'proj-1', hotspots: mockApiHotspots });
  }),

  http.get('/api/projects/:id/report/trends', () => {
    return HttpResponse.json({ project_id: 'proj-1', trends: mockApiTrends });
  }),
];
