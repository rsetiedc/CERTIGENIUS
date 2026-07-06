"""
CertiGenius - Automated Certificate Generation and Distribution Platform
Main Flask application.
"""

import json
import logging
import os
import re
import shutil
import uuid
from datetime import datetime, timezone

from flask import (
    Flask,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)

from config import Config
from models import Certificate, CertificateBatch, Participant, Template, TemplateGroup, db
import io

import openpyxl

from utils.certificate_generator import generate_certificate
from utils.email_sender import EmailSender
from utils.excel_parser import parse_file

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def _detect_position_from_filename(filename):
    """Detect a prize position from a filename.

    Examples:
        '1st_prize.pdf'   -> '1st'
        '2nd_prize.pdf'   -> '2nd'
        '3rd_prize.pdf'   -> '3rd'
        'participation.pdf' -> 'Participation'
        'first_place.pdf' -> '1st'
    """
    name = os.path.splitext(filename)[0].lower().replace("-", " ").replace("_", " ")
    if re.search(r'\b1st\b|first', name):
        return "1st"
    if re.search(r'\b2nd\b|second', name):
        return "2nd"
    if re.search(r'\b3rd\b|third', name):
        return "3rd"
    if re.search(r'particip', name):
        return "Participation"
    return "Participation"


def create_app():
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app.config.from_object(Config)

    # Initialize extensions
    db.init_app(app)

    # Ensure upload directories exist
    os.makedirs(
        os.path.join(app.root_path, Config.UPLOAD_FOLDER, "templates"), exist_ok=True
    )
    os.makedirs(
        os.path.join(app.root_path, Config.UPLOAD_FOLDER, "participants"), exist_ok=True
    )
    os.makedirs(
        os.path.join(app.root_path, Config.CERTIFICATE_FOLDER), exist_ok=True
    )

    with app.app_context():
        db.create_all()

    # Register routes
    register_routes(app)

    return app


def register_routes(app):
    """Register all application routes."""

    # ---------- Dashboard ----------
    @app.route("/")
    def dashboard():
        template_count = TemplateGroup.query.filter_by(is_deleted=False).count()
        participant_count = Participant.query.count()
        batch_count = CertificateBatch.query.count()
        certificate_count = Certificate.query.count()
        sent_count = Certificate.query.filter_by(status="sent").count()

        recent_batches = (
            CertificateBatch.query.order_by(CertificateBatch.created_at.desc())
            .limit(5)
            .all()
        )

        return render_template(
            "dashboard.html",
            template_count=template_count,
            participant_count=participant_count,
            batch_count=batch_count,
            certificate_count=certificate_count,
            sent_count=sent_count,
            recent_batches=recent_batches,
        )

    # ---------- Template Management ----------

    @app.route("/templates")
    def templates():
        all_groups = (
            TemplateGroup.query.filter_by(is_deleted=False)
            .order_by(TemplateGroup.created_at.desc())
            .all()
        )
        return render_template("templates.html", template_groups=all_groups)

    @app.route("/templates/upload", methods=["POST"])
    def upload_template():
        files = request.files.getlist("template_files")
        if not files or all(f.filename == "" for f in files):
            flash("No files selected", "error")
            return redirect(url_for("templates"))

        name = request.form.get("name", "").strip()
        if not name:
            name = f"Template Group {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}"

        # Parse placeholder fields from form
        placeholder_fields_str = request.form.get("placeholder_fields", "")
        placeholder_fields = []
        if placeholder_fields_str:
            placeholder_fields = [
                f.strip() for f in placeholder_fields_str.split(",") if f.strip()
            ]

        # Validate all files
        allowed_extensions = {".png", ".jpg", ".jpeg", ".pdf"}
        for file in files:
            ext = os.path.splitext(file.filename)[1].lower()
            if ext not in allowed_extensions:
                flash(
                    f"Unsupported file format: {file.filename}. Allowed: PNG, JPG, JPEG, PDF",
                    "error",
                )
                return redirect(url_for("templates"))

        # Create template group
        group = TemplateGroup(
            name=name,
            description=request.form.get("description", ""),
        )
        db.session.add(group)
        db.session.flush()  # get group.id

        upload_dir = os.path.join(
            app.root_path, Config.UPLOAD_FOLDER, "templates"
        )

        positions_added = []
        for file in files:
            if file.filename == "":
                continue
            ext = os.path.splitext(file.filename)[1].lower()
            position_label = _detect_position_from_filename(file.filename)

            # Save file
            filename = f"{uuid.uuid4().hex}{ext}"
            file_path = os.path.join(upload_dir, filename)
            file.save(file_path)

            template = Template(
                name=f"{name} - {position_label}",
                description=request.form.get("description", ""),
                file_path=os.path.join(Config.UPLOAD_FOLDER, "templates", filename),
                file_type=ext[1:],  # Remove the dot
                position_label=position_label,
                group_id=group.id,
            )
            template.set_placeholders(placeholder_fields)
            db.session.add(template)
            positions_added.append(position_label)

        db.session.commit()

        positions_str = ", ".join(positions_added) if positions_added else "none"
        flash(
            f'Template group "{name}" uploaded with {len(positions_added)} template(s): {positions_str}',
            "success",
        )
        return redirect(url_for("templates"))

    @app.route("/templates/<int:group_id>/delete", methods=["POST"])
    def delete_template(group_id):
        group = TemplateGroup.query.get_or_404(group_id)
        group.is_deleted = True
        # Also soft-delete child templates
        for t in group.templates.all():
            t.is_deleted = True
        db.session.commit()

        flash(f'Template group "{group.name}" deleted.', "success")
        return redirect(url_for("templates"))

    @app.route("/templates/<int:group_id>")
    def template_detail(group_id):
        group = TemplateGroup.query.get_or_404(group_id)
        child_templates = group.templates.filter_by(is_deleted=False).all()
        return render_template("template_detail.html", group=group, templates=child_templates)

    @app.route("/api/templates/<int:group_id>")
    def api_template(group_id):
        group = TemplateGroup.query.get_or_404(group_id)
        return jsonify(group.to_dict())

    # ---------- Participant Data Management ----------

    @app.route("/participants/upload")
    def upload_participants():
        batches = (
            CertificateBatch.query.order_by(CertificateBatch.created_at.desc()).all()
        )
        template_groups = (
            TemplateGroup.query.filter_by(is_deleted=False).all()
        )
        return render_template(
            "participants.html", batches=batches, template_groups=template_groups
        )

    @app.route("/participants/upload", methods=["POST"])
    def upload_participants_post():
        if "participant_file" not in request.files:
            flash("No file selected", "error")
            return redirect(url_for("upload_participants"))

        file = request.files["participant_file"]
        if file.filename == "":
            flash("No file selected", "error")
            return redirect(url_for("upload_participants"))

        batch_name = request.form.get("batch_name", "").strip()
        if not batch_name:
            batch_name = f"Batch {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}"

        template_group_id = request.form.get("template_group_id", type=int)

        # Validate file type
        allowed_extensions = {".csv", ".xlsx", ".xls"}
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in allowed_extensions:
            flash(f"Unsupported file format: {ext}. Allowed: CSV, XLSX, XLS", "error")
            return redirect(url_for("upload_participants"))

        # Save file
        filename = f"{uuid.uuid4().hex}{ext}"
        upload_dir = os.path.join(
            app.root_path, Config.UPLOAD_FOLDER, "participants"
        )
        file_path = os.path.join(upload_dir, filename)
        file.save(file_path)

        # Parse the file
        parse_result = parse_file(file_path)

        if parse_result.errors:
            for error in parse_result.errors[:10]:
                flash(error, "error")

        if parse_result.valid_count == 0:
            flash("No valid participants found in the file.", "error")
            return redirect(url_for("upload_participants"))

        # Create batch and store participants
        batch = CertificateBatch(
            name=batch_name,
            template_group_id=template_group_id,
            status="pending",
            total_count=0,
        )
        db.session.add(batch)
        db.session.flush()

        for parsed in parse_result.participants:
            if not parsed.is_valid():
                continue
            participant = Participant(
                name=parsed.name,
                email=parsed.email,
                prize_position=parsed.prize_position,
                batch_id=batch.id,
            )
            participant.set_extra_data(parsed.extra_data)
            db.session.add(participant)
            batch.total_count += 1

        db.session.commit()

        # Store parse result in session for preview
        flash(
            f"Uploaded {parse_result.valid_count} participants from {parse_result.total_rows} rows.",
            "success",
        )
        return redirect(url_for("batch_detail", batch_id=batch.id))

    @app.route("/batches/<int:batch_id>")
    def batch_detail(batch_id):
        batch = CertificateBatch.query.get_or_404(batch_id)
        participants = batch.participants.order_by(Participant.id).all()
        certificates = batch.certificates.order_by(Certificate.id).all()

        return render_template(
            "batch_detail.html",
            batch=batch,
            participants=participants,
            certificates=certificates,
        )

    @app.route("/batches")
    def batches():
        all_batches = (
            CertificateBatch.query.order_by(CertificateBatch.created_at.desc()).all()
        )
        return render_template("batches.html", batches=all_batches)

    @app.route("/batches/<int:batch_id>/delete", methods=["POST"])
    def delete_batch(batch_id):
        batch = CertificateBatch.query.get_or_404(batch_id)

        # Delete certificate files
        for cert in batch.certificates:
            if cert.file_path:
                full_path = os.path.join(app.root_path, cert.file_path)
                if os.path.exists(full_path):
                    os.remove(full_path)

        # Delete participant files
        cert_folder = os.path.join(
            app.root_path, Config.CERTIFICATE_FOLDER, str(batch.id)
        )
        if os.path.exists(cert_folder):
            shutil.rmtree(cert_folder, ignore_errors=True)

        db.session.delete(batch)
        db.session.commit()

        flash(f'Batch "{batch.name}" deleted.', "success")
        return redirect(url_for("batches"))

    # ---------- Certificate Generation ----------

    @app.route("/batches/<int:batch_id>/generate", methods=["POST"])
    def generate_certificates(batch_id):
        batch = CertificateBatch.query.get_or_404(batch_id)

        if not batch.template_group_id:
            flash("No template group assigned to this batch.", "error")
            return redirect(url_for("batch_detail", batch_id=batch_id))

        group = TemplateGroup.query.get(batch.template_group_id)
        if not group or group.is_deleted:
            flash("Assigned template group not found or has been deleted.", "error")
            return redirect(url_for("batch_detail", batch_id=batch_id))

        # Update batch status
        batch.status = "generating"
        db.session.commit()

        participants = batch.participants.all()
        generated_count = 0
        failed_count = 0

        cert_output_dir = os.path.join(
            app.root_path, Config.CERTIFICATE_FOLDER, str(batch.id)
        )
        os.makedirs(cert_output_dir, exist_ok=True)

        for participant in participants:
            try:
                # Find the correct template for this participant's position
                template = group.get_template_for_position(participant.prize_position)
                if not template:
                    raise ValueError(f"No template found for position: {participant.prize_position}")

                template_path = os.path.join(app.root_path, template.file_path)
                if not os.path.exists(template_path):
                    raise FileNotFoundError(f"Template file not found: {template_path}")

                placeholders = template.get_placeholders()

                # Prepare data for the certificate
                extra = participant.get_extra_data()
                data = {
                    "participant_name": participant.name,
                    "email": participant.email,
                    "prize_position": participant.prize_position,
                }

                # Pull event_name and date from extra_data columns
                # Try common column names for event
                event_name = (
                    extra.get("Event")
                    or extra.get("event")
                    or extra.get("Event Name")
                    or extra.get("event_name")
                    or batch.name  # fallback to batch name
                )
                data["event_name"] = event_name
                data["Event"] = event_name

                # Try common column names for date
                date_val = (
                    extra.get("Date")
                    or extra.get("date")
                    or extra.get("Event Date")
                    or extra.get("event_date")
                    or ""
                )
                data["date"] = date_val
                data["Date"] = date_val

                # Add all other extra data
                data.update(extra)

                # If placeholders are defined, only include those fields
                if placeholders:
                    filtered_data = {}
                    for ph in placeholders:
                        field_name = ph.get("field", ph) if isinstance(ph, dict) else ph
                        if field_name in data:
                            filtered_data[field_name] = data[field_name]
                        else:
                            filtered_data[field_name] = f"[{field_name}]"
                    data = filtered_data

                # Generate certificate
                cert_filename = f"{participant.id}_{uuid.uuid4().hex}.pdf"
                cert_path = os.path.join(cert_output_dir, cert_filename)

                generate_certificate(
                    template_path=template_path,
                    template_type=template.file_type,
                    output_path=cert_path,
                    data=data,
                    placeholders=placeholders if isinstance(placeholders, list) and placeholders and isinstance(placeholders[0], dict) else None,
                )

                relative_path = os.path.join(
                    Config.CERTIFICATE_FOLDER, str(batch.id), cert_filename
                )

                # Check for existing certificate for this participant
                existing_cert = Certificate.query.filter_by(
                    batch_id=batch.id, participant_id=participant.id
                ).first()

                if existing_cert:
                    existing_cert.file_path = relative_path
                    existing_cert.template_id = template.id
                    existing_cert.status = "generated"
                    existing_cert.error_message = ""
                else:
                    cert = Certificate(
                        batch_id=batch.id,
                        participant_id=participant.id,
                        template_id=template.id,
                        file_path=relative_path,
                        status="generated",
                    )
                    db.session.add(cert)

                generated_count += 1

            except Exception as e:
                logger.exception(f"Failed to generate certificate for {participant.name}")
                failed_count += 1

                existing_cert = Certificate.query.filter_by(
                    batch_id=batch.id, participant_id=participant.id
                ).first()

                if existing_cert:
                    existing_cert.status = "failed"
                    existing_cert.error_message = str(e)
                else:
                    # Use first available template id for error records
                    fallback_template = group.templates.first()
                    cert = Certificate(
                        batch_id=batch.id,
                        participant_id=participant.id,
                        template_id=fallback_template.id if fallback_template else 0,
                        status="failed",
                        error_message=str(e),
                    )
                    db.session.add(cert)

        # Update batch — reset sent_count since certificates are freshly generated
        batch.generated_count = generated_count
        batch.sent_count = 0
        batch.failed_count = failed_count
        batch.status = "generated" if failed_count == 0 else "completed" if generated_count > 0 else "failed"
        batch.error_message = ""

        if failed_count > 0 and generated_count > 0:
            batch.status = "completed"
            batch.error_message = f"{generated_count} generated, {failed_count} failed"

        db.session.commit()

        flash(
            f"Generated {generated_count} certificates. {failed_count} failed.",
            "success" if failed_count == 0 else "warning",
        )
        return redirect(url_for("batch_detail", batch_id=batch_id))

    # ---------- Certificate Distribution ----------

    @app.route("/batches/<int:batch_id>/distribute", methods=["POST"])
    def distribute_certificates(batch_id):
        batch = CertificateBatch.query.get_or_404(batch_id)

        sender_email = request.form.get("sender_email", "").strip()
        email_sender = EmailSender(sender_email=sender_email if sender_email else None)
        if not email_sender.is_configured():
            flash(
                "Email sender is not configured. Please set MAIL_USERNAME and MAIL_PASSWORD in .env file.",
                "error",
            )
            return redirect(url_for("batch_detail", batch_id=batch_id))

        certificates = Certificate.query.filter_by(
            batch_id=batch.id, status="generated"
        ).all()

        if not certificates:
            flash("No generated certificates to distribute.", "warning")
            return redirect(url_for("batch_detail", batch_id=batch_id))

        batch.status = "distributing"
        db.session.commit()

        # Run distribution in a background thread
        import threading
        
        def _run_distribution(app_context, batch_id_val, sender_email_val, cert_ids):
            with app_context:
                from models import CertificateBatch, Certificate, db
                from utils.email_sender import EmailSender
                import os
                from datetime import datetime, timezone

                batch = CertificateBatch.query.get(batch_id_val)
                if not batch:
                    return

                email_sender = EmailSender(sender_email=sender_email_val if sender_email_val else None)
                email_sender.connect()

                sent_count = 0
                failed_count = 0

                for cid in cert_ids:
                    cert = Certificate.query.get(cid)
                    if not cert:
                        continue
                    try:
                        participant = cert.participant
                        if not participant:
                            cert.status = "failed"
                            cert.error_message = "Participant not found"
                            failed_count += 1
                            continue

                        cert_path = os.path.join(app.root_path, cert.file_path) if cert.file_path else ""
                        if not cert_path or not os.path.exists(cert_path):
                            cert.status = "failed"
                            cert.error_message = "Certificate file not found"
                            failed_count += 1
                            continue

                        # Get event name from participant's extra data
                        extra = participant.get_extra_data()
                        event_name = (
                            extra.get("Event")
                            or extra.get("event")
                            or extra.get("Event Name")
                            or extra.get("event_name")
                            or batch.name
                        )

                        success, message = email_sender.send_certificate(
                            recipient_name=participant.name,
                            recipient_email=participant.email,
                            certificate_path=cert_path,
                            prize_position=participant.prize_position,
                            event_name=event_name,
                        )

                        if success:
                            cert.status = "sent"
                            cert.sent_at = datetime.now(timezone.utc)
                            sent_count += 1
                        else:
                            cert.status = "failed"
                            cert.error_message = message
                            failed_count += 1

                    except Exception as e:
                        logger.exception(f"Error distributing certificate ID {cert.id}")
                        cert.status = "failed"
                        cert.error_message = str(e)
                        failed_count += 1
                        
                    # Commit progress per certificate to show live updates
                    db.session.commit()

                email_sender.disconnect()

                # Final update on batch
                batch.sent_count = sent_count
                batch.failed_count = (batch.failed_count or 0) + failed_count

                if failed_count == 0:
                    batch.status = "completed"
                    batch.completed_at = datetime.now(timezone.utc)
                elif sent_count > 0:
                    batch.status = "completed"
                    batch.completed_at = datetime.now(timezone.utc)
                    batch.error_message = f"{sent_count} sent, {failed_count} failed"
                else:
                    batch.status = "failed"
                    batch.error_message = f"All {failed_count} emails failed"

                db.session.commit()

        cert_ids = [c.id for c in certificates]
        thread = threading.Thread(
            target=_run_distribution,
            args=(app.app_context(), batch.id, sender_email, cert_ids)
        )
        thread.daemon = True
        thread.start()

        flash(
            f"Email distribution for {len(certificates)} certificates has started in the background. The page will auto-refresh.",
            "info"
        )
        return redirect(url_for("batch_detail", batch_id=batch_id))

    # ---------- Certificate Download ----------

    @app.route("/certificates/<int:cert_id>/download")
    def download_certificate(cert_id):
        cert = Certificate.query.get_or_404(cert_id)
        if not cert.file_path:
            flash("Certificate file not found.", "error")
            return redirect(url_for("batch_detail", batch_id=cert.batch_id))

        full_path = os.path.join(app.root_path, cert.file_path)
        if not os.path.exists(full_path):
            flash("Certificate file not found on disk.", "error")
            return redirect(url_for("batch_detail", batch_id=cert.batch_id))

        return send_file(
            full_path,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=f"certificate_{cert.participant.name.replace(' ', '_')}.pdf"
            if cert.participant
            else "certificate.pdf",
        )

    # ---------- Sample Template Download ----------

    @app.route("/sample-template")
    def download_sample_template():
        """Generate and download a sample certificate template PNG."""
        from PIL import Image, ImageDraw, ImageFont

        width, height = 1200, 800
        img = Image.new("RGB", (width, height), (255, 255, 255))
        draw = ImageDraw.Draw(img)

        # ---------- Helper ----------
        def _font(size, bold=False):
            candidates = [
                "/System/Library/Fonts/Helvetica.ttc",
                "/System/Library/Fonts/Helvetica.ttf",
                "/Library/Fonts/Arial.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            ]
            if bold:
                bold_candidates = [
                    "/System/Library/Fonts/Helvetica-Bold.ttf",
                    "/Library/Fonts/Arial Bold.ttf",
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                ]
                candidates = bold_candidates + candidates
            for p in candidates:
                if os.path.exists(p):
                    try:
                        return ImageFont.truetype(p, size)
                    except (IOError, OSError):
                        pass
            return ImageFont.load_default()

        # ---------- Colors ----------
        primary = (102, 126, 234)       # #667EEA
        dark = (33, 37, 41)
        gray = (108, 117, 125)
        light_gray = (241, 243, 247)
        accent_gold = (212, 175, 55)

        # ---------- Background ----------
        draw.rectangle([(0, 0), (width, height)], fill=(248, 249, 252))

        # ---------- Outer decorative border ----------
        margin = 20
        draw.rectangle(
            [(margin, margin), (width - margin, height - margin)],
            outline=primary,
            width=3,
        )
        # Inner border
        margin2 = 30
        draw.rectangle(
            [(margin2, margin2), (width - margin2, height - margin2)],
            outline=primary,
            width=1,
        )

        # ---------- Top accent bar ----------
        draw.rectangle([(margin2, margin2), (width - margin2, margin2 + 8)], fill=primary)
        # Bottom accent bar
        draw.rectangle([(margin2, height - margin2 - 8), (width - margin2, height - margin2)], fill=primary)

        # ---------- Corner decorative elements ----------
        corner_size = 40
        for cx, cy in [(margin2, margin2), (width - margin2, margin2), (margin2, height - margin2), (width - margin2, height - margin2)]:
            draw.ellipse([(cx - 6, cy - 6), (cx + 6, cy + 6)], fill=accent_gold)

        # ---------- Title ----------
        title_font = _font(42, bold=True)
        title_text = "CERTIFICATE OF ACHIEVEMENT"
        bbox = draw.textbbox((0, 0), title_text, font=title_font)
        draw.text(
            ((width - (bbox[2] - bbox[0])) // 2, 100),
            title_text,
            fill=primary,
            font=title_font,
        )

        # ---------- Decorative line under title ----------
        line_y = 155
        line_width = 300
        draw.line(
            [(width // 2 - line_width // 2, line_y), (width // 2 + line_width // 2, line_y)],
            fill=accent_gold,
            width=2,
        )

        # ---------- "This certifies that" ----------
        sub_font = _font(18)
        sub_text = "This certifies that"
        bbox = draw.textbbox((0, 0), sub_text, font=sub_font)
        draw.text(
            ((width - (bbox[2] - bbox[0])) // 2, 190),
            sub_text,
            fill=gray,
            font=sub_font,
        )

        # ---------- Placeholder: Participant Name ----------
        ph_name_y = 250
        name_font = _font(48, bold=True)
        name_label = "[participant_name]"
        bbox = draw.textbbox((0, 0), name_label, font=name_font)
        ph_box_pad = 20
        ph_box_x1 = (width - (bbox[2] - bbox[0])) // 2 - ph_box_pad
        ph_box_x2 = (width + (bbox[2] - bbox[0])) // 2 + ph_box_pad
        ph_box_y1 = ph_name_y - 10
        ph_box_y2 = ph_name_y + (bbox[3] - bbox[1]) + 10
        draw.rounded_rectangle(
            [(ph_box_x1, ph_box_y1), (ph_box_x2, ph_box_y2)],
            radius=8,
            fill=light_gray,
            outline=primary,
            width=2,
        )
        draw.text(
            ((width - (bbox[2] - bbox[0])) // 2, ph_name_y),
            name_label,
            fill=primary,
            font=name_font,
        )

        # ---------- "for achieving" ----------
        ach_font = _font(18)
        ach_text = "for achieving"
        bbox = draw.textbbox((0, 0), ach_text, font=ach_font)
        draw.text(
            ((width - (bbox[2] - bbox[0])) // 2, 340),
            ach_text,
            fill=gray,
            font=ach_font,
        )

        # ---------- Placeholder: Prize Position ----------
        prize_y = 390
        prize_font = _font(30, bold=True)
        prize_label = "[prize_position]"
        bbox = draw.textbbox((0, 0), prize_label, font=prize_font)
        ph_box_x1 = (width - (bbox[2] - bbox[0])) // 2 - ph_box_pad
        ph_box_x2 = (width + (bbox[2] - bbox[0])) // 2 + ph_box_pad
        ph_box_y1 = prize_y - 8
        ph_box_y2 = prize_y + (bbox[3] - bbox[1]) + 8
        draw.rounded_rectangle(
            [(ph_box_x1, ph_box_y1), (ph_box_x2, ph_box_y2)],
            radius=8,
            fill=light_gray,
            outline=primary,
            width=2,
        )
        draw.text(
            ((width - (bbox[2] - bbox[0])) // 2, prize_y),
            prize_label,
            fill=primary,
            font=prize_font,
        )

        # ---------- "at" ----------
        at_font = _font(16)
        at_text = "at"
        bbox = draw.textbbox((0, 0), at_text, font=at_font)
        draw.text(
            ((width - (bbox[2] - bbox[0])) // 2, 450),
            at_text,
            fill=gray,
            font=at_font,
        )

        # ---------- Placeholder: Event ----------
        event_y = 490
        event_font = _font(26, bold=True)
        event_label = "[event_name]"
        bbox = draw.textbbox((0, 0), event_label, font=event_font)
        ph_box_x1 = (width - (bbox[2] - bbox[0])) // 2 - ph_box_pad
        ph_box_x2 = (width + (bbox[2] - bbox[0])) // 2 + ph_box_pad
        ph_box_y1 = event_y - 8
        ph_box_y2 = event_y + (bbox[3] - bbox[1]) + 8
        draw.rounded_rectangle(
            [(ph_box_x1, ph_box_y1), (ph_box_x2, ph_box_y2)],
            radius=8,
            fill=light_gray,
            outline=primary,
            width=2,
        )
        draw.text(
            ((width - (bbox[2] - bbox[0])) // 2, event_y),
            event_label,
            fill=primary,
            font=event_font,
        )

        # ---------- Placeholder: Date ----------
        date_font = _font(18)
        date_label = "[date]"
        bbox = draw.textbbox((0, 0), date_label, font=date_font)
        ph_box_x1 = (width - (bbox[2] - bbox[0])) // 2 - 12
        ph_box_x2 = (width + (bbox[2] - bbox[0])) // 2 + 12
        ph_box_y1 = 555 - 6
        ph_box_y2 = 555 + (bbox[3] - bbox[1]) + 6
        draw.rounded_rectangle(
            [(ph_box_x1, ph_box_y1), (ph_box_x2, ph_box_y2)],
            radius=6,
            fill=light_gray,
            outline=primary,
            width=1,
        )
        draw.text(
            ((width - (bbox[2] - bbox[0])) // 2, 555),
            date_label,
            fill=primary,
            font=date_font,
        )

        # ---------- Footer ----------
        footer_font = _font(14)
        footer_text = "Presented by CertiGenius \u2022 Automated Certificate Platform"
        bbox = draw.textbbox((0, 0), footer_text, font=footer_font)
        draw.text(
            ((width - (bbox[2] - bbox[0])) // 2, height - 80),
            footer_text,
            fill=gray,
            font=footer_font,
        )

        # ---------- Save to BytesIO ----------
        output = io.BytesIO()
        img.save(output, format="PNG")
        output.seek(0)

        return send_file(
            output,
            mimetype="image/png",
            as_attachment=True,
            download_name="sample_certificate_template.png",
        )

    # ---------- Sample Excel Download ----------

    @app.route("/sample-excel")
    def download_sample_excel():
        """Generate and download a sample Excel file with participant data."""
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Participants"

        # Headers
        headers = ["Name", "Email", "Prize Position", "Event", "Date"]
        ws.append(headers)

        # Sample data
        sample_data = [
            ["John Doe", "john@example.com", "1st", "Annual Conference 2024", "2024-12-01"],
            ["Jane Smith", "jane@example.com", "2nd", "Annual Conference 2024", "2024-12-01"],
            ["Bob Johnson", "bob@example.com", "3rd", "Annual Conference 2024", "2024-12-01"],
            ["Alice Brown", "alice@example.com", "Participation", "Annual Conference 2024", "2024-12-01"],
            ["Charlie Wilson", "charlie@example.com", "1st", "Workshop Series 2024", "2024-11-15"],
            ["Diana Garcia", "diana@example.com", "2nd", "Workshop Series 2024", "2024-11-15"],
            ["Edward Lee", "edward@example.com", "Participation", "Hackathon Q4", "2024-10-20"],
            ["Fiona Chen", "fiona@example.com", "1st", "Hackathon Q4", "2024-10-20"],
        ]

        for row in sample_data:
            ws.append(row)

        # Style headers
        from openpyxl.styles import Font, PatternFill
        header_fill = PatternFill(start_color="667EEA", end_color="667EEA", fill_type="solid")
        header_font = Font(color="FFFFFF", bold=True, size=11)
        for cell in ws[1]:
            cell.fill = header_fill
            cell.font = header_font

        # Auto-adjust column widths
        for col in ws.columns:
            max_length = 0
            col_letter = col[0].column_letter
            for cell in col:
                if cell.value:
                    max_length = max(max_length, len(str(cell.value)))
            ws.column_dimensions[col_letter].width = max_length + 4

        # Save to BytesIO
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)

        return send_file(
            output,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name="sample_participants.xlsx",
        )

    # ---------- API endpoints for AJAX ----------

    @app.route("/api/batches/<int:batch_id>/status")
    def api_batch_status(batch_id):
        batch = CertificateBatch.query.get_or_404(batch_id)
        return jsonify(batch.to_dict())

    @app.route("/api/certificates/<int:cert_id>/status")
    def api_certificate_status(cert_id):
        cert = Certificate.query.get_or_404(cert_id)
        return jsonify(cert.to_dict())

    # ---------- Error Handlers ----------

    @app.errorhandler(404)
    def not_found(e):
        return render_template("error.html", error_code=404, error_message="Page not found"), 404

    @app.errorhandler(500)
    def server_error(e):
        return render_template("error.html", error_code=500, error_message="Internal server error"), 500


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, host="0.0.0.0", port=5000)
