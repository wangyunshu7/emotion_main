import type { components } from "./generated";
export type User = components["schemas"]["UserOut"];
export type Journal = components["schemas"]["JournalOut"];
export type JournalSummary = components["schemas"]["JournalSummary"];
export type JournalCreate = components["schemas"]["JournalCreate"];
export type Tag = components["schemas"]["Tag"];
export type Analysis = components["schemas"]["AnalysisOut"];
export type Factor = components["schemas"]["FactorOut"];
export type Job = components["schemas"]["JobOut"];
export type Insights = components["schemas"]["InsightsOut"];
export type Review = components["schemas"]["ReviewOut"];
export type Activity = components["schemas"]["ActivityOut"];
export type ActivitySummary = components["schemas"]["ActivitySummary"];
export type CareSession = components["schemas"]["CareOut"];
export type Recommendation = components["schemas"]["RecommendationOut"];
export type Page<T> = {
  items: T[];
  page: number;
  page_size: number;
  total: number;
};
export type Metadata = components["schemas"]["MetadataOut"];
export type SessionInfo = { user: User | null; csrf_token: string };
export type Receipt =
  | { job_id: string; status: string; poll_after_ms?: number }
  | { analysis_id: string; reused: true }
  | { review_id: string; reused: true };
