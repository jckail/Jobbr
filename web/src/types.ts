export type Stage = "saved" | "applied" | "screen" | "interview" | "offer" | "rejected" | "withdrawn";
export const STAGES: Stage[] = ["saved", "applied", "screen", "interview", "offer", "rejected", "withdrawn"];
export const BOARD_STAGES: Stage[] = ["saved", "applied", "screen", "interview", "offer"];
export type Remote = "remote" | "hybrid" | "onsite" | "unknown";

export interface Match {
  score: number;
  breakdown: Record<"skills" | "seniority" | "location" | "comp", { score: number; weight: number }>;
  matched_skills: string[];
  missing_skills: string[];
  rationale: string | null;
}
export interface Job {
  id: number;
  title: string;
  url: string | null;
  external_identity?: { provider: DiscoveryProvider; board: string; posting_id: string } | null;
  company: { id: number; name: string; domain: string | null; industry: string | null };
  seniority: string;
  employment_type: string | null;
  remote_policy: Remote;
  locations: string[];
  comp_min: number | null;
  comp_max: number | null;
  comp_currency: string;
  years_experience_min: number | null;
  summary: string | null;
  responsibilities: string[];
  qualifications: string[];
  skills: string[];
  nice_to_have: string[];
  benefits: string[];
  ai_take: string | null;
  first_seen_at: string;
  match: Match | null;
  application: { stage: Stage; notes: string; applied_at?: string | null; next_step_at?: string | null };
  raw_text?: string;
  extractions?: { id: number; method: string; model: string | null; cost_usd: number; latency_ms: number; error: string | null; created_at: string }[];
  events?: { id: number; from_stage: Stage | null; to_stage: Stage; note: string | null; at: string }[];
}
export interface AvailabilityObservation {
  state: "available" | "unavailable" | "unknown";
  checked_at: string;
  source_url: string | null;
  reason: "listed" | "absent_complete_board" | "incomplete_snapshot" | "upstream_unavailable" | "invalid_data" | "unsupported_identity";
}
export interface ProfileSnapshot {
  name: string;
  headline: string | null;
  resume_text: string;
  skills: string[];
  years_experience: number | null;
  seniority: string;
  target_titles: string[];
  locations: string[];
  remote_pref: Remote;
  min_comp: number | null;
}
export interface Profile extends ProfileSnapshot {
  active_revision_id: number;
  revision_version: number;
}
export interface ProfileRevisionSummary {
  id: number;
  saved_at: string;
  source: "saved" | "legacy";
  active: boolean;
}
export interface ProfileRevision extends ProfileRevisionSummary {
  snapshot: ProfileSnapshot;
}
export interface Stats {
  totals: { jobs: number; companies: number; avg_score: number | null; median_comp: number | null; ai_cost_usd: number | null };
  stages: Record<Stage, number>;
  skill_demand: { skill: string; jobs: number; have: boolean }[];
  added_per_day: { day: string; count: number }[];
  score_buckets: { label: string; count: number }[];
  top_matches: { id: number; title: string; company: string; score: number | null }[];
}
export type AIProvider = "openai" | "anthropic";
export interface Config { version: string; llm_enabled: boolean; model: string | null; ai_provider: AIProvider; ai_provider_label: string; ai_model: string; write_protected: boolean; private_instance: boolean; auth_enabled: boolean; seed_demo: boolean; career_enabled: boolean; cost_estimates_available: boolean }

export interface AuthSession {
  enabled: boolean;
  ready: boolean;
  reason: string | null;
  authenticated: boolean;
  user: { subject: string; name: string | null; email: string | null } | null;
  csrf_token: string | null;
  login_url: string | null;
}
export interface ExtensionPairing {
  request_id: string;
  challenge: string;
  extension_id: string;
  destination: string;
  comparison_code: string;
  expires_at: string | null;
  status: "pending" | "approved";
  scope: "jobs:capture";
  capture_limit: number;
  token_ttl_seconds: number;
  ai_provider: AIProvider;
  ai_model: string;
  llm_enabled: boolean;
}
export interface ExtensionGrant {
  grant_id: string;
  extension_id: string;
  destination: string;
  expires_at: string;
  captures_remaining: number;
  busy: boolean;
  revoked: boolean;
}
export type CareerKind = "cover_letter" | "interview_prep";
export interface CareerResult {
  kind: CareerKind;
  provider?: AIProvider;
  generated_at?: string;
  model: string;
  input_tokens: number;
  output_tokens: number;
  requires_review: boolean;
  draft: {
    cover_letter: string | null;
    interview_questions: { question: string; answer_outline: string[]; evidence_quotes: string[] }[];
    strengths: string[];
    gaps: string[];
    questions_to_ask: string[];
    evidence_quotes: string[];
    review_notes: string[];
  };
}
export interface SavedCareerDraft {
  id: number;
  job_id: number;
  created_at: string;
  source_fingerprint: string;
  result: CareerResult;
}
export interface TailoringDraft {
  resume_text: string;
  changes: { description: string; evidence_quotes: string[] }[];
  gaps: string[];
  review_notes: string[];
}
export interface TailoringResult {
  kind: "resume_tailoring";
  receipt_id: string;
  source: {
    revision_id: number;
    revision_fingerprint: string;
    job_id: number;
    job_fingerprint: string;
    input_fingerprint: string;
  };
  provider: AIProvider;
  model: string;
  input_tokens: number;
  output_tokens: number;
  generated_at: string;
  requires_review: boolean;
  draft: TailoringDraft;
}
export interface SavedTailoringDraft extends TailoringResult {
  id: number;
  created_at: string;
  user_edited: boolean;
}
export interface ResumePreview { text: string; page_count: number; filename: string }

export type DiscoveryProvider = "greenhouse" | "lever";
export interface DiscoveryPosting {
  source_id: string;
  title: string;
  company: string | null;
  location: string | null;
  url: string;
  raw_text: string;
  remote_policy: string;
}
export interface DiscoverySnapshot {
  provider: DiscoveryProvider;
  board: string;
  source_url: string;
  fetched_at: string;
  postings: DiscoveryPosting[];
  truncated: boolean;
  skipped_unsafe_links: number;
}
