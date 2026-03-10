export type Severity = 'critical' | 'high' | 'medium' | 'low' | 'minimal';

export type Scenario = 'default' | 'pre-release' | 'onboarding' | 'tech-debt' | 'post-incident';

export interface Project {
  id: string;
  name: string;
  scenario: Scenario;
  created_at: string;
  updated_at: string;
  last_analysis_at: string | null;
  health_score: number | null;
  status: 'pending' | 'analyzing' | 'completed' | 'failed';
}

export interface AnalysisReport {
  project_id: string;
  generated_at: string;
  health_score: number;
  dimensions: DimensionScore[];
  components: ComponentRisk[];
  hotspots: FileHotspot[];
  trends: FeatureBugTrend[];
  summary: string;
}

export interface DimensionScore {
  id: string;
  name: string;
  score: number;
  severity: Severity;
  weight: number;
  evidence: string[];
  description: string;
}

export interface ComponentRisk {
  name: string;
  path: string;
  composite_score: number;
  severity: Severity;
  file_count: number;
  dimension_scores: Record<string, number>;
  systemic_risks: string[];
}

export interface FileHotspot {
  file_path: string;
  risk_score: number;
  severity: Severity;
  churn_rate: number;
  complexity: number;
  bug_correlation: number;
  ownership_fragmentation: number;
  effort_estimate: 'small' | 'medium' | 'large';
  indicators: string[];
}

export interface FeatureBugTrend {
  period: string;
  features: number;
  bugs: number;
  refactors: number;
  bug_fix_ratio: number;
  total_commits: number;
}

export interface CreateProjectPayload {
  name: string;
  scenario: Scenario;
}

export interface AnalyzePayload {
  git_log: File;
  manifests?: File[];
  scenario?: Scenario;
}
