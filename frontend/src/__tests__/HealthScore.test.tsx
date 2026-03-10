import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import HealthScore from '../components/HealthScore';

describe('HealthScore', () => {
  it('renders with score 0', () => {
    render(<HealthScore score={0} />);
    expect(screen.getByText('0.0')).toBeInTheDocument();
    expect(screen.getByText('Critical')).toBeInTheDocument();
  });

  it('renders with score 5', () => {
    render(<HealthScore score={5} />);
    expect(screen.getByText('5.0')).toBeInTheDocument();
    expect(screen.getByText('At risk')).toBeInTheDocument();
  });

  it('renders with score 10', () => {
    render(<HealthScore score={10} />);
    expect(screen.getByText('10.0')).toBeInTheDocument();
    expect(screen.getByText('Healthy')).toBeInTheDocument();
  });

  it('renders with null score', () => {
    render(<HealthScore score={null} />);
    expect(screen.getByText('--')).toBeInTheDocument();
    expect(screen.getByText('No data')).toBeInTheDocument();
  });

  it('hides label when showLabel is false', () => {
    render(<HealthScore score={7} showLabel={false} />);
    expect(screen.getByText('7.0')).toBeInTheDocument();
    expect(screen.queryByText('Healthy')).not.toBeInTheDocument();
  });
});
