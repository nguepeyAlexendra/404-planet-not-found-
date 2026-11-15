export type Maturity = "beta" | "provisional" | "validated" | "demo";

export interface Coverage { available: boolean; dates: string[]; count: number; bounds: [number, number, number, number] | null; maturities: Maturity[]; has_demo: boolean }
export interface Layer {
  key: string; label: string; group: string; product_type: string; band: string; source: string; unit: string;
  style: { rescale?: [number, number]; colormap?: string }; default_opacity: number; description: string;
  coverage: Coverage | null; tiles: string | null;
}
export interface DatasetMeta {
  id: number; source_id: string; date: string; maturity: Maturity; is_demo: boolean; processing_version: string | null;
  resolution_m: number | null; crs: string; track: number | null; orbit_direction: string | null; source_uri: string | null;
  checksum_sha256: string | null; license: string | null; provenance: Record<string, unknown> | null;
}
export interface LayerMetadata { layer: Layer; datasets: DatasetMeta[]; note: string }
export interface PixelBand { linear: number | null; db: number | null; status: string; reason: string | null }
export interface PixelInfo {
  lon: number; lat: number; date: string; dataset_id: number; source_id: string; sensor: string; product_type: string;
  maturity: Maturity; is_demo: boolean; units: string; bands: Record<string, PixelBand>;
  interpretation: null | { class_id: number; class_key: string; label: string; hh_db: number; hv_db: number; ratio_db: number; explanation: string; ruleset_version: string; caution: string };
  series: { date: string; db: number | null }[];
}
export interface RulesetClass { key: string; label: string; color: string }
export interface Ruleset { version: string; name: string; validated: boolean; notes: string; config: { classes: Record<string, RulesetClass>; thresholds_db: Record<string, number>; explanations: Record<string, string> } }
export interface ClassShare { class_id: number; key: string; label: string; color: string; pixels: number; pct: number; area_km2: number }
export interface Classification { dataset_id: number; source_id: string; maturity: Maturity; is_demo: boolean; ruleset_version: string; ruleset_name: string; classes: ClassShare[] }
export interface Scene {
  order: number; title: string; body: string; center: [number, number]; zoom: number; layers: string[];
  date_start: string | null; date_end: string | null; annotation: string | null; figure: string | null; provenance: string; limits: string;
}
export interface StorySummary { id: number; slug: string; title: string; theme: string; synopsis: string; duration_min: number; is_example: boolean; scene_count: number }
export interface Story extends Omit<StorySummary, "scene_count"> { sources: { label: string; url: string | null }[]; scenes: Scene[] }
export interface LevelSummary { id: number; number: number; title: string; summary: string; xp: number; badge_key: string; simulator: string; unlocked: boolean; completed: boolean }
export interface QuizQuestion { id: number; order: number; text: string; options: { id: number; text: string }[] }
export interface LevelDetail { id: number; number: number; title: string; summary: string; xp: number; simulator: string; lessons: { order: number; title: string; content: string }[]; quiz: { id: number; pass_ratio: number; questions: QuizQuestion[] }; completed: boolean }
export interface GlossaryTerm { term: string; definition: string; level: number | null; example: string }
export interface AttemptResult {
  score: number; passed: boolean; correct: number; total: number; xp_awarded: number; new_badge: string | null; pass_ratio: number;
  results: { question_id: number; chosen: number; correct_option_id: number; is_correct: boolean; explanation: string }[];
}
export interface Progress {
  xp: number; completed_levels: number[]; total_levels: number; badges: { key: string; label: string; description: string }[];
  certificate_eligible: boolean; certificate_code: string | null;
}
export interface AOI { id: number; title: string; geometry: GeoJSON.Geometry; source: string; area_km2: number; created_at: string }
export interface Job<T = unknown> { job_id: string; kind: string; status: "queued" | "running" | "succeeded" | "failed" | "cancelled"; progress: number; error_message: string | null; result: T | null; method_version: string | null }
export interface TimePoint { period: string; n_observations: number; dataset_ids: number[]; valid_area_km2: number; bands: Record<string, { mean_db: number; min_db: number; max_db: number }>; classes_pct: Record<string, number> }
export interface TimeSeriesResult { series: TimePoint[]; warnings?: string[]; has_demo?: boolean }
export interface ChangeMatrixResult {
  date_a: string; date_b: string; labels: string[]; class_keys: string[]; colors: string[];
  matrix: { class_ids: number[]; counts: number[][]; area_km2: number[][]; lost_km2: number[]; gained_km2: number[]; net_km2: number[]; valid_pixels: number };
  summary_text: string; warnings: string[]; has_demo: boolean; method_version: string;
}
export interface ProjPoint { day: number; value: number; low: number; high: number }
export interface ProjectionResult {
  variable: string; history: { period: string; day: number; value: number }[];
  scenarios: Record<string, { points: ProjPoint[]; slope_per_day: number; r2: number; n: number; slope_factor: number; confidence: number }>;
  method: string; warnings?: string[]; has_demo?: boolean;
}

export interface ChangeResult {
  before: { dataset_id: number; date: string; source_id: string }; after: { dataset_id: number; date: string; source_id: string };
  band: string; threshold_db: number; method: string;
  summary: { valid_pixels: number; stable_pct: number; increase_pct: number; decrease_pct: number; changed_area_km2: number; valid_area_km2: number };
  maturity: Maturity; is_demo: boolean; limits: string[];
}
