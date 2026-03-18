/**
 * Shared color/severity utilities for risk scores.
 *
 * Scores are 0-10 where lower is better (less risk).
 */

/** Returns a hex color string for a given risk score (green = low risk, red = high risk). */
export function getScoreColor(score: number): string {
  if (score >= 7) return '#ef4444';
  if (score >= 4) return '#eab308';
  return '#22c55e';
}

/** Returns a Tailwind background color class for a given risk score. */
export function getScoreBgColor(score: number): string {
  if (score >= 8) return 'bg-red-500/70';
  if (score >= 6) return 'bg-orange-500/50';
  if (score >= 4) return 'bg-yellow-500/40';
  if (score >= 2) return 'bg-green-500/20';
  return 'bg-navy-700/40';
}
