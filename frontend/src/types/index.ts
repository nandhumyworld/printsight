// ===== Auth =====
export type Role = 'owner' | 'print_person';

export interface User {
  id: number;
  email: string;
  full_name: string;
  role: Role;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface LoginRequest { email: string; password: string; }
export interface LoginResponse { access_token: string; refresh_token: string; token_type: string; }
export interface RegisterRequest { email: string; password: string; full_name: string; }
export interface UpdateProfileRequest { full_name?: string; email?: string; current_password?: string; new_password?: string; }

// ===== Printers =====
export type ColumnMapping = Record<string, string>;

export interface Printer {
  id: number;
  owner_id: number;
  name: string;
  model: string | null;
  type: string | null;
  serial_number: string | null;
  location: string | null;
  image_url?: string;
  column_mapping: ColumnMapping;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}
export interface PrinterCreate { name: string; model?: string; type?: string; serial_number?: string; location?: string; column_mapping?: ColumnMapping; }
export interface PrinterUpdate { name?: string; model?: string; type?: string; serial_number?: string; location?: string; is_active?: boolean; }

// ===== API Keys =====
export interface PrinterApiKey {
  id: number;
  printer_id: number;
  key_prefix: string;
  label: string | null;
  last_used_at: string | null;
  is_active: boolean;
  created_at: string;
}
export interface PrinterApiKeyCreateResponse extends PrinterApiKey { full_key: string; }

// ===== Papers =====
export interface Paper {
  id: number;
  owner_id: number;
  name: string;
  display_name: string | null;
  length_mm: number | null;
  width_mm: number | null;
  gsm_min: number | null;
  gsm_max: number | null;
  counter_multiplier: number;
  price_per_sheet: number;
  currency: string;
  created_at: string;
}
export interface PaperCreate { name: string; display_name?: string; length_mm?: number; width_mm?: number; gsm_min?: number; gsm_max?: number; counter_multiplier?: number; price_per_sheet: number; currency?: string; }
export interface PaperUpdate extends Partial<PaperCreate> {}

// ===== Toners =====
export type TonerColor = 'Black' | 'Cyan' | 'Magenta' | 'Yellow' | 'Gold' | 'Silver' | 'Clear' | 'White' | 'Texture' | 'Pink';
export type TonerType = 'standard' | 'specialty';

export interface Toner {
  id: number;
  printer_id: number;
  toner_color: TonerColor;
  toner_type: TonerType;
  price_per_unit: number;
  rated_yield_pages: number;
  currency: string;
  created_at: string;
}
export interface TonerCreate { toner_color: TonerColor; toner_type?: TonerType; price_per_unit: number; rated_yield_pages: number; currency?: string; }

// ===== Toner Replacement =====
export interface TonerReplacementLog {
  id: number;
  printer_id: number;
  toner_id: number;
  replaced_by_user_id: number;
  counter_reading_at_replacement: number;
  replaced_at: string;
  actual_yield_pages: number | null;
  yield_efficiency_pct: number | null;
  notes: string | null;
  created_at: string;
  toner?: Toner;
  replaced_by?: User;
}
export interface TonerReplacementCreate { toner_id: number; counter_reading_at_replacement: number; replaced_at: string; notes?: string; }

// ===== Upload =====
export type UploadSource = 'manual' | 'api_push';
export type UploadStatus = 'processing' | 'completed' | 'failed';

export interface SkippedRow { row_number: number; reason: string; }
export interface UploadBatch {
  id: number;
  printer_id: number;
  uploaded_by_user_id: number | null;
  source: UploadSource;
  filename: string | null;
  uploaded_at: string;
  rows_total: number;
  rows_imported: number;
  rows_skipped: number;
  skipped_details: SkippedRow[];
  status: UploadStatus;
}

// ===== Print Jobs =====
export interface PrintJob {
  id: number;
  printer_id: number;
  upload_batch_id: number | null;
  job_id: string;
  job_name: string | null;
  status: string | null;
  owner_name: string | null;
  recorded_at: string | null;
  arrived_at: string | null;
  printed_at: string | null;
  color_mode: string | null;
  paper_type: string | null;
  paper_size: string | null;
  paper_width_mm: number | null;
  paper_length_mm: number | null;
  is_duplex: boolean;
  copies: number;
  input_pages: number;
  printed_pages: number;
  color_pages: number;
  bw_pages: number;
  specialty_pages: number;
  gold_pages: number;
  silver_pages: number;
  clear_pages: number;
  white_pages: number;
  texture_pages: number;
  pink_pages: number;
  blank_pages: number;
  printed_sheets: number;
  waste_sheets: number;
  error_info: string | null;
  computed_paper_cost: number;
  computed_toner_cost: number;
  computed_total_cost: number;
  is_waste: boolean;
}

// ===== Notifications =====
export interface NotificationConfig {
  id: number;
  user_id: number;
  email_enabled: boolean;
  email_address: string | null;
  telegram_enabled: boolean;
  telegram_chat_id: string | null;
  telegram_bot_token: string | null;
  high_cost_threshold: number | null;
  toner_low_pages_threshold: number;
  toner_yield_warning_pct: number;
  monthly_report_enabled: boolean;
  weekly_summary_enabled: boolean;
  updated_at: string;
}
export interface NotificationConfigUpdate extends Partial<Omit<NotificationConfig, 'id' | 'user_id' | 'updated_at'>> {}

// ===== Webhooks =====
export type WebhookEvent = 'log_imported' | 'high_cost_alert' | 'toner_low' | 'toner_yield_warning' | 'monthly_report_ready' | 'weekly_summary_ready';

export interface WebhookConfig {
  id: number;
  owner_id: number;
  url: string;
  events: WebhookEvent[];
  secret: string;
  is_active: boolean;
  created_at: string;
}
export interface WebhookConfigCreate { url: string; events: WebhookEvent[]; secret: string; }
export interface WebhookDeliveryLog { id: number; webhook_config_id: number; event: string; payload: Record<string, unknown>; response_status: number | null; response_body: string | null; delivered_at: string; failed: boolean; }

// ===== Analytics =====
export interface AnalyticsSummary { total_cost: number; total_pages: number; waste_pct: number; color_cost_per_page: number; bw_cost_per_page: number; waste_cost: number; period: string; }
export interface CostBreakdown { paper_cost: number; toner_cost: number; color_cost: number; bw_cost: number; specialty_cost: number; waste_cost: number; }
export interface TrendPoint { date: string; total_cost: number; pages: number; waste_cost: number; }
export interface PrinterComparison { printer_id: number; printer_name: string; total_cost: number; total_pages: number; cost_per_page: number; }

// ===== Toner Yield =====
export interface CartridgeStatus {
  toner_id: number;
  toner_color: TonerColor;
  toner_type: TonerType;
  pages_used: number;
  pages_remaining: number;
  pct_used: number;
  rated_yield: number;
  estimated_replacement_date: string | null;
  actual_cost_per_page: number | null;
  rated_cost_per_page: number;
}
export interface YieldHistoryRecord {
  log_id: number;
  replaced_at: string;
  toner_color: TonerColor;
  rated_yield: number;
  actual_yield: number;
  efficiency_pct: number;
  actual_cost_per_page: number;
  rated_cost_per_page: number;
  cost_variance_pct: number;
  early_replacement_flag: boolean;
}

// ===== API Responses =====
export interface ApiResponse<T> { data: T; message: string; }
export interface PaginatedResponse<T> { data: T[]; total: number; page: number; per_page: number; }
export interface ApiErrorResponse { detail: string; }
