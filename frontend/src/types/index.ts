export interface User {
  id: string;
  email: string;
  full_name: string;
  role: 'ADMIN' | 'MANAGER' | 'REVIEWER' | 'VIEWER';
  is_active: boolean;
  organization_id: string;
  created_at: string;
}

export interface Workspace {
  id: string;
  organization_id: string;
  name: string;
  description?: string;
  created_at: string;
}

export interface Supplier {
  id: string;
  organization_id: string;
  name: string;
  canonical_name: string;
  supplier_code?: string;
  tax_id?: string;
  payment_terms?: string;
  contact_email?: string;
  created_at: string;
}

export interface ReconciliationCase {
  id: string;
  organization_id: string;
  workspace_id: string;
  supplier_id?: string;
  supplier_name?: string;
  title: string;
  case_reference: string;
  currency: string;
  status: string;
  date_from?: string;
  date_to?: string;
  notes?: string;
  created_at: string;
  updated_at: string;
  document_count: number;
  finding_count: number;
  potential_leakage_amount: number;
  confirmed_leakage_amount: number;
}

export interface UploadedDocument {
  id: string;
  case_id: string;
  filename: string;
  original_filename: string;
  file_type: string;
  category: string;
  file_size_bytes: number;
  sha256_hash: string;
  processing_status: string;
  error_message?: string;
  created_at: string;
}

export interface RecentDocumentItem {
  id: string;
  case_id: string;
  case_reference: string;
  case_title: string;
  filename: string;
  original_filename: string;
  file_type: string;
  category: string;
  file_size_bytes: number;
  processing_status: string;
  created_at: string;
  error_message?: string;
}

export interface PipelineResultFinding {
  id: string;
  finding_category: string;
  supplier_name: string;
  invoice_reference: string;
  line_number?: number;
  item_code?: string;
  item_description?: string;
  expected_amount: number;
  invoiced_amount: number;
  potential_difference: number;
  currency: string;
  severity: string;
  review_status: string;
  calculation_explanation: string;
  source_document_references?: Array<Record<string, any>>;
}

export interface AutomatedStepItem {
  name: string;
  status: string;
  detail: string;
}

export interface PipelineResultResponse {
  document_id: string;
  case_id: string;
  case_reference: string;
  case_title: string;
  filename: string;
  original_filename: string;
  category: string;
  processing_status: string;
  uploaded_at: string;
  recognized_data?: Record<string, any>;
  findings_count: number;
  potential_leakage: number;
  findings: PipelineResultFinding[];
  automated_steps: AutomatedStepItem[];
}

export interface DocumentUploadResponse {
  id: string;
  case_id: string;
  case_reference?: string;
  case_title?: string;
  original_filename: string;
  category: string;
  processing_status: string;
  message: string;
  reconciled?: boolean;
  findings_count?: number;
  potential_leakage?: number;
  recognized_data?: Record<string, any>;
  findings?: PipelineResultFinding[];
  automated_steps?: AutomatedStepItem[];
}

export interface ExtractedField {
  id: string;
  field_name: string;
  extracted_value?: string;
  source_page_or_cell?: string;
  confidence_score?: number;
  extraction_method: string;
  requires_review: boolean;
  reviewed_value?: string;
}

export interface ReviewDecision {
  id: string;
  reviewer_id?: string;
  reviewer_name?: string;
  action: string;
  previous_status: string;
  new_status: string;
  comment?: string;
  adjusted_amount?: number;
  created_at: string;
}

export interface Finding {
  id: string;
  case_id: string;
  finding_category: string;
  supplier_name: string;
  invoice_reference: string;
  line_number?: number;
  item_code?: string;
  item_description?: string;
  expected_amount: number;
  invoiced_amount: number;
  potential_difference: number;
  currency: string;
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW' | 'INFO';
  review_status: 'NEW' | 'UNDER_REVIEW' | 'CONFIRMED' | 'REJECTED' | 'NEEDS_MORE_INFO';
  calculation_explanation: string;
  source_document_references?: Array<Record<string, any>>;
  rule_version: number;
  requires_more_info_reason?: string;
  created_at: string;
  updated_at: string;
  decisions?: ReviewDecision[];
}

export interface RuleConfig {
  id: string;
  organization_id: string;
  version: number;
  is_active: boolean;
  price_variance_tolerance_pct: number;
  price_variance_tolerance_abs: number;
  quantity_variance_tolerance_pct: number;
  duplicate_window_days: number;
  fuzzy_match_threshold: number;
  high_severity_threshold: number;
  critical_severity_threshold: number;
  require_grn_for_goods: boolean;
  change_reason?: string;
  created_at: string;
}

export interface DashboardStats {
  total_invoices: number;
  total_cases: number;
  total_documents?: number;
  potential_leakage: number;
  confirmed_leakage_amount?: number;
  findings_awaiting_review: number;
  confirmed_findings: number;
  rejected_findings: number;
}

export interface AuditLog {
  id: string;
  organization_id: string;
  user_id?: string;
  action: string;
  resource_type: string;
  resource_id: string;
  payload_before?: Record<string, any>;
  payload_after?: Record<string, any>;
  ip_address?: string;
  created_at: string;
}

export interface ExportRecord {
  id: string;
  case_id: string;
  format: string;
  file_name: string;
  record_count: number;
  total_leakage_amount: number;
  created_at: string;
  download_url?: string;
}

