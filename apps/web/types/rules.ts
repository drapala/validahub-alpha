export interface RuleField {
  name: string;
  type: "string" | "number" | "boolean" | "date" | "email" | "url";
  required: boolean;
  description?: string;
}

export interface ValidationRule {
  id: string;
  field: string;
  type: "required" | "format" | "range" | "pattern" | "custom";
  condition: string;
  message: string;
  severity: "error" | "warning" | "info";
  enabled: boolean;
}

export interface RuleSet {
  id: string;
  name: string;
  description?: string;
  version: string;
  marketplace?: string;
  fields: RuleField[];
  rules: ValidationRule[];
  metadata: {
    created_at: string;
    updated_at: string;
    created_by: string;
    tags: string[];
  };
}

export interface RuleTemplate {
  id: string;
  name: string;
  description: string;
  category: string;
  marketplace: string;
  version: string;
  template: Partial<RuleSet>;
  downloads: number;
  rating: number;
  author: string;
}

export interface RuleVersion {
  version: string;
  changelog: string;
  published_at: string;
  status: "draft" | "published" | "deprecated";
  compatibility: string[];
}

export interface RuleAnalytics {
  rule_id: string;
  rule_name: string;
  period: "hour" | "day" | "week" | "month";
  metrics: {
    validations: number;
    errors: number;
    warnings: number;
    success_rate: number;
    avg_processing_time: number;
    total_rows_processed: number;
  };
  timestamp: string;
}

export interface ValidationResult {
  job_id: string;
  rule_id: string;
  total_rows: number;
  processed_rows: number;
  errors: ValidationError[];
  warnings: ValidationWarning[];
  status: "running" | "completed" | "failed";
  processing_time?: number;
}

export interface ValidationError {
  row: number;
  field: string;
  rule_id: string;
  message: string;
  severity: "error" | "warning";
  suggested_fix?: string;
}

export interface ValidationWarning {
  row: number;
  field: string;
  rule_id: string;
  message: string;
  impact: "low" | "medium" | "high";
}

export interface SSEMessage {
  id: string;
  event: string;
  data: any;
  timestamp: string;
}

export interface RuleEngineStatus {
  connected: boolean;
  last_heartbeat: string;
  active_validations: number;
  queue_size: number;
  processing_rate: number;
}

export interface SmartSuggestion {
  id: string;
  type: "rule_improvement" | "field_mapping" | "performance_optimization";
  rule_id: string;
  title: string;
  description: string;
  impact: "low" | "medium" | "high";
  confidence: number;
  suggested_changes: any;
  auto_applicable: boolean;
  created_at: string;
}

export interface RuleBuilderItem {
  id: string;
  type: "field" | "condition" | "action" | "group";
  label: string;
  config: any;
  position: { x: number; y: number };
  connections: string[];
}