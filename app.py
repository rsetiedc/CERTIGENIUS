"""
CertiGenius - Automated Certificate Generation and Distribution Platform
Main Flask application.
"""

import json
import logging
import os
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
from models import Certificate, CertificateBatch, Participant, Template, db
from utils.certificate_generator import generate_certificate
from utils.email_sender import EmailSender
from utils.excel_parser import parse_file

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


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
        template_count = Template.query.filter_by(is_deleted=False).count()
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
        all_templates = (
            Template.query.filter_by(is_deleted=False)
            .order_by(Template.created_at.desc())
            .all()
        )
        return render_template("templates.html", templates=all_templates)

    @app.route("/templates/upload", methods=["POST"])
    def upload_template():
        if "template_file" not in request.files:
            flash("No file selected", "error")
            return redirect(url_for("templates"))

        file = request.files["template_file"]
        if file.filename == "":
            flash("No file selected", "error")
            return redirect(url_for("templates"))

        name = request.form.get("name", "").strip()
        if not name:
            name = os.path.splitext(file.filename)[0]

        # Validate file type
        allowed_extensions = {".png", ".jpg", ".jpeg", ".pdf"}
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in allowed_extensions:
            flash(
                f"Unsupported file format: {ext}. Allowed: PNG, JPG, JPEG, PDF",
                "error",
            )
            return redirect(url_for("templates"))

        # Parse placeholder fields from form
        placeholder_fields_str = request.form.get("placeholder_fields", "")
        placeholder_fields = []
        if placeholder_fields_str:
            placeholder_fields = [
                f.strip() for f in placeholder_fields_str.split(",") if f.strip()
            ]

        # Save file
        filename = f"{uuid.uuid4().hex}{ext}"
        upload_dir = os.path.join(
            app.root_path, Config.UPLOAD_FOLDER, "templates"
        )
        file_path = os.path.join(upload_dir, filename)
        file.save(file_path)

        template = Template(
            name=name,
            description=request.form.get("description", ""),
            file_path=os.path.join(Config.UPLOAD_FOLDER, "templates", filename),
            file_type=ext[1:],  # Remove the dot
        )
        template.set_placeholders(placeholder_fields)

        db.session.add(template)
        db.session.commit()

        flash(f'Template "{name}" uploaded successfully!', "success")
        return redirect(url_for("templates"))

    @app.route("/templates/<int:template_id>/delete", methods=["POST"])
    def delete_template(template_id):
        template = Template.query.get_or_404(template_id)
        template.is_deleted = True
        db.session.commit()

        flash(f'Template "{template.name}" deleted.', "success")
        return redirect(url_for("templates"))

    @app.route("/templates/<int:template_id>")
    def template_detail(template_id):
        template = Template.query.get_or_404(template_id)
        return render_template("template_detail.html", template=template)

    @app.route("/api/templates/<int:template_id>")
    def api_template(template_id):
        template = Template.query.get_or_404(template_id)
        return jsonify(template.to_dict())

    # ---------- Participant Data Management ----------

    @app.route("/participants/upload")
    def upload_participants():
        batches = (
            CertificateBatch.query.order_by(CertificateBatch.created_at.desc()).all()
        )
        templates_list = (
            Template.query.filter_by(is_deleted=False).all()
        )
        return render_template(
            "participants.html", batches=batches, templates=templates_list
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

        template_id = request.form.get("template_id", type=int)

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
            template_id=template_id,
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

        if not batch.template_id:
            flash("No template assigned to this batch.", "error")
            return redirect(url_for("batch_detail", batch_id=batch_id))

        template = Template.query.get(batch.template_id)
        if not template or template.is_deleted:
            flash("Assigned template not found or has been deleted.", "error")
            return redirect(url_for("batch_detail", batch_id=batch_id))

        template_path = os.path.join(app.root_path, template.file_path)
        if not os.path.exists(template_path):
            flash("Template file not found on disk.", "error")
            return redirect(url_for("batch_detail", batch_id=batch_id))

        # Update batch status
        batch.status = "generating"
        db.session.commit()

        participants = batch.participants.all()
        placeholders = template.get_placeholders()
        generated_count = 0
        failed_count = 0

        cert_output_dir = os.path.join(
            app.root_path, Config.CERTIFICATE_FOLDER, str(batch.id)
        )
        os.makedirs(cert_output_dir, exist_ok=True)

        for participant in participants:
            try:
                # Prepare data for the certificate
                data = {
                    "participant_name": participant.name,
                    "email": participant.email,
                    "prize_position": participant.prize_position,
                }

                # Add extra data fields
                extra = participant.get_extra_data()
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
                    cert = Certificate(
                        batch_id=batch.id,
                        participant_id=participant.id,
                        template_id=template.id,
                        status="failed",
                        error_message=str(e),
                    )
                    db.session.add(cert)

        # Update batch
        batch.generated_count = generated_count
        batch.failed_count = failed_count
        batch.status = "generated" if failed_count == 0 else "completed" if generated_count > 0 else "failed"

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

        email_sender = EmailSender()
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

        sent_count = 0
        failed_count = 0
        event_name = batch.name

        for cert in certificates:
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

        # Update batch
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

        flash(
            f"Distributed {sent_count} certificates via email. {failed_count} failed.",
            "success" if failed_count == 0 else "warning",
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
