import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';
import type { AnalysisReport, ComponentRisk } from '../types';

const mockComponents: ComponentRisk[] = [
  {
    name: 'auth-service',
    path: 'auth-service',
    composite_score: 7.8,
    severity: 'high',
    file_count: 0,
    dimension_scores: { code_complexity: 8.1, code_churn: 7.5, test_coverage: 3.2 },
    systemic_risks: ['Systemic risk: 3+ dimensions above 7'],
  },
  {
    name: 'api-gateway',
    path: 'api-gateway',
    composite_score: 4.2,
    severity: 'medium',
    file_count: 0,
    dimension_scores: { code_complexity: 5.0 },
    systemic_risks: [],
  },
];

const mockReport: AnalysisReport = {
  project_id: 'proj-1',
  generated_at: '2026-03-01T14:30:00Z',
  health_score: 7.2,
  dimensions: [],
  components: mockComponents,
  hotspots: [],
  trends: [],
  summary: 'Test summary',
};

// Mock the ProjectDetail context
vi.mock('../pages/ProjectDetail', () => ({
  useProjectContext: vi.fn(),
}));

import { useProjectContext } from '../pages/ProjectDetail';
import ComponentsView from '../pages/report/ComponentsView';

const mockedUseProjectContext = vi.mocked(useProjectContext);

function setMockReport(report: AnalysisReport | null) {
  mockedUseProjectContext.mockReturnValue({
    project: null,
    report,
    loading: false,
    onAnalyze: async () => {},
  });
}

describe('ComponentsView', () => {
  it('renders component list with names and scores', () => {
    setMockReport(mockReport);
    render(<ComponentsView />);

    // Component names appear in heatmap, table name column, and table path column
    expect(screen.getAllByText('auth-service').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('api-gateway').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('7.8')).toBeInTheDocument();
    expect(screen.getByText('4.2')).toBeInTheDocument();
  });

  it('renders the heatmap section', () => {
    setMockReport(mockReport);
    render(<ComponentsView />);

    expect(screen.getByText('Component x Dimension Heatmap')).toBeInTheDocument();
    expect(screen.getByText('Component Details')).toBeInTheDocument();
  });

  it('renders severity badges derived from composite score', () => {
    setMockReport(mockReport);
    render(<ComponentsView />);

    // auth-service score 7.8 => high, api-gateway score 4.2 => medium
    // "High" appears in the SeverityBadge and also in the heatmap legend
    // "Medium" appears in the SeverityBadge and also in the heatmap legend
    expect(screen.getAllByText('High').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('Medium').length).toBeGreaterThanOrEqual(1);
  });

  it('shows systemic risk indicators', () => {
    setMockReport(mockReport);
    render(<ComponentsView />);

    expect(
      screen.getByText('Systemic risk: 3+ dimensions above 7'),
    ).toBeInTheDocument();
  });

  it('renders "None" for components without systemic risks', () => {
    setMockReport(mockReport);
    render(<ComponentsView />);

    expect(screen.getByText('None')).toBeInTheDocument();
  });

  it('sorts components by score by default (descending)', () => {
    setMockReport(mockReport);
    render(<ComponentsView />);

    const rows = screen.getAllByRole('row');
    // First data row (after header) should be auth-service (highest score)
    // rows[0] is the heatmap header, rows[1..2] heatmap data, then component table
    const cells = rows.filter((row) => row.textContent?.includes('auth-service') || row.textContent?.includes('api-gateway'));
    expect(cells[0].textContent).toContain('auth-service');
    expect(cells[1].textContent).toContain('api-gateway');
  });

  it('toggles sort when clicking score column header', async () => {
    setMockReport(mockReport);
    const user = userEvent.setup();
    render(<ComponentsView />);

    // Click the "Score" column header to toggle sort direction (default is desc)
    const scoreHeader = screen.getByText('Score');
    await user.click(scoreHeader);

    // After toggling to ascending, lower score should be first
    const rows = screen.getAllByRole('row');
    const dataRows = rows.filter(
      (row) => row.textContent?.includes('auth-service') || row.textContent?.includes('api-gateway'),
    );
    expect(dataRows.length).toBeGreaterThanOrEqual(2);
    // In ascending order, api-gateway (4.2) should come before auth-service (7.8)
    expect(dataRows[0].textContent).toContain('api-gateway');
    expect(dataRows[1].textContent).toContain('auth-service');
  });

  it('renders dimension keys in heatmap columns', () => {
    setMockReport(mockReport);
    render(<ComponentsView />);

    // Dimension keys are rendered with underscores replaced by spaces
    expect(screen.getByText('code complexity')).toBeInTheDocument();
    expect(screen.getByText('code churn')).toBeInTheDocument();
    expect(screen.getByText('test coverage')).toBeInTheDocument();
  });

  it('handles empty components', () => {
    setMockReport({ ...mockReport, components: [] });
    render(<ComponentsView />);

    expect(
      screen.getByText('No component data available. Run an analysis first.'),
    ).toBeInTheDocument();
  });

  it('handles null report', () => {
    setMockReport(null);
    render(<ComponentsView />);

    expect(
      screen.getByText('No component data available. Run an analysis first.'),
    ).toBeInTheDocument();
  });
});
