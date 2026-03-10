import { render, screen, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { describe, it, expect } from 'vitest';
import Dashboard from '../pages/Dashboard';

function renderWithRouter(ui: React.ReactElement) {
  return render(<BrowserRouter>{ui}</BrowserRouter>);
}

describe('Dashboard', () => {
  it('renders the dashboard heading', () => {
    renderWithRouter(<Dashboard />);
    expect(screen.getByText('Dashboard')).toBeInTheDocument();
  });

  it('shows loading skeleton then loads content', async () => {
    renderWithRouter(<Dashboard />);

    // Initially shows skeleton (loading state)
    expect(
      screen.getByText('Overview of your codebase health and active projects'),
    ).toBeInTheDocument();

    // After data loads, shows project count and stats
    await waitFor(() => {
      expect(screen.getByText('2')).toBeInTheDocument();
    });
  });

  it('shows projects section after loading', async () => {
    renderWithRouter(<Dashboard />);

    await waitFor(() => {
      expect(screen.getByText('Backend API')).toBeInTheDocument();
    });

    await waitFor(() => {
      // Frontend App may appear in both "Top Risks" and "Recent Projects"
      const items = screen.getAllByText('Frontend App');
      expect(items.length).toBeGreaterThanOrEqual(1);
    });
  });

  it('displays at-risk projects', async () => {
    renderWithRouter(<Dashboard />);

    // Frontend App has score 5.4, which is < 7 so it's at risk
    await waitFor(() => {
      expect(screen.getByText('5.4')).toBeInTheDocument();
    });
  });
});
