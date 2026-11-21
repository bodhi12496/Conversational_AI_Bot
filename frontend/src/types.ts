export interface Project { id: string; name: string; head: number; active: number | null }
export interface Column { name: string; source_name: string; dtype: string; description: string; null_count: number; distinct_count: number; candidate_key: boolean; sensitive: boolean }
export interface Metric { name: string; description: string; expression: string; aggregation: string; unit: string; confirmed: boolean; filters: unknown[] }
export interface View { id: string; name: string; grain: string; columns: Column[]; metrics: Metric[]; filters: unknown[] }
export interface Model { views: View[]; selected_views: string[]; relationships: unknown[]; fiscal_year_start_month: number }
export interface Validation { valid: boolean; errors: string[]; warnings: string[]; checks: string[] }
export interface Instructions { sample_prompts: string[]; orchestration: string[]; response: string[]; [key: string]: unknown }
export interface State { project: Project; model: Model; instructions: Instructions; validation: Validation; versions: { number: number; reason: string; created_at: string }[]; datasets: { view_id: string; row_count: number; loaded_at: string }[]; regressions: { id: string; name: string }[]; recent_runs: { id: string; version: number; question: string }[] }
export interface Proposal { id?: string; clarification?: string; diff?: string; validation?: Validation; changes?: { summary: string } }
export interface Result { id?: string; clarification?: string; version: number; columns?: string[]; rows?: Record<string, unknown>[]; summary?: string; warnings?: string[]; evidence?: unknown[]; queries?: unknown[]; plan?: unknown; truncated?: boolean }
