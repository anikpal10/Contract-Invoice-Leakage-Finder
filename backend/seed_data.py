import sys
import os
from pathlib import Path
from decimal import Decimal
import shutil
import glob

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app.core.database import SessionLocal, engine, Base
from backend.app.core.security import get_password_hash
from backend.app.models.organization import Organization, Workspace, WorkspaceMember
from backend.app.models.user import User, UserRole
from backend.app.models.supplier import Supplier
from backend.app.models.case import ReconciliationCase, CaseStatus
from backend.app.models.document import UploadedDocument, DocumentCategory, ProcessingStatus
from backend.app.models.rule_config import RuleConfiguration
from backend.app.services.extraction import extraction_service
from backend.app.services.reconciliation_engine import reconciliation_engine
from backend.app.services.audit import log_audit_event

def seed():
    print("Beginning database seeding...")
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # Check if already seeded
        existing_org = db.query(Organization).filter(Organization.slug == "apex-global-retail").first()
        if existing_org:
            print("Database already seeded with demo organization. Skipping.")
            return

        # 1. Organization
        org = Organization(
            name="Apex Global Retail Ltd",
            slug="apex-global-retail"
        )
        db.add(org)
        db.flush()

        # 2. Users (Admin, Manager, Reviewer, Viewer)
        default_pwd = get_password_hash("Password123!")

        admin = User(
            organization_id=org.id,
            email="admin@apexretail.co.uk",
            hashed_password=default_pwd,
            full_name="Victoria Stirling (Head of Audit)",
            role=UserRole.ADMIN.value,
            is_active=True
        )
        manager = User(
            organization_id=org.id,
            email="manager@apexretail.co.uk",
            hashed_password=default_pwd,
            full_name="Marcus Vance (AP & Procurement Lead)",
            role=UserRole.MANAGER.value,
            is_active=True
        )
        reviewer = User(
            organization_id=org.id,
            email="reviewer@apexretail.co.uk",
            hashed_password=default_pwd,
            full_name="Elena Rostova (Senior Financial Analyst)",
            role=UserRole.REVIEWER.value,
            is_active=True
        )
        viewer = User(
            organization_id=org.id,
            email="viewer@apexretail.co.uk",
            hashed_password=default_pwd,
            full_name="James Thorne (Internal Auditor / Read-Only)",
            role=UserRole.VIEWER.value,
            is_active=True
        )
        db.add_all([admin, manager, reviewer, viewer])
        db.flush()

        # 3. Workspaces
        ws1 = Workspace(
            organization_id=org.id,
            name="Q4 High-Value Procurement Audit",
            description="Reconciliation batch for major supplier agreements Q4 2026"
        )
        ws2 = Workspace(
            organization_id=org.id,
            name="Logistics & Facilities Review",
            description="Dedicated workspace for haulage, facilities, and maintenance billing"
        )
        db.add_all([ws1, ws2])
        db.flush()

        # Add memberships
        for ws in [ws1, ws2]:
            db.add(WorkspaceMember(workspace_id=ws.id, user_id=admin.id, role="ADMIN"))
            db.add(WorkspaceMember(workspace_id=ws.id, user_id=manager.id, role="MANAGER"))
            db.add(WorkspaceMember(workspace_id=ws.id, user_id=reviewer.id, role="MEMBER"))
            db.add(WorkspaceMember(workspace_id=ws.id, user_id=viewer.id, role="VIEWER"))

        # 4. Baseline Rule Configuration
        rule_config = RuleConfiguration(
            organization_id=org.id,
            version=1,
            is_active=True,
            price_variance_tolerance_pct=Decimal("0.50"),   # 0.5% tolerance
            price_variance_tolerance_abs=Decimal("1.00"),   # £1.00 tolerance
            quantity_variance_tolerance_pct=Decimal("0.00"),
            duplicate_window_days=90,
            fuzzy_match_threshold=85,
            high_severity_threshold=Decimal("500.00"),
            critical_severity_threshold=Decimal("2000.00"),
            require_grn_for_goods=True,
            created_by_id=admin.id,
            change_reason="Standard Corporate Audit Tolerance Rules 2026"
        )
        db.add(rule_config)
        db.flush()

        # 5. Suppliers
        suppliers_data = [
            ("Apex Industrial Supplies Ltd", "SUP-APX-01", "GB123456789", "30 Days Net"),
            ("Brite Logistics & Haulage PLC", "SUP-BRT-02", "GB987654321", "45 Days Net"),
            ("Crestview Packaging Solutions", "SUP-CPS-03", "GB555444333", "30 Days Net"),
            ("Falcon Electrical Contractors", "SUP-FEC-04", "GB777888999", "14 Days Net"),
            ("Kingsway Security & Guarding", "SUP-KSG-05", "GB333222111", "30 Days Net"),
        ]
        supplier_objs = []
        for name, code, tax, terms in suppliers_data:
            s = Supplier(
                organization_id=org.id,
                name=name,
                canonical_name=name.upper(),
                supplier_code=code,
                tax_id=tax,
                payment_terms=terms
            )
            db.add(s)
            supplier_objs.append(s)
        db.flush()

        # 6. Primary Demonstration Case (ABC Supplies / Apex Industrial)
        demo_case = ReconciliationCase(
            organization_id=org.id,
            workspace_id=ws1.id,
            supplier_id=supplier_objs[0].id,
            title="Apex Industrial Supplies Q4 Review",
            case_reference="CASE-202610-APX01",
            currency="GBP",
            created_by_id=manager.id,
            status=CaseStatus.PROCESSING.value,
            notes="Quarterly audit comparing Master Contract CTR-APX-2026-01 against POs, delivery notes and recent invoices."
        )
        db.add(demo_case)
        db.flush()

        # Storage directory setup for demonstration case
        storage_base = os.path.abspath(os.path.join(os.path.dirname(__file__), "storage", "uploads", demo_case.id))
        os.makedirs(storage_base, exist_ok=True)

        synthetic_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "synthetic_dataset", "sample_files"))

        # Ingest Contract
        ctr_file = glob.glob(os.path.join(synthetic_dir, "contracts", "CTR-APX*.csv"))
        if ctr_file:
            target_path = os.path.join(storage_base, os.path.basename(ctr_file[0]))
            shutil.copyfile(ctr_file[0], target_path)
            doc_ctr = UploadedDocument(
                case_id=demo_case.id,
                organization_id=org.id,
                filename=os.path.basename(ctr_file[0]),
                original_filename=os.path.basename(ctr_file[0]),
                file_type="csv",
                category=DocumentCategory.CONTRACT.value,
                storage_path=target_path,
                file_size_bytes=os.path.getsize(target_path),
                sha256_hash="hash_ctr_001",
                processing_status=ProcessingStatus.PENDING.value
            )
            db.add(doc_ctr)
            db.flush()
            extraction_service.extract_document(db, doc_ctr)

        # Ingest Purchase Orders (first 3 POs)
        po_files = glob.glob(os.path.join(synthetic_dir, "pos", "*.csv"))[:3]
        for p_f in po_files:
            target_path = os.path.join(storage_base, os.path.basename(p_f))
            shutil.copyfile(p_f, target_path)
            doc_po = UploadedDocument(
                case_id=demo_case.id,
                organization_id=org.id,
                filename=os.path.basename(p_f),
                original_filename=os.path.basename(p_f),
                file_type="csv",
                category=DocumentCategory.PURCHASE_ORDER.value,
                storage_path=target_path,
                file_size_bytes=os.path.getsize(target_path),
                sha256_hash=f"hash_po_{os.path.basename(p_f)}",
                processing_status=ProcessingStatus.PENDING.value
            )
            db.add(doc_po)
            db.flush()
            extraction_service.extract_document(db, doc_po)

        # Ingest GRNs (first 2 GRNs)
        grn_files = glob.glob(os.path.join(synthetic_dir, "grns", "*.csv"))[:2]
        for g_f in grn_files:
            target_path = os.path.join(storage_base, os.path.basename(g_f))
            shutil.copyfile(g_f, target_path)
            doc_grn = UploadedDocument(
                case_id=demo_case.id,
                organization_id=org.id,
                filename=os.path.basename(g_f),
                original_filename=os.path.basename(g_f),
                file_type="csv",
                category=DocumentCategory.GOODS_RECEIVED_NOTE.value,
                storage_path=target_path,
                file_size_bytes=os.path.getsize(target_path),
                sha256_hash=f"hash_grn_{os.path.basename(g_f)}",
                processing_status=ProcessingStatus.PENDING.value
            )
            db.add(doc_grn)
            db.flush()
            extraction_service.extract_document(db, doc_grn)

        # Ingest Invoices (8 invoices representing varied scenarios)
        inv_files = glob.glob(os.path.join(synthetic_dir, "invoices", "*.csv"))[:8]
        for i_f in inv_files:
            target_path = os.path.join(storage_base, os.path.basename(i_f))
            shutil.copyfile(i_f, target_path)
            doc_inv = UploadedDocument(
                case_id=demo_case.id,
                organization_id=org.id,
                filename=os.path.basename(i_f),
                original_filename=os.path.basename(i_f),
                file_type="csv",
                category=DocumentCategory.INVOICE.value,
                storage_path=target_path,
                file_size_bytes=os.path.getsize(target_path),
                sha256_hash=f"hash_inv_{os.path.basename(i_f)}",
                processing_status=ProcessingStatus.PENDING.value
            )
            db.add(doc_inv)
            db.flush()
            extraction_service.extract_document(db, doc_inv)

        # 7. Run Reconciliation Engine
        print("Running deterministic financial reconciliation engine on demo case...")
        findings = reconciliation_engine.run_reconciliation(db, demo_case)
        print(f"Generated {len(findings)} initial reviewable findings!")

        # 8. Record audit trail
        log_audit_event(
            db=db,
            organization_id=org.id,
            action="SYSTEM_SEEDED",
            resource_type="ORGANIZATION",
            resource_id=org.id,
            user_id=admin.id,
            payload_after={"demo_case": demo_case.case_reference, "findings": len(findings)}
        )

        db.commit()
        print("Database seeding completed successfully!")
        print("Demo Credentials:")
        print(" - Admin: admin@apexretail.co.uk / Password123!")
        print(" - Manager: manager@apexretail.co.uk / Password123!")
        print(" - Reviewer: reviewer@apexretail.co.uk / Password123!")
        print(" - Viewer: viewer@apexretail.co.uk / Password123!")

    except Exception as e:
        db.rollback()
        print(f"Error seeding database: {e}")
        raise e
    finally:
        db.close()

if __name__ == "__main__":
    seed()

