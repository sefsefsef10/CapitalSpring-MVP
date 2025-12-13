// Document types
export type DocumentStatus = 'pending' | 'processing' | 'processed' | 'needs_review' | 'failed'

export type DocumentType =
  | 'monthly_financials'
  | 'quarterly_financials'
  | 'annual_financials'
  | 'covenant_compliance'
  | 'borrowing_base'
  | 'ar_aging'
  | 'capital_call'
  | 'distribution_notice'
  | 'nav_statement'
  | 'invoice'
  | 'other'
  | 'unknown'

export type ProcessorType =
  | 'document_ai_invoice'
  | 'document_ai_form'
  | 'document_ai_ocr'
  | 'claude'
  | 'manual'

export interface Document {
  id: string
  gcs_path: string
  original_filename: string
  mime_type: string | null
  file_size_bytes: number | null
  doc_type: DocumentType | null
  status: DocumentStatus
  extracted_data: Record<string, unknown> | null
  confidence: number | null
  field_confidences: Record<string, number> | null
  requires_review: boolean
  processor_used: ProcessorType | null
  processing_time_ms: number | null
  processing_error: string | null
  uploaded_by: string | null
  reviewed_by: string | null
  created_at: string
  processed_at: string | null
  updated_at: string
}

export interface DocumentListResponse {
  items: Document[]
  total: number
  page: number
  page_size: number
  pages: number
}

export interface DocumentMetrics {
  total_documents: number
  processed_count: number
  pending_count: number
  failed_count: number
  needs_review_count: number
  automation_rate: number
  avg_confidence: number
  avg_processing_time_ms: number
  documents_by_type: Record<string, number>
  documents_by_status: Record<string, number>
  processor_usage: Record<string, number>
}

// Exception types
export type ExceptionStatus = 'open' | 'in_review' | 'resolved' | 'ignored'
export type ExceptionCategory =
  | 'validation_error'
  | 'extraction_error'
  | 'low_confidence'
  | 'missing_field'
  | 'invalid_format'
  | 'business_rule'
  | 'cross_field'
  | 'unknown_doc_type'
  | 'processing_failure'
  | 'other'
export type ExceptionPriority = 'low' | 'medium' | 'high' | 'critical'

export interface Exception {
  id: string
  document_id: string
  category: ExceptionCategory
  reason: string
  field_name: string | null
  expected_value: string | null
  actual_value: string | null
  priority: ExceptionPriority
  status: ExceptionStatus
  resolution: Record<string, unknown> | null
  resolution_notes: string | null
  resolved_by: string | null
  resolved_at: string | null
  auto_resolvable: boolean
  suggested_resolution: Record<string, unknown> | null
  created_at: string
  updated_at: string
  // With document details
  document_filename?: string
  document_type?: string | null
  document_status?: string
}

export interface ExceptionListResponse {
  items: Exception[]
  total: number
  page: number
  page_size: number
  pages: number
}

export interface ExceptionMetrics {
  total_exceptions: number
  open_count: number
  in_review_count: number
  resolved_count: number
  ignored_count: number
  exceptions_by_category: Record<string, number>
  exceptions_by_priority: Record<string, number>
  avg_resolution_time_hours: number
  auto_resolved_count: number
}

// Dashboard types
export interface DashboardMetrics {
  period_days: number
  total_documents: number
  documents_by_status: Record<string, number>
  automation_rate: number
  avg_confidence: number
  avg_processing_time_ms: number
  documents_by_type: Record<string, number>
  processor_usage: Record<string, number>
  open_exceptions: number
  kpis: {
    processed_count: number
    pending_count: number
    failed_count: number
    needs_review_count: number
  }
}

export interface TrendData {
  period_days: number
  granularity: string
  document_trends: Array<{
    period: string
    total: number
    processed: number
    failed: number
    needs_review: number
  }>
  confidence_trends: Array<{
    period: string
    avg_confidence: number
  }>
  exception_trends: Array<{
    period: string
    created: number
    resolved: number
  }>
}

// Export types
export type ExportTemplate =
  | 'portfolio_financials'
  | 'covenant_compliance'
  | 'borrowing_base'
  | 'capital_activity'
  | 'exception_report'
  | 'custom'

export interface ExportRequest {
  document_ids: string[]
  template: ExportTemplate
  format: 'xlsx' | 'csv' | 'json'
  include_raw_data: boolean
  include_confidence_scores: boolean
  custom_fields?: string[]
}

export interface ExportResponse {
  export_id: string
  status: string
  download_url: string | null
  expires_at: string | null
  file_name: string
  file_size_bytes: number | null
  document_count: number
  created_at: string
}
