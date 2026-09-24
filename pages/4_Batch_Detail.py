"""
CertiGenius — Batch Detail Page
View batch participants, generate certificates, download, and distribute via email.
"""
import io
import os
import uuid
import zipfile
from datetime import datetime, timezone

import streamlit as st

from sqlalchemy.orm import joinedload

from config import Config
from models import (
    Certificate,
    CertificateBatch,
    Participant,
    Template,
    TemplateGroup,
    Base,
)
from utils.certificate_generator import generate_certificate
from utils.email_sender import EmailSender
from utils.db import get_session, init_connection

st.set_page_config(page_title="Batch Detail — CertiGenius", page_icon="📦", layout="wide")

engine = init_connection()
Base.metadata.create_all(engine)


def get_batch(batch_id):
    session = get_session()
    try:
        return session.query(CertificateBatch).options(
            joinedload(CertificateBatch.template_group)
        ).get(batch_id)
    finally:
        session.close()


def get_participants(batch_id):
    session = get_session()
    try:
        return session.query(Participant).filter_by(batch_id=batch_id).order_by(Participant.id).all()
    finally:
        session.close()


def get_certificates(batch_id):
    session = get_session()
    try:
        return session.query(Certificate).options(
            joinedload(Certificate.participant)
        ).filter_by(batch_id=batch_id).order_by(Certificate.id).all()
    finally:
        session.close()


def status_badge(status):
    badges = {
        "pending": "🟡 Pending",
        "generating": "🔵 Generating",
        "generated": "🟢 Generated",
        "sent": "✉️ Sent",
        "failed": "❌ Failed",
    }
    return badges.get(status, status)


# ---- Read batch_id from query params ----
batch_id_raw = st.query_params.get("batch_id")
batch_id = int(batch_id_raw) if batch_id_raw else None
if not batch_id:
    st.title("📦 Batch Detail")
    st.warning("No batch ID provided. Enter one below or go to Batches page.")
    bid = st.number_input("Batch ID:", min_value=1, step=1)
    if st.button("🔍 View Batch", type="primary"):
        st.query_params["batch_id"] = str(bid)
        st.rerun()
    st.page_link("pages/3_Batches.py", label="← Back to Batches")
    st.stop()

st.title(f"📦 Batch #{batch_id}")

batch = get_batch(batch_id)
if not batch:
    st.error("Batch not found.")
    st.page_link("pages/3_Batches.py", label="← Back to Batches")
    st.stop()

# ---- Batch Info ----
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Name", batch.name)
with col2:
    st.metric("Status", status_badge(batch.status))
with col3:
    st.metric("Participants", batch.total_count)
with col4:
    created_str = batch.created_at.strftime("%b %d, %Y %H:%M") if batch.created_at else "—"
    st.metric("Created", created_str)

if batch.template_group:
    st.info(f"📄 Template Group: **{batch.template_group.name}**")

# Show event type
if batch.event_type == "isa":
    st.info("🏛️ Event Type: **ISA Event** — Using ISA certificate templates")
else:
    st.info("📌 Event Type: **Non-ISA Event** — Using Non-ISA certificate templates")

# ---- Participants ----
st.markdown("---")
st.subheader("👥 Participants")

participants = get_participants(batch_id)
if participants:
    pdata = []
    for p in participants:
        extra = p.get_extra_data()
        extra_str = ", ".join(f"{k}: {v}" for k, v in extra.items() if v) if extra else ""
        pdata.append({
            "ID": p.id,
            "Name": p.name,
            "Email": p.email,
            "Position": p.prize_position,
            "Extra": extra_str,
        })
    st.dataframe(pdata, use_container_width=True, hide_index=True)
else:
    st.caption("No participants in this batch.")

# ---- Certificates ----
st.markdown("---")
st.subheader("📜 Certificates")

certificates = get_certificates(batch_id)

if certificates:
    cdata = []
    for c in certificates:
        cdata.append({
            "ID": c.id,
            "Participant": c.participant.name if c.participant else "—",
            "Status": status_badge(c.status),
            "Error": c.error_message or "",
            "File": "✅" if c.file_path and os.path.exists(os.path.join(os.getcwd(), c.file_path)) else "—",
        })
    st.dataframe(cdata, use_container_width=True, hide_index=True)
else:
    st.caption("No certificates yet. Generate them below!")

# ---- Actions ----
st.markdown("---")
st.subheader("⚡ Actions")

act_col1, act_col2, act_col3, act_col4 = st.columns(4)

# 1. Generate Certificates
with act_col1:
    can_generate = batch.status not in ("generating", "distributing")
    gen_btn = st.button(
        "🔨 Generate Certificates",
        use_container_width=True,
        type="primary",
        disabled=not can_generate,
        help="Generate certificates for all participants" if can_generate else "Wait for current operation to finish",
    )

    if gen_btn:
        if not batch.template_group_id:
            st.error("No template group assigned to this batch.")
            st.stop()

        group = get_session()
        try:
            tg = group.query(TemplateGroup).get(batch.template_group_id)
            if not tg or tg.is_deleted:
                st.error("Template group not found or deleted.")
                st.stop()
        finally:
            group.close()

        # Determine template folder based on event type
        event_type = batch.event_type or "non_isa"
        if event_type == "isa":
            built_in_template_dir = os.path.join(os.getcwd(), "uploads", "templates", "isa_events")
        else:
            built_in_template_dir = os.path.join(os.getcwd(), "uploads", "templates", "non_isa_events")

        # Update status
        session = get_session()
        try:
            b = session.query(CertificateBatch).get(batch.id)
            b.status = "generating"
            session.commit()
        finally:
            session.close()

        # Create progress bar
        progress_bar = st.progress(0, text="Generating certificates...")
        status_text = st.empty()

        participants_list = get_participants(batch_id)
        total = len(participants_list)
        generated = 0
        failed = 0

        cert_output_dir = os.path.join(os.getcwd(), Config.CERTIFICATE_FOLDER, str(batch.id))
        os.makedirs(cert_output_dir, exist_ok=True)

        session = get_session()
        try:
            tg = session.query(TemplateGroup).get(batch.template_group_id)

            for idx, participant in enumerate(participants_list):
                try:
                    template = tg.get_template_for_position(participant.prize_position)
                    if not template:
                        raise ValueError(f"No template for position: {participant.prize_position}")

                    # Use built-in ISA/non-ISA templates if available
                    built_in_template_path = None
                    if os.path.isdir(built_in_template_dir):
                        position = (participant.prize_position or "").strip().lower()
                        # Map position to template filename: 1.png, 2.png, etc.
                        pos_to_file = {
                            "1st": "1.png", "first": "1.png",
                            "2nd": "2.png", "second": "2.png",
                        }
                        template_filename = pos_to_file.get(position, "1.png")
                        candidate = os.path.join(built_in_template_dir, template_filename)
                        if os.path.exists(candidate):
                            built_in_template_path = candidate

                    if built_in_template_path:
                        template_path = built_in_template_path
                        placeholders = None  # Use auto-detection for built-in templates
                    else:
                        template_path = os.path.join(os.getcwd(), template.file_path)
                        if not os.path.exists(template_path):
                            raise FileNotFoundError(f"Template not found: {template_path}")
                        placeholders = template.get_placeholders()

                    extra = participant.get_extra_data()

                    data = {
                        "participant_name": participant.name,
                        "email": participant.email,
                        "prize_position": participant.prize_position,
                    }

                    event_name = (
                        extra.get("Event") or extra.get("event")
                        or extra.get("Event Name") or extra.get("event_name")
                        or batch.name
                    )
                    data["event_name"] = event_name
                    data["Event"] = event_name

                    date_val = (
                        extra.get("Date") or extra.get("date")
                        or extra.get("Event Date") or extra.get("event_date")
                        or ""
                    )
                    data["date"] = date_val
                    data["Date"] = date_val
                    data.update(extra)

                    if placeholders:
                        filtered = {}
                        for ph in placeholders:
                            fn = ph.get("field", ph) if isinstance(ph, dict) else ph
                            filtered[fn] = data.get(fn, f"[{fn}]")
                        data = filtered

                    cert_filename = f"{participant.id}_{uuid.uuid4().hex}.pdf"
                    relative_path = os.path.join(Config.CERTIFICATE_FOLDER, str(batch.id), cert_filename)

                    # Check for existing cert
                    existing = (
                        session.query(Certificate)
                        .filter_by(batch_id=batch.id, participant_id=participant.id)
                        .first()
                    )
                    if existing:
                        existing.file_path = relative_path
                        existing.template_id = template.id
                        existing.status = "generating"
                        existing.error_message = ""
                    else:
                        existing = Certificate(
                            batch_id=batch.id,
                            participant_id=participant.id,
                            template_id=template.id,
                            file_path=relative_path,
                            status="generating",
                        )
                        session.add(existing)
                    session.commit()

                    # Verification URL (using Streamlit app URL)
                    base_url = st.query_params.get("base_url", "")
                    if not base_url:
                        # Try to detect from streamlit
                        try:
                            from streamlit.runtime.scriptrunner import get_script_run_ctx
                            base_url = st.secrets.get("APP_URL", "")
                        except Exception:
                            base_url = ""
                    
                    verify_url = f"{base_url}/Verify?cert_id={existing.id}" if base_url else ""
                    
                    qr_metadata = (
                        f"Certificate ID: {existing.id}\n"
                        f"Awarded To: {participant.name}\n"
                        f"Event: {event_name}\n"
                        f"Achievement: {participant.prize_position}\n"
                        f"Date: {date_val}\n"
                    )
                    if verify_url:
                        qr_metadata += f"Verify at: {verify_url}"

                    cert_path = os.path.join(os.getcwd(), relative_path)
                    generate_certificate(
                        template_path=template_path,
                        template_type=template.file_type,
                        output_path=cert_path,
                        data=data,
                        placeholders=placeholders if isinstance(placeholders, list) and placeholders and isinstance(placeholders[0], dict) else None,
                        qr_data=qr_metadata,
                    )

                    existing.status = "generated"
                    generated += 1

                except Exception as e:
                    failed += 1
                    existing = (
                        session.query(Certificate)
                        .filter_by(batch_id=batch.id, participant_id=participant.id)
                        .first()
                    )
                    if existing:
                        existing.status = "failed"
                        existing.error_message = str(e)

                progress_bar.progress((idx + 1) / total, text=f"Processing {idx + 1}/{total}...")
                status_text.text(f"✅ {generated} generated | ❌ {failed} failed")
                session.commit()

            # Finalize batch
            b = session.query(CertificateBatch).get(batch.id)
            b.generated_count = generated
            b.sent_count = 0
            b.failed_count = failed
            b.status = "generated" if failed == 0 else "completed" if generated > 0 else "failed"
            b.error_message = f"{generated} generated, {failed} failed" if failed > 0 else ""
            session.commit()

        except Exception as e:
            session.rollback()
            st.error(f"Generation error: {e}")
        finally:
            session.close()

        progress_bar.progress(1.0, text="Done!")
        status_text.success(f"✅ Completed: {generated} generated, {failed} failed")

        if "certificates" in st.session_state:
            del st.session_state["certificates"]

        st.rerun()

# 2. Distribute via Email
with act_col2:
    can_distribute = batch.status in ("generated", "completed") and batch.generated_count > 0
    dist_btn = st.button(
        "✉️ Distribute via Email",
        use_container_width=True,
        type="primary",
        disabled=not can_distribute,
        help="Send certificates via email to participants" if can_distribute else "Generate certificates first",
    )

    if dist_btn:
        email_sender = EmailSender()
        if not email_sender.is_configured():
            st.error(
                "Email not configured. Set MAIL_USERNAME and MAIL_PASSWORD "
                "in .streamlit/secrets.toml or Streamlit Cloud secrets."
            )
            st.stop()

        certs = get_certificates(batch_id)
        eligible = [c for c in certs if c.status in ("generated", "failed") and c.file_path]
        if not eligible:
            st.warning("No eligible certificates to distribute.")
            st.stop()

        progress_bar = st.progress(0, text="Sending emails...")
        status_text = st.empty()

        session = get_session()
        try:
            b = session.query(CertificateBatch).get(batch.id)
            b.status = "distributing"
            session.commit()
        finally:
            session.close()

        sent_count = 0
        failed_count = 0
        total_eligible = len(eligible)

        for idx, cert in enumerate(eligible):
            session = get_session()
            try:
                c = session.query(Certificate).get(cert.id)
                participant = c.participant
                if not participant:
                    c.status = "failed"
                    c.error_message = "Participant not found"
                    failed_count += 1
                    session.commit()
                    continue

                cert_path = os.path.join(os.getcwd(), c.file_path)
                if not os.path.exists(cert_path):
                    c.status = "failed"
                    c.error_message = "Certificate file not found"
                    failed_count += 1
                    session.commit()
                    continue

                extra = participant.get_extra_data()
                event_name = (
                    extra.get("Event") or extra.get("event")
                    or extra.get("Event Name") or extra.get("event_name")
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
                    c.status = "sent"
                    c.sent_at = datetime.now(timezone.utc)
                    sent_count += 1
                else:
                    c.status = "failed"
                    c.error_message = message
                    failed_count += 1

                session.commit()
            except Exception as e:
                failed_count += 1
            finally:
                session.close()

            progress_bar.progress((idx + 1) / total_eligible, text=f"Sending {idx + 1}/{total_eligible}...")
            status_text.text(f"✉️ {sent_count} sent | ❌ {failed_count} failed")

        # Final update
        session = get_session()
        try:
            b = session.query(CertificateBatch).get(batch.id)
            b.sent_count = (b.sent_count or 0) + sent_count
            b.failed_count = (b.failed_count or 0) + failed_count
            if failed_count == 0:
                b.status = "completed"
                b.completed_at = datetime.now(timezone.utc)
            elif sent_count > 0:
                b.status = "completed"
                b.completed_at = datetime.now(timezone.utc)
                b.error_message = f"{sent_count} sent, {failed_count} failed"
            else:
                b.status = "failed"
                b.error_message = f"All {failed_count} emails failed"
            session.commit()
        finally:
            session.close()

        progress_bar.progress(1.0, text="Done!")
        status_text.success(f"✅ {sent_count} sent, {failed_count} failed")
        st.rerun()

# 3. Download All as ZIP
with act_col3:
    certs = get_certificates(batch_id)
    has_generated = any(
        c.status in ("generated", "sent") and c.file_path
        and os.path.exists(os.path.join(os.getcwd(), c.file_path))
        for c in certs
    )

    if has_generated:
        zip_buffer = io.BytesIO()
        files_added = 0
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for c in certs:
                if c.status not in ("generated", "sent") or not c.file_path:
                    continue
                full_path = os.path.join(os.getcwd(), c.file_path)
                if not os.path.exists(full_path):
                    continue
                safe_name = c.participant.name.replace(" ", "_").replace("/", "_") if c.participant else f"cert_{c.id}"
                zf.write(full_path, arcname=f"{safe_name}.pdf")
                files_added += 1

        zip_buffer.seek(0)
        safe_batch_name = batch.name.replace(" ", "_").replace("/", "_")[:50]
        st.download_button(
            label="📦 Download All as ZIP",
            data=zip_buffer,
            file_name=f"{safe_batch_name}_certificates.zip",
            mime="application/zip",
            use_container_width=True,
        )
    else:
        st.button(
            "📦 Download All as ZIP",
            use_container_width=True,
            disabled=True,
            help="No generated certificates available",
        )

# 4. Delete Batch
with act_col4:
    if st.button("🗑️ Delete Batch", use_container_width=True, type="secondary"):
        session = get_session()
        try:
            b = session.query(CertificateBatch).get(batch.id)
            if b:
                # Delete certificate files
                for c in b.certificates:
                    if c.file_path:
                        fp = os.path.join(os.getcwd(), c.file_path)
                        if os.path.exists(fp):
                            os.remove(fp)
                cert_folder = os.path.join(os.getcwd(), Config.CERTIFICATE_FOLDER, str(batch.id))
                if os.path.exists(cert_folder):
                    import shutil
                    shutil.rmtree(cert_folder, ignore_errors=True)
                session.delete(b)
                session.commit()
                st.success(f"Deleted batch #{batch.id}")
                st.session_state["deleted_batch"] = True
        except Exception as e:
            session.rollback()
            st.error(f"Error: {e}")
        finally:
            session.close()

        if st.session_state.get("deleted_batch"):
            st.switch_page("pages/3_Batches.py")

# ---- Individual Certificate Downloads ----
if certificates:
    st.markdown("---")
    st.subheader("⬇️ Downloads")

    for c in certificates:
        if c.file_path and os.path.exists(os.path.join(os.getcwd(), c.file_path)):
            with open(os.path.join(os.getcwd(), c.file_path), "rb") as f:
                pdf_data = f.read()
            pname = c.participant.name.replace(" ", "_") if c.participant else f"cert_{c.id}"
            st.download_button(
                label=f"📄 Download {c.participant.name}'s Certificate" if c.participant else f"📄 Download Cert #{c.id}",
                data=pdf_data,
                file_name=f"{pname}.pdf",
                mime="application/pdf",
                use_container_width=False,
            )
