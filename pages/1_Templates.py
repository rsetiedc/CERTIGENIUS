"""
CertiGenius — Template Management Page
Upload, view, and delete certificate template groups.
"""
import os
import re
import uuid
from datetime import datetime, timezone

import streamlit as st

from models import Template, TemplateGroup, Base
from utils.db import get_session, init_connection

st.set_page_config(page_title="Templates — CertiGenius", page_icon="📄", layout="wide")


def _detect_position_from_filename(filename):
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


# ---- Init DB ----
engine = init_connection()
Base.metadata.create_all(engine)

st.title("📄 Template Groups")
st.markdown("Upload certificate template designs and organize them into groups.")

# ---- Upload Form ----
with st.expander("➕ Upload New Template Group", expanded=False):
    with st.form("upload_template_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("Group Name", placeholder="e.g., Summer Workshop 2024")
        with col2:
            description = st.text_input("Description (optional)", placeholder="Any notes about this template")

        placeholder_fields = st.text_input(
            "Placeholder Fields (comma-separated)",
            value="participant_name, prize_position, event_name, date",
            help="Field names that will be replaced with participant data",
        )

        files = st.file_uploader(
            "Upload Templates (PNG, JPG, PDF)",
            type=["png", "jpg", "jpeg", "pdf"],
            accept_multiple_files=True,
            help="Name files like '1st_prize.png', 'participation.pdf' to auto-detect positions",
        )

        submitted = st.form_submit_button("🚀 Upload Templates", use_container_width=True, type="primary")

        if submitted:
            if not files:
                st.error("Please select at least one file.")
                st.stop()

            group_name = name.strip() or f"Template Group {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}"
            fields_list = [f.strip() for f in placeholder_fields.split(",") if f.strip()]

            session = get_session()
            try:
                group = TemplateGroup(name=group_name, description=description)
                session.add(group)
                session.flush()

                upload_dir = os.path.join(os.getcwd(), "uploads", "templates")
                os.makedirs(upload_dir, exist_ok=True)

                positions_added = []
                for file in files:
                    ext = os.path.splitext(file.name)[1].lower()
                    if ext not in (".png", ".jpg", ".jpeg", ".pdf"):
                        st.warning(f"Skipped unsupported file: {file.name}")
                        continue

                    position_label = _detect_position_from_filename(file.name)
                    filename = f"{uuid.uuid4().hex}{ext}"
                    file_path = os.path.join(upload_dir, filename)
                    
                    with open(file_path, "wb") as f:
                        f.write(file.getbuffer())

                    template = Template(
                        name=f"{group_name} - {position_label}",
                        description=description,
                        file_path=os.path.join("uploads", "templates", filename),
                        file_type=ext[1:],
                        position_label=position_label,
                        group_id=group.id,
                    )
                    template.set_placeholders(fields_list)
                    session.add(template)
                    positions_added.append(position_label)

                session.commit()
                st.success(f"✅ Uploaded {len(positions_added)} template(s): {', '.join(positions_added)}")
                
                # Cache busting
                if "template_groups" in st.session_state:
                    del st.session_state["template_groups"]

            except Exception as e:
                session.rollback()
                st.error(f"Error uploading templates: {e}")
            finally:
                session.close()

# ---- List Template Groups ----
st.markdown("---")
st.subheader("📋 Existing Template Groups")

session = get_session()
try:
    groups = (
        session.query(TemplateGroup)
        .filter_by(is_deleted=False)
        .order_by(TemplateGroup.created_at.desc())
        .all()
    )
finally:
    session.close()

if not groups:
    st.info("No template groups yet. Upload one above to get started!")
    st.stop()

for group in groups:
    with st.container(border=True):
        col1, col2, col3 = st.columns([3, 1, 1])
        with col1:
            st.markdown(f"**{group.name}**")
            if group.description:
                st.caption(group.description)
            st.caption(f"Created: {group.created_at.strftime('%b %d, %Y %H:%M') if group.created_at else '—'}")

        with col2:
            session2 = get_session()
            try:
                child_templates = session2.query(Template).filter_by(group_id=group.id, is_deleted=False).all()
                if child_templates:
                    with st.popover(f"📄 {len(child_templates)} template(s)"):
                        for t in child_templates:
                            st.markdown(f"- **{t.position_label}** ({t.file_type.upper()})")
                            if t.get_placeholders():
                                st.caption(f"  Placeholders: {', '.join(t.get_placeholders())}")
            finally:
                session2.close()

        with col3:
            delete_key = f"delete_{group.id}"
            if st.button("🗑️ Delete", key=delete_key, use_container_width=True):
                session3 = get_session()
                try:
                    group_to_delete = session3.query(TemplateGroup).get(group.id)
                    if group_to_delete:
                        group_to_delete.is_deleted = True
                        for t in group_to_delete.templates:
                            t.is_deleted = True
                        session3.commit()
                        st.success(f"Deleted '{group.name}'")
                        st.rerun()
                except Exception as e:
                    session3.rollback()
                    st.error(f"Error: {e}")
                finally:
                    session3.close()
