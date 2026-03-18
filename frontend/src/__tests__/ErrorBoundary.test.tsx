import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';
import ErrorBoundary from '../components/ErrorBoundary';

// A component that throws an error when rendered
function ThrowingComponent({ shouldThrow = true }: { shouldThrow?: boolean }) {
  if (shouldThrow) {
    throw new Error('Test error');
  }
  return <div>Child content rendered successfully</div>;
}

describe('ErrorBoundary', () => {
  // Suppress console.error for expected error boundary logs
  const originalError = console.error;
  beforeEach(() => {
    console.error = vi.fn();
  });
  afterEach(() => {
    console.error = originalError;
  });

  it('renders children normally when no error occurs', () => {
    render(
      <ErrorBoundary>
        <div>Hello World</div>
      </ErrorBoundary>,
    );

    expect(screen.getByText('Hello World')).toBeInTheDocument();
  });

  it('catches errors and shows default fallback UI', () => {
    render(
      <ErrorBoundary>
        <ThrowingComponent />
      </ErrorBoundary>,
    );

    expect(screen.queryByText('Child content rendered successfully')).not.toBeInTheDocument();
    expect(screen.getByText('Try again')).toBeInTheDocument();
  });

  it('catches errors and shows custom fallback when provided', () => {
    render(
      <ErrorBoundary fallback={<div>Custom error fallback</div>}>
        <ThrowingComponent />
      </ErrorBoundary>,
    );

    expect(screen.queryByText('Child content rendered successfully')).not.toBeInTheDocument();
    expect(screen.getByText('Custom error fallback')).toBeInTheDocument();
  });

  it('"Try again" button resets error state', async () => {
    // Use a stateful wrapper to control whether the child throws
    let shouldThrow = true;

    function ConditionalThrower() {
      if (shouldThrow) {
        throw new Error('Test error');
      }
      return <div>Recovered successfully</div>;
    }

    const { unmount } = render(
      <ErrorBoundary>
        <ConditionalThrower />
      </ErrorBoundary>,
    );

    // Error boundary should be showing fallback
    expect(screen.getByText('Try again')).toBeInTheDocument();

    // Fix the error condition
    shouldThrow = false;

    // Click "Try again"
    const user = userEvent.setup();
    await user.click(screen.getByText('Try again'));

    // After reset, the component should re-render without throwing
    expect(screen.getByText('Recovered successfully')).toBeInTheDocument();
    expect(screen.queryByText('Try again')).not.toBeInTheDocument();

    unmount();
  });
});
