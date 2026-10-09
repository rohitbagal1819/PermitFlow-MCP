"""Permit data service – loads and queries mock permit data."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from permitflow_mcp.config import settings

logger = logging.getLogger("permitflow_mcp.permit_service")


class PermitService:
    """Provides access to mock permit, project, document, and comment data."""

    def __init__(self, data_dir: Optional[str] = None) -> None:
        self._data_dir = Path(data_dir or settings.mock_data_dir)
        self._permits: list[dict] = []
        self._projects: list[dict] = []
        self._documents: list[dict] = []
        self._requirements: list[dict] = []
        self._comments: list[dict] = []
        self._inspections: list[dict] = []
        self._cases: list[dict] = []
        self._loaded = False

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def _load_json(self, filename: str) -> list[dict]:
        path = self._data_dir / filename
        if not path.exists():
            logger.warning("Data file not found: %s", path)
            return []
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)

    def load_data(self) -> None:
        """Load all mock data from JSON files."""
        if self._loaded:
            return
        logger.info("[PermitService] Loading mock data from %s", self._data_dir)
        self._permits = self._load_json("permits.json")
        self._projects = self._load_json("projects.json")
        self._documents = self._load_json("submitted_documents.json")
        self._requirements = self._load_json("requirements.json")
        self._comments = self._load_json("authority_comments.json")
        self._inspections = self._load_json("inspections.json")
        self._cases = self._load_json("previous_cases.json")
        self._contractors = self._load_json("contractors.json")
        self._loaded = True
        logger.info(
            "[PermitService] Loaded %d permits, %d projects, %d documents, "
            "%d requirements, %d comments, %d inspections, %d cases, %d contractors",
            len(self._permits),
            len(self._projects),
            len(self._documents),
            len(self._requirements),
            len(self._comments),
            len(self._inspections),
            len(self._cases),
            len(self._contractors),
        )

    def _ensure_loaded(self) -> None:
        if not self._loaded:
            self.load_data()

    # ------------------------------------------------------------------
    # Permit queries
    # ------------------------------------------------------------------

    def get_permit(self, permit_id: str) -> Optional[dict]:
        """Return a single permit by ID, or None."""
        self._ensure_loaded()
        for p in self._permits:
            if p["permit_id"] == permit_id:
                return p
        return None

    def list_permits(self) -> list[dict]:
        self._ensure_loaded()
        return list(self._permits)

    # ------------------------------------------------------------------
    # Project queries
    # ------------------------------------------------------------------

    def get_project(self, project_id: str) -> Optional[dict]:
        self._ensure_loaded()
        for p in self._projects:
            if p["project_id"] == project_id:
                return p
        return None

    # ------------------------------------------------------------------
    # Document queries
    # ------------------------------------------------------------------

    def get_document(self, document_id: str) -> Optional[dict]:
        self._ensure_loaded()
        for d in self._documents:
            if d["document_id"] == document_id:
                return d
        return None

    def get_documents_for_permit(self, permit_id: str) -> list[dict]:
        """Return all documents associated with a permit."""
        self._ensure_loaded()
        permit = self.get_permit(permit_id)
        if not permit:
            return []
        all_doc_ids = set(permit.get("required_document_ids", []))
        all_doc_ids.update(permit.get("submitted_document_ids", []))
        return [d for d in self._documents if d["document_id"] in all_doc_ids]

    def get_required_documents(self, permit_id: str) -> list[dict]:
        """Return metadata for all required documents of a permit."""
        self._ensure_loaded()
        permit = self.get_permit(permit_id)
        if not permit:
            return []
        req_ids = set(permit.get("required_document_ids", []))
        return [d for d in self._documents if d["document_id"] in req_ids]

    def get_submitted_documents(self, permit_id: str) -> list[dict]:
        """Return metadata for all submitted documents of a permit."""
        self._ensure_loaded()
        permit = self.get_permit(permit_id)
        if not permit:
            return []
        sub_ids = set(permit.get("submitted_document_ids", []))
        return [d for d in self._documents if d["document_id"] in sub_ids]

    # ------------------------------------------------------------------
    # Requirement queries
    # ------------------------------------------------------------------

    def get_requirements_for_permit(self, permit_id: str) -> list[dict]:
        """Return jurisdiction/type-matching requirements for a permit."""
        self._ensure_loaded()
        permit = self.get_permit(permit_id)
        if not permit:
            return []
        return [
            r
            for r in self._requirements
            if r["jurisdiction"] == permit["jurisdiction"]
            and r["permit_type"] == permit["permit_type"]
        ]

    def get_requirements_by_jurisdiction(
        self, jurisdiction: str, permit_type: Optional[str] = None
    ) -> list[dict]:
        self._ensure_loaded()
        clean_jurisdiction = jurisdiction.strip().lower()
        results = [
            r
            for r in self._requirements
            if clean_jurisdiction == r["jurisdiction"].lower()
            or clean_jurisdiction in r["jurisdiction"].lower()
            or r["jurisdiction"].lower() in clean_jurisdiction
        ]
        if permit_type:
            clean_type = permit_type.strip().lower()
            results = [r for r in results if r["permit_type"].lower() == clean_type]
        return results


    # ------------------------------------------------------------------
    # Authority comment queries
    # ------------------------------------------------------------------

    def get_comments_for_permit(self, permit_id: str) -> list[dict]:
        """Return all authority comments for a permit."""
        self._ensure_loaded()
        return [c for c in self._comments if c["permit_id"] == permit_id]

    def get_open_comments(self, permit_id: str) -> list[dict]:
        return [
            c
            for c in self.get_comments_for_permit(permit_id)
            if c.get("status") == "open"
        ]

    # ------------------------------------------------------------------
    # Inspection queries
    # ------------------------------------------------------------------

    def get_inspections_for_permit(self, permit_id: str) -> list[dict]:
        self._ensure_loaded()
        return [i for i in self._inspections if i["permit_id"] == permit_id]

    def get_pending_inspections(self, permit_id: str) -> list[dict]:
        return [
            i
            for i in self.get_inspections_for_permit(permit_id)
            if i.get("status") in ("scheduled", "pending")
        ]

    # ------------------------------------------------------------------
    # Case queries
    # ------------------------------------------------------------------

    def get_cases_for_permit(self, permit_id: str) -> list[dict]:
        self._ensure_loaded()
        return [c for c in self._cases if c["permit_id"] == permit_id]

    # ------------------------------------------------------------------
    # Contractor queries
    # ------------------------------------------------------------------

    def list_contractors(self) -> list[dict]:
        self._ensure_loaded()
        return list(self._contractors)

    def get_contractor(self, name_or_id: str) -> Optional[dict]:
        self._ensure_loaded()
        needle = name_or_id.strip().lower()
        for c in self._contractors:
            if (
                c.get("contractor_id", "").lower() == needle
                or c.get("name", "").lower() == needle
                or needle in c.get("name", "").lower()
                or c.get("roc_license", "").lower() == needle
            ):
                return c
        return None

    def add_permit(self, permit_data: dict) -> dict:
        """Add a newly created draft permit and persist to disk."""
        self._ensure_loaded()
        self._permits.append(permit_data)
        path = self._data_dir / "permits.json"
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self._permits, fh, indent=2)
        self._append_audit_log(
            "New Permit Intake Created",
            {
                "Permit ID": permit_data.get("permit_id", "N/A"),
                "Project Name": permit_data.get("project_name", "N/A"),
                "Trade": permit_data.get("permit_type", "N/A"),
                "Jurisdiction": permit_data.get("jurisdiction", "N/A"),
                "Status": permit_data.get("status", "draft"),
            },
        )
        return permit_data

    # ------------------------------------------------------------------
    # Mutation operations (Status updates, Comment resolutions & Audit log)
    # ------------------------------------------------------------------

    def log_action(self, permit_id: str, action: str, notes: str) -> None:
        """Log an operational activity to reports/audit_log.md."""
        self._append_audit_log(action, {"Permit ID": permit_id, "Notes": notes})

    def _append_audit_log(self, action: str, details: dict) -> None:
        """Append an entry to reports/audit_log.md."""
        try:
            reports_dir = Path(settings.reports_dir)
            reports_dir.mkdir(parents=True, exist_ok=True)
            log_path = reports_dir / "audit_log.md"
            if not log_path.exists():
                log_path.write_text(
                    "# 📋 PermitFlow Real-Time Activity & Audit Log\n\n"
                    "This log records live mutations and actions executed through the PermitFlow MCP interface.\n\n"
                    "---\n\n",
                    encoding="utf-8",
                )
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            entry = [f"### ⏱ [{timestamp}] {action}"]
            for k, v in details.items():
                entry.append(f"- **{k}:** {v}")
            entry.append("\n---\n")
            with open(log_path, "a", encoding="utf-8") as fh:
                fh.write("\n".join(entry) + "\n")
        except Exception as exc:
            logger.warning("Failed to append to audit log: %s", exc)

    def update_permit_status(
        self, permit_id: str, new_status: str, notes: Optional[str] = None
    ) -> Optional[dict]:
        """Update the status of a permit and persist the change."""
        self._ensure_loaded()
        for p in self._permits:
            if p["permit_id"] == permit_id:
                old_status = p.get("status", "unknown")
                p["status"] = new_status.lower()
                if notes:
                    p["notes"] = notes
                p["last_updated"] = "2026-07-06"
                path = self._data_dir / "permits.json"
                with open(path, "w", encoding="utf-8") as fh:
                    json.dump(self._permits, fh, indent=2)
                logger.info("[PermitService] Updated permit %s to status '%s'", permit_id, new_status)
                self._append_audit_log(
                    "Permit Status Update",
                    {
                        "Permit ID": permit_id,
                        "Project Name": p.get("project_name", "Unknown"),
                        "Old Status": old_status.upper(),
                        "New Status": new_status.upper(),
                        "Notes": notes or "No notes provided",
                    },
                )
                return p
        return None

    def resolve_comment(
        self, comment_id: str, resolution_notes: Optional[str] = None
    ) -> Optional[dict]:
        """Mark an authority comment as resolved and persist the change."""
        self._ensure_loaded()
        for c in self._comments:
            if c["comment_id"] == comment_id:
                c["status"] = "resolved"
                c["resolution_required"] = False
                if resolution_notes:
                    c["resolution_notes"] = resolution_notes
                path = self._data_dir / "authority_comments.json"
                with open(path, "w", encoding="utf-8") as fh:
                    json.dump(self._comments, fh, indent=2)
                logger.info("[PermitService] Resolved authority comment %s", comment_id)
                self._append_audit_log(
                    "Authority Comment Resolved",
                    {
                        "Comment ID": comment_id,
                        "Permit ID": c.get("permit_id", "Unknown"),
                        "Authority": c.get("authority", "Unknown"),
                        "Category": c.get("category", "Unknown"),
                        "Resolution Notes": resolution_notes or "Marked resolved via MCP",
                    },
                )
                return c
        return None

    def update_document_status(
        self, document_id: str, new_status: str, notes: Optional[str] = None
    ) -> Optional[dict]:
        """Update the status of a submitted document and persist the change."""
        self._ensure_loaded()
        for d in self._documents:
            if d["document_id"] == document_id:
                old_status = d.get("status", "unknown")
                d["status"] = new_status.lower()
                if notes:
                    d["notes"] = notes
                path = self._data_dir / "submitted_documents.json"
                with open(path, "w", encoding="utf-8") as fh:
                    json.dump(self._documents, fh, indent=2)
                logger.info("[PermitService] Updated document %s to status '%s'", document_id, new_status)
                self._append_audit_log(
                    "Document Status Update",
                    {
                        "Document ID": document_id,
                        "Document Name": d.get("document_name", "Unknown"),
                        "Permit ID": d.get("permit_id", "Unknown"),
                        "Old Status": old_status.upper(),
                        "New Status": new_status.upper(),
                        "Notes": notes or "No notes provided",
                    },
                )
                return d
        return None

