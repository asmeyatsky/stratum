import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import SeverityBadge from '../components/SeverityBadge';

describe('SeverityBadge', () => {
  it('renders critical severity', () => {
    render(<SeverityBadge severity="critical" />);
    expect(screen.getByText('Critical')).toBeInTheDocument();
  });

  it('renders high severity', () => {
    render(<SeverityBadge severity="high" />);
    expect(screen.getByText('High')).toBeInTheDocument();
  });

  it('renders medium severity', () => {
    render(<SeverityBadge severity="medium" />);
    expect(screen.getByText('Medium')).toBeInTheDocument();
  });

  it('renders low severity', () => {
    render(<SeverityBadge severity="low" />);
    expect(screen.getByText('Low')).toBeInTheDocument();
  });

  it('renders minimal severity', () => {
    render(<SeverityBadge severity="minimal" />);
    expect(screen.getByText('Minimal')).toBeInTheDocument();
  });

  it('applies custom className', () => {
    const { container } = render(
      <SeverityBadge severity="high" className="extra-class" />,
    );
    expect(container.firstChild).toHaveClass('extra-class');
  });
});
