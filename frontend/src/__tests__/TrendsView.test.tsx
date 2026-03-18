import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import type { AnalysisReport, FeatureBugTrend } from '../types';

// Mock recharts to avoid jsdom rendering issues
vi.mock('recharts', () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="responsive-container">{children}</div>
  ),
  AreaChart: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="area-chart">{children}</div>
  ),
  LineChart: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="line-chart">{children}</div>
  ),
  Area: () => <div />,
  Line: () => <div />,
  XAxis: () => <div />,
  YAxis: () => <div />,
  CartesianGrid: () => <div />,
  Tooltip: () => <div />,
  Legend: () => <div />,
}));

const mockTrends: FeatureBugTrend[] = [
  { period: '2026-01-01', features: 12, bugs: 5, refactors: 3, bug_fix_ratio: 0.25, total_commits: 20 },
  { period: '2026-01-15', features: 8, bugs: 7, refactors: 2, bug_fix_ratio: 0.41, total_commits: 17 },
  { period: '2026-02-01', features: 15, bugs: 4, refactors: 6, bug_fix_ratio: 0.16, total_commits: 25 },
];

const mockReport: AnalysisReport = {
  project_id: 'proj-1',
  generated_at: '2026-03-01T14:30:00Z',
  health_score: 7.2,
  dimensions: [],
  components: [],
  hotspots: [],
  trends: mockTrends,
  summary: 'Test summary',
};

// Mock the ProjectDetail context
vi.mock('../pages/ProjectDetail', () => ({
  useProjectContext: vi.fn(),
}));

import { useProjectContext } from '../pages/ProjectDetail';
import TrendsView from '../pages/report/TrendsView';

const mockedUseProjectContext = vi.mocked(useProjectContext);

function setMockReport(report: AnalysisReport | null) {
  mockedUseProjectContext.mockReturnValue({
    project: null,
    report,
    loading: false,
    onAnalyze: async () => {},
  });
}

describe('TrendsView', () => {
  it('renders trend summary cards with totals', () => {
    setMockReport(mockReport);
    render(<TrendsView />);

    // Features total: 12 + 8 + 15 = 35
    expect(screen.getByText('35')).toBeInTheDocument();
    // Bugs total: 5 + 7 + 4 = 16
    expect(screen.getByText('16')).toBeInTheDocument();
    // Refactors total: 3 + 2 + 6 = 11
    expect(screen.getByText('11')).toBeInTheDocument();
  });

  it('renders summary card labels', () => {
    setMockReport(mockReport);
    render(<TrendsView />);

    expect(screen.getByText('Features')).toBeInTheDocument();
    expect(screen.getByText('Bug Fixes')).toBeInTheDocument();
    expect(screen.getByText('Refactors')).toBeInTheDocument();
    expect(screen.getByText('Avg Bug Ratio')).toBeInTheDocument();
  });

  it('renders average bug ratio percentage', () => {
    setMockReport(mockReport);
    render(<TrendsView />);

    // Avg bug ratio: (0.25 + 0.41 + 0.16) / 3 = 0.2733... => 27%
    expect(screen.getByText('27%')).toBeInTheDocument();
  });

  it('renders chart containers', () => {
    setMockReport(mockReport);
    render(<TrendsView />);

    expect(screen.getByText('Commit Activity Over Time')).toBeInTheDocument();
    expect(screen.getByText('Bug-Fix Ratio Trend')).toBeInTheDocument();
    expect(screen.getAllByTestId('responsive-container')).toHaveLength(2);
  });

  it('renders time range selector buttons', () => {
    setMockReport(mockReport);
    render(<TrendsView />);

    expect(screen.getByText('30d')).toBeInTheDocument();
    expect(screen.getByText('90d')).toBeInTheDocument();
    expect(screen.getByText('180d')).toBeInTheDocument();
  });

  it('renders the heading', () => {
    setMockReport(mockReport);
    render(<TrendsView />);

    expect(screen.getByText('Feature / Bug Trends')).toBeInTheDocument();
  });

  it('handles empty trends', () => {
    setMockReport({ ...mockReport, trends: [] });
    render(<TrendsView />);

    expect(
      screen.getByText('No trend data available. Run an analysis first.'),
    ).toBeInTheDocument();
  });

  it('handles null report', () => {
    setMockReport(null);
    render(<TrendsView />);

    expect(
      screen.getByText('No trend data available. Run an analysis first.'),
    ).toBeInTheDocument();
  });
});
