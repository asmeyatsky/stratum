import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';
import type { AnalysisReport, FileHotspot } from '../types';

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
    indicators: ['churn', 'complexity', 'bug_density', 'ownership'],
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
    indicators: ['churn', 'complexity', 'bug_density'],
  },
];

const mockReport: AnalysisReport = {
  project_id: 'proj-1',
  generated_at: '2026-03-01T14:30:00Z',
  health_score: 7.2,
  dimensions: [],
  components: [],
  hotspots: mockHotspots,
  trends: [],
  summary: 'Test summary',
};

// Mock the ProjectDetail context
vi.mock('../pages/ProjectDetail', () => ({
  useProjectContext: vi.fn(),
}));

import { useProjectContext } from '../pages/ProjectDetail';
import HotspotsView from '../pages/report/HotspotsView';

const mockedUseProjectContext = vi.mocked(useProjectContext);

function setMockReport(report: AnalysisReport | null) {
  mockedUseProjectContext.mockReturnValue({
    project: null,
    report,
    loading: false,
    onAnalyze: async () => {},
  });
}

describe('HotspotsView', () => {
  it('renders hotspot table with file paths', () => {
    setMockReport(mockReport);
    render(<HotspotsView />);

    expect(screen.getByText('src/services/auth/handler.ts')).toBeInTheDocument();
    expect(screen.getByText('src/gateway/router.ts')).toBeInTheDocument();
  });

  it('renders risk scores', () => {
    setMockReport(mockReport);
    render(<HotspotsView />);

    expect(screen.getByText('8.9')).toBeInTheDocument();
    expect(screen.getByText('5.4')).toBeInTheDocument();
  });

  it('renders severity badges', () => {
    setMockReport(mockReport);
    render(<HotspotsView />);

    expect(screen.getByText('Critical')).toBeInTheDocument();
    expect(screen.getByText('Medium')).toBeInTheDocument();
  });

  it('renders effort estimates', () => {
    setMockReport(mockReport);
    render(<HotspotsView />);

    expect(screen.getByText('large')).toBeInTheDocument();
    expect(screen.getByText('medium')).toBeInTheDocument();
  });

  it('renders indicator values', () => {
    setMockReport(mockReport);
    render(<HotspotsView />);

    // Churn rate values
    expect(screen.getByText('9.2')).toBeInTheDocument();
    expect(screen.getByText('4.1')).toBeInTheDocument();

    // Complexity values
    expect(screen.getByText('7.8')).toBeInTheDocument();
    expect(screen.getByText('6.2')).toBeInTheDocument();
  });

  it('displays the file count', () => {
    setMockReport(mockReport);
    render(<HotspotsView />);

    expect(screen.getByText('2 files analyzed')).toBeInTheDocument();
  });

  it('renders indicator tags', () => {
    setMockReport(mockReport);
    render(<HotspotsView />);

    // Indicator tags appear for both hotspots, and some names also appear in column headers
    // Use getAllByText for all indicator names
    expect(screen.getAllByText('churn').length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText('complexity').length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText('bug_density').length).toBe(2);
    // First hotspot has 4 indicators with only 3 shown, so "+1" overflow appears
    expect(screen.getByText('+1')).toBeInTheDocument();
  });

  it('sorts by risk score descending by default', () => {
    setMockReport(mockReport);
    render(<HotspotsView />);

    const rows = screen.getAllByRole('row');
    // Skip header row, first data row should be highest risk
    const dataRows = rows.slice(1);
    expect(dataRows[0].textContent).toContain('src/services/auth/handler.ts');
    expect(dataRows[1].textContent).toContain('src/gateway/router.ts');
  });

  it('toggles sort direction when clicking same column header', async () => {
    setMockReport(mockReport);
    const user = userEvent.setup();
    render(<HotspotsView />);

    // Click Risk header to toggle sort direction (default is desc, clicking again -> asc)
    const riskHeader = screen.getByText('Risk');
    await user.click(riskHeader);

    const rows = screen.getAllByRole('row');
    const dataRows = rows.slice(1);
    // After toggling to ascending, lower risk should be first
    expect(dataRows[0].textContent).toContain('src/gateway/router.ts');
    expect(dataRows[1].textContent).toContain('src/services/auth/handler.ts');
  });

  it('sorts by a different column when clicking its header', async () => {
    setMockReport(mockReport);
    const user = userEvent.setup();
    render(<HotspotsView />);

    // Click Complexity header to sort by complexity
    const complexityHeader = screen.getByText('Complexity');
    await user.click(complexityHeader);

    const rows = screen.getAllByRole('row');
    const dataRows = rows.slice(1);
    // Sorted by complexity desc: 7.8 > 6.2
    expect(dataRows[0].textContent).toContain('src/services/auth/handler.ts');
    expect(dataRows[1].textContent).toContain('src/gateway/router.ts');
  });

  it('handles empty hotspots', () => {
    setMockReport({ ...mockReport, hotspots: [] });
    render(<HotspotsView />);

    expect(
      screen.getByText('No hotspot data available. Run an analysis first.'),
    ).toBeInTheDocument();
  });

  it('handles null report', () => {
    setMockReport(null);
    render(<HotspotsView />);

    expect(
      screen.getByText('No hotspot data available. Run an analysis first.'),
    ).toBeInTheDocument();
  });
});
