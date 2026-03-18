import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';
import type { AnalysisReport, DimensionScore } from '../types';

// Mock recharts to avoid jsdom rendering issues
vi.mock('recharts', () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="responsive-container">{children}</div>
  ),
  BarChart: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="bar-chart">{children}</div>
  ),
  Bar: () => <div />,
  XAxis: () => <div />,
  YAxis: () => <div />,
  CartesianGrid: () => <div />,
  Tooltip: () => <div />,
  Cell: () => <div />,
}));

const mockDimensions: DimensionScore[] = [
  {
    id: 'code_complexity',
    name: 'Code Complexity',
    score: 6.5,
    severity: 'medium',
    weight: 1,
    evidence: ['Average cyclomatic complexity: 12.3'],
    description: 'Code Complexity',
  },
  {
    id: 'test_coverage',
    name: 'Test Coverage',
    score: 8.1,
    severity: 'low',
    weight: 1,
    evidence: ['Overall coverage: 81%'],
    description: 'Test Coverage',
  },
  {
    id: 'code_churn',
    name: 'Code Churn',
    score: 3.2,
    severity: 'high',
    weight: 1,
    evidence: ['High churn in auth module'],
    description: 'Code Churn',
  },
];

const mockReport: AnalysisReport = {
  project_id: 'proj-1',
  generated_at: '2026-03-01T14:30:00Z',
  health_score: 7.2,
  dimensions: mockDimensions,
  components: [],
  hotspots: [],
  trends: [],
  summary: 'Test summary',
};

// Mock the ProjectDetail context
vi.mock('../pages/ProjectDetail', () => ({
  useProjectContext: vi.fn(),
}));

import { useProjectContext } from '../pages/ProjectDetail';
import DimensionsView from '../pages/report/DimensionsView';

const mockedUseProjectContext = vi.mocked(useProjectContext);

function setMockReport(report: AnalysisReport | null) {
  mockedUseProjectContext.mockReturnValue({
    project: null,
    report,
    loading: false,
    onAnalyze: async () => {},
  });
}

describe('DimensionsView', () => {
  it('renders dimension cards with scores', () => {
    setMockReport(mockReport);
    render(<DimensionsView />);

    // Each dimension name appears twice (once as name, once as description)
    expect(screen.getAllByText('Code Complexity')).toHaveLength(2);
    expect(screen.getAllByText('Test Coverage')).toHaveLength(2);
    expect(screen.getAllByText('Code Churn')).toHaveLength(2);

    expect(screen.getByText('6.5')).toBeInTheDocument();
    expect(screen.getByText('8.1')).toBeInTheDocument();
    expect(screen.getByText('3.2')).toBeInTheDocument();
  });

  it('renders severity badges for each dimension', () => {
    setMockReport(mockReport);
    render(<DimensionsView />);

    expect(screen.getByText('Medium')).toBeInTheDocument();
    expect(screen.getByText('Low')).toBeInTheDocument();
    expect(screen.getByText('High')).toBeInTheDocument();
  });

  it('renders the bar chart container', () => {
    setMockReport(mockReport);
    render(<DimensionsView />);

    expect(screen.getByText('Dimension Scores')).toBeInTheDocument();
    expect(screen.getByTestId('responsive-container')).toBeInTheDocument();
  });

  it('expands dimension row to show evidence on click', async () => {
    setMockReport(mockReport);
    const user = userEvent.setup();
    render(<DimensionsView />);

    // Evidence should not be visible initially
    expect(screen.queryByText('Average cyclomatic complexity: 12.3')).not.toBeInTheDocument();

    // Click on a dimension row to expand it (first match is the name span)
    const complexityButton = screen.getAllByText('Code Complexity')[0].closest('button')!;
    await user.click(complexityButton);

    // Evidence should now be visible
    expect(screen.getByText('Average cyclomatic complexity: 12.3')).toBeInTheDocument();
    expect(screen.getByText('Evidence')).toBeInTheDocument();
  });

  it('handles empty dimensions array', () => {
    setMockReport({ ...mockReport, dimensions: [] });
    render(<DimensionsView />);

    expect(
      screen.getByText('No dimension data available. Run an analysis first.'),
    ).toBeInTheDocument();
  });

  it('handles null report', () => {
    setMockReport(null);
    render(<DimensionsView />);

    expect(
      screen.getByText('No dimension data available. Run an analysis first.'),
    ).toBeInTheDocument();
  });
});
