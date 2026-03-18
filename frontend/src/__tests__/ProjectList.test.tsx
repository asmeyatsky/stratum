import { render, screen, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { describe, it, expect } from 'vitest';
import ProjectList from '../pages/ProjectList';

function renderWithRouter(ui: React.ReactElement) {
  return render(<BrowserRouter>{ui}</BrowserRouter>);
}

describe('ProjectList', () => {
  it('renders the projects heading', () => {
    renderWithRouter(<ProjectList />);
    expect(screen.getByText('Projects')).toBeInTheDocument();
  });

  it('renders project list from mock data', async () => {
    renderWithRouter(<ProjectList />);

    await waitFor(() => {
      expect(screen.getByText('Backend API')).toBeInTheDocument();
    });

    await waitFor(() => {
      expect(screen.getByText('Frontend App')).toBeInTheDocument();
    });
  });

  it('shows scenario badges', async () => {
    renderWithRouter(<ProjectList />);

    await waitFor(() => {
      expect(screen.getByText('cto_onboarding')).toBeInTheDocument();
    });

    await waitFor(() => {
      expect(screen.getByText('ma_due_diligence')).toBeInTheDocument();
    });
  });

  it('shows completed status for projects', async () => {
    renderWithRouter(<ProjectList />);

    await waitFor(() => {
      const completedBadges = screen.getAllByText('completed');
      expect(completedBadges.length).toBe(2);
    });
  });

  it('shows the New Project button', () => {
    renderWithRouter(<ProjectList />);
    expect(screen.getByText('New Project')).toBeInTheDocument();
  });
});
