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
export interface Profile {
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
export interface Stats {
  totals: { jobs: number; companies: number; avg_score: number | null; median_comp: number | null; ai_cost_usd: number };
  stages: Record<Stage, number>;
  skill_demand: { skill: string; jobs: number; have: boolean }[];
  added_per_day: { day: string; count: number }[];
  score_buckets: { label: string; count: number }[];
  top_matches: { id: number; title: string; company: string; score: number | null }[];
}
export interface Config { version: string; llm_enabled: boolean; model: string | null; write_protected: boolean }
