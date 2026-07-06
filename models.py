import json
from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class TemplateGroup(db.Model):
    """A group of certificate templates, one per prize position."""
    __tablename__ = "template_groups"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default="")
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )
    is_deleted = db.Column(db.Boolean, default=False)

    # Relationships
    templates = db.relationship(
        "Template", backref="group", lazy="dynamic", cascade="all, delete-orphan"
    )
    batches = db.relationship(
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
        # Fallback: try participation template
        for t in self.templates.filter_by(is_deleted=False).all():
            if _normalize_position(t.position_label) == "participation":
                return t
        # Last resort: first template in the group
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
    # Remove trailing "prize" / "place"
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


class Template(db.Model):
    __tablename__ = "templates"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default="")
    file_path = db.Column(db.String(500), nullable=False)
    file_type = db.Column(db.String(10), nullable=False)  # png, jpg, pdf
    position_label = db.Column(db.String(50), default="Participation")  # 1st, 2nd, 3rd, Participation
    placeholder_fields = db.Column(db.Text, default="[]")  # JSON array of field names
    width = db.Column(db.Integer, default=1200)
    height = db.Column(db.Integer, default=800)
    group_id = db.Column(db.Integer, db.ForeignKey("template_groups.id"), nullable=True)
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    is_deleted = db.Column(db.Boolean, default=False)

    # Relationships
    certificates = db.relationship(
        "Certificate", backref="template", lazy="dynamic"
    )

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


class Participant(db.Model):
    __tablename__ = "participants"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(200), nullable=False)
    prize_position = db.Column(db.String(50), default="Participation")
    extra_data = db.Column(db.Text, default="{}")  # JSON for additional columns
    batch_id = db.Column(db.Integer, db.ForeignKey("certificate_batches.id"))
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    certificates = db.relationship("Certificate", backref="participant", lazy="dynamic")

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


class CertificateBatch(db.Model):
    __tablename__ = "certificate_batches"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    template_group_id = db.Column(db.Integer, db.ForeignKey("template_groups.id"), nullable=True)
    status = db.Column(
        db.String(20), default="pending"
    )  # pending, generating, generated, distributing, completed, failed
    total_count = db.Column(db.Integer, default=0)
    generated_count = db.Column(db.Integer, default=0)
    sent_count = db.Column(db.Integer, default=0)
    failed_count = db.Column(db.Integer, default=0)
    error_message = db.Column(db.Text, default="")
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )
    completed_at = db.Column(db.DateTime, nullable=True)

    # Relationships
    participants = db.relationship(
        "Participant", backref="batch", lazy="dynamic", cascade="all, delete-orphan"
    )
    certificates = db.relationship(
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


class Certificate(db.Model):
    __tablename__ = "certificates"

    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(
        db.Integer, db.ForeignKey("certificate_batches.id"), nullable=False
    )
    participant_id = db.Column(
        db.Integer, db.ForeignKey("participants.id"), nullable=False
    )
    template_id = db.Column(
        db.Integer, db.ForeignKey("templates.id"), nullable=False
    )
    file_path = db.Column(db.String(500), default="")
    status = db.Column(
        db.String(20), default="pending"
    )  # pending, generated, sent, failed
    error_message = db.Column(db.Text, default="")
    sent_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )

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
