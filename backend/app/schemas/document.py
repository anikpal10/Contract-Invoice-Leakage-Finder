from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime
from decimal import Decimal

class DocumentResponse(BaseModel):
    id: str
    case_id: str
    filename: str
    original_filename: str
    file_type: str
    category: str
    file_size_bytes: int
    sha256_hash: str
    processing_status: str
    error_message: Optional[str] = None
    extracted_metadata: Optional[Dict[str, Any]] = None
    created_at: datetime

    class Config:
        from_attributes = True

class RecentDocumentItem(BaseModel):
    id: str
    case_id: str
    case_reference: str
    case_title: str
    filename: str
    original_filename: str
    file_type: str
    category: str
    file_size_bytes: int
    processing_status: str
    created_at: datetime
    error_message: Optional[str] = None

class PipelineResultFinding(BaseModel):
    id: str
    finding_category: str
    supplier_name: str
    invoice_reference: str
    line_number: Optional[int] = None
    item_code: Optional[str] = None
    item_description: Optional[str] = None
    expected_amount: Decimal
    invoiced_amount: Decimal
    potential_difference: Decimal
    currency: str
    severity: str
    review_status: str
    calculation_explanation: str
    source_document_references: Optional[List[Dict[str, Any]]] = None

class AutomatedStepItem(BaseModel):
    name: str
    status: str
    detail: str

class PipelineResultResponse(BaseModel):
    document_id: str
    case_id: str
    case_reference: str
    case_title: str
    filename: str
    original_filename: str
    category: str
    processing_status: str
    uploaded_at: datetime
    recognized_data: Optional[Dict[str, Any]] = None
    findings_count: int
    potential_leakage: Decimal
    findings: List[PipelineResultFinding] = []
    automated_steps: List[AutomatedStepItem] = []

class DocumentUploadResponse(BaseModel):
    id: str
    case_id: str
    case_reference: Optional[str] = None
    case_title: Optional[str] = None
    original_filename: str
    category: str
    processing_status: str
    message: str
    reconciled: Optional[bool] = False
    findings_count: Optional[int] = 0
    potential_leakage: Optional[Decimal] = Decimal("0.00")
    recognized_data: Optional[Dict[str, Any]] = None
    findings: Optional[List[PipelineResultFinding]] = []
    automated_steps: Optional[List[AutomatedStepItem]] = []

class DirectPathIngestRequest(BaseModel):
    file_path: str
    category: Optional[str] = "INVOICE"

class DirectFolderIngestRequest(BaseModel):
    folder_path: str
    category: Optional[str] = "AUTO"

class DirectBatchIngestItem(BaseModel):
    filename: str
    file_path: str
    category: str
    status: str
    document_id: Optional[str] = None
    message: str

class DirectBatchIngestResponse(BaseModel):
    case_id: str
    total_found: int
    ingested_count: int
    skipped_duplicates: int
    errors: int
    results: List[DirectBatchIngestItem]


