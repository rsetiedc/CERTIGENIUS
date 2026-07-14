"""
SQLAlchemy models for the CertiGenius application.
Uses declarative_base() for Streamlit compatibility (no Flask dependency).
"""
import json
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer, String, Text, create_engine
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def _normalize_position(pos):
    """Normalize a prize position string for matching.

    Maps common variants to canonical forms:
    '1st', '1st prize', 'first', 'first prize' -> '1st'
    '2nd', '2nd prize', 'second' -> '2nd'
    '3rd', '3rd prize', 'third' -> '3rd'
    Everything else -> lowercase stripped
    """
    if not pos:
        return "participation"
    s = pos.strip().lower().replace("_", " ").replace("-", " ")
    for suffix in (" prize", " place", " position"):
        if s.endswith(suffix):
            s = s[: -len(suffix)].strip()
    mapping = {
        "1st": "1st", "first": "1st", "1": "1st",
        "2nd": "2nd", "second": "2nd", "2": "2nd",
        "3rd": "3rd", "third": "3rd", "3": "3rd",
        "participation": "participation", "participant": "participation",
    }
    return mapping.get(s, s)


class TemplateGroup(Base):
    """A group of certificate templates, one per prize position."""
    __tablename__ = "template_groups"

    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, default="")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    is_deleted = Column(Boolean, default=False)

    # Relationships
    templates = relationship(
        "Template", backref="group", lazy="dynamic", cascade="all, delete-orphan"
    )
    batches = relationship(
        "CertificateBatch", backref="template_group", lazy="dynamic"
    )

    def get_template_for_position(self, position):
        """Return the Template matching a prize position, with fallback."""
        if not position:
            position = "Participation"
        norm = _normalize_position(position)
        for t in self.templates.filter_by(is_deleted=False).all():
            if _normalize_position(t.position_label) == norm:
                return t
        for t in self.templates.filter_by(is_deleted=False).all():
            if _normalize_position(t.position_label) == "participation":
                return t
        return self.templates.filter_by(is_deleted=False).first()

    def to_dict(self):
        templates_list = [t.to_dict() for t in self.templates.filter_by(is_deleted=False).all()]
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "templates": templates_list,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Template(Base):
    __tablename__ = "templates"

    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, default="")
    file_path = Column(String(500), nullable=False)
    file_type = Column(String(10), nullable=False)
    position_label = Column(String(50), default="Participation")
    placeholder_fields = Column(Text, default="[]")
    width = Column(Integer, default=1200)
    height = Column(Integer, default=800)
    group_id = Column(Integer, ForeignKey("template_groups.id"), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    is_deleted = Column(Boolean, default=False)

    certificates = relationship("Certificate", backref="template", lazy="dynamic")

    def get_placeholders(self):
        return json.loads(self.placeholder_fields) if self.placeholder_fields else []

    def set_placeholders(self, fields):
        self.placeholder_fields = json.dumps(fields)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "file_path": self.file_path,
            "file_type": self.file_type,
            "position_label": self.position_label,
            "placeholder_fields": self.get_placeholders(),
            "width": self.width,
            "height": self.height,
            "group_id": self.group_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Participant(Base):
    __tablename__ = "participants"

    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    email = Column(String(200), nullable=False)
    prize_position = Column(String(50), default="Participation")
    extra_data = Column(Text, default="{}")
    batch_id = Column(Integer, ForeignKey("certificate_batches.id"))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    certificates = relationship("Certificate", backref="participant", lazy="dynamic")

    def get_extra_data(self):
        return json.loads(self.extra_data) if self.extra_data else {}

    def set_extra_data(self, data):
        self.extra_data = json.dumps(data)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "prize_position": self.prize_position,
            "extra_data": self.get_extra_data(),
            "batch_id": self.batch_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class CertificateBatch(Base):
    __tablename__ = "certificate_batches"

    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    template_group_id = Column(Integer, ForeignKey("template_groups.id"), nullable=True)
    status = Column(String(20), default="pending")
    total_count = Column(Integer, default=0)
    generated_count = Column(Integer, default=0)
    sent_count = Column(Integer, default=0)
    failed_count = Column(Integer, default=0)
    error_message = Column(Text, default="")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime, nullable=True)

    participants = relationship(
        "Participant", backref="batch", lazy="dynamic", cascade="all, delete-orphan"
    )
    certificates = relationship(
        "Certificate", backref="batch", lazy="dynamic", cascade="all, delete-orphan"
    )

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "template_group_id": self.template_group_id,
            "template_group_name": self.template_group.name if self.template_group else "Unknown",
            "status": self.status,
            "total_count": self.total_count,
            "generated_count": self.generated_count,
            "sent_count": self.sent_count,
            "failed_count": self.failed_count,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class Certificate(Base):
    __tablename__ = "certificates"

    id = Column(Integer, primary_key=True)
    batch_id = Column(Integer, ForeignKey("certificate_batches.id"), nullable=False)
    participant_id = Column(Integer, ForeignKey("participants.id"), nullable=False)
    template_id = Column(Integer, ForeignKey("templates.id"), nullable=False)
    file_path = Column(String(500), default="")
    status = Column(String(20), default="pending")
    error_message = Column(Text, default="")
    sent_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id,
            "batch_id": self.batch_id,
            "participant_id": self.participant_id,
            "participant_name": self.participant.name if self.participant else "Unknown",
            "participant_email": self.participant.email if self.participant else "",
            "template_id": self.template_id,
            "file_path": self.file_path,
            "status": self.status,
            "error_message": self.error_message,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
