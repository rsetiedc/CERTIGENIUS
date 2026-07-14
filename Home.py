"""
CertiGenius — Streamlit Dashboard
Automated Certificate Generation and Distribution Platform
"""
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st

# Must be the first Streamlit command
st.set_page_config(
    page_title="CertiGenius",
    page_icon="🏆",
    layout="wide",
    initial_sidebar_state="expanded",
)

from models import Certificate, CertificateBatch, Participant, TemplateGroup, Base
from utils.db import init_connection, get_session
from datetime import datetime, timezone


def init_app():
    """Initialize the app: create DB tables and required directories."""
    engine = init_connection()
    Base.metadata.create_all(engine)
    
    # Ensure upload directories exist
    from config import Config
    for path in [
        os.path.join(os.getcwd(), Config.UPLOAD_FOLDER, "templates"),
        os.path.join(os.getcwd(), Config.UPLOAD_FOLDER, "participants"),
        os.path.join(os.getcwd(), Config.CERTIFICATE_FOLDER),
    ]:
        os.makedirs(path, exist_ok=True)


def format_time(dt):
    if not dt:
        return "—"
    if isinstance(dt, str):
        return dt
    return dt.strftime("%b %d, %Y %H:%M")


def status_badge(status):
    badges = {
        "pending": "🟡 Pending",
        "generating": "🔵 Generating",
        "generated": "🟢 Generated",
        "distributing": "🟠 Distributing",
        "completed": "✅ Completed",
        "failed": "❌ Failed",
    }
    return badges.get(status, status)


# ---- Initialize ----
init_app()

# ---- Sidebar ----
st.sidebar.markdown(
    """
    <div style="text-align: center; padding: 1rem 0;">
        <h1 style="font-size: 2rem;">🏆</h1>
        <h3 style="margin: 0; color: #667eea;">CertiGenius</h3>
        <p style="font-size: 0.8rem; color: #6c757d;">Certificate Platform</p>
    </div>
    """,
    unsafe_allow_html=True,
)

st.sidebar.page_link("Home.py", label="📊 Dashboard", use_container_width=True)
st.sidebar.page_link("pages/1_Templates.py", label="📄 Templates")
st.sidebar.page_link("pages/2_Import_Participants.py", label="👥 Import Participants")
st.sidebar.page_link("pages/3_Batches.py", label="📦 Batches")
st.sidebar.page_link("pages/5_Verify.py", label="✅ Verify Certificate")

st.sidebar.markdown("---")
st.sidebar.markdown(
    "<p style='font-size: 0.75rem; color: #adb5bd; text-align: center;'>"
    "Built with Streamlit &hearts;</p>",
    unsafe_allow_html=True,
)

# ---- Dashboard ----
st.markdown(
    """
    <div style="text-align: center; padding: 2rem 0 1rem;">
        <h1 style="font-size: 2.5rem; font-weight: 700; color: #212529;">
            🏆 CertiGenius
        </h1>
        <p style="font-size: 1.1rem; color: #6c757d; max-width: 600px; margin: 0 auto;">
            Automated Certificate Generation and Distribution Platform
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---- Stats Cards ----
session = get_session()
try:
    template_count = session.query(TemplateGroup).filter_by(is_deleted=False).count()
    participant_count = session.query(Participant).count()
    batch_count = session.query(CertificateBatch).count()
    certificate_count = session.query(Certificate).count()
    sent_count = session.query(Certificate).filter_by(status="sent").count()
    recent_batches = (
        session.query(CertificateBatch)
        .order_by(CertificateBatch.created_at.desc())
        .limit(5)
        .all()
    )
finally:
    session.close()

col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    st.metric("📄 Templates", template_count, border=True)
with col2:
    st.metric("👥 Participants", participant_count, border=True)
with col3:
    st.metric("📦 Batches", batch_count, border=True)
with col4:
    st.metric("📜 Certificates", certificate_count, border=True)
with col5:
    st.metric("✉️ Sent", sent_count, border=True)

# ---- Quick Actions ----
st.markdown("---")
st.subheader("🚀 Quick Actions")

qa_col1, qa_col2, qa_col3, qa_col4 = st.columns(4)
with qa_col1:
    if st.button("📄 Manage Templates", use_container_width=True, type="primary"):
        st.switch_page("pages/1_Templates.py")
with qa_col2:
    if st.button("👥 Import Participants", use_container_width=True, type="primary"):
        st.switch_page("pages/2_Import_Participants.py")
with qa_col3:
    if st.button("📦 View Batches", use_container_width=True, type="primary"):
        st.switch_page("pages/3_Batches.py")
with qa_col4:
    if st.button("✅ Verify Certificate", use_container_width=True):
        st.switch_page("pages/5_Verify.py")

# ---- Recent Batches ----
st.markdown("---")
st.subheader("📋 Recent Batches")

if recent_batches:
    rows = []
    for b in recent_batches:
        progress = "—"
        if b.total_count > 0:
            done = (b.generated_count or 0) + (b.sent_count or 0)
            progress = f"{done}/{b.total_count}"
        rows.append({
            "ID": b.id,
            "Name": b.name,
            "Status": status_badge(b.status),
            "Progress": progress,
            "Created": format_time(b.created_at),
        })

    st.dataframe(
        rows,
        column_config={
            "ID": st.column_config.NumberColumn(width=60),
            "Name": st.column_config.TextColumn(width=250),
            "Status": st.column_config.TextColumn(width=130),
            "Progress": st.column_config.TextColumn(width=100),
            "Created": st.column_config.TextColumn(width=180),
        },
        use_container_width=True,
        hide_index=True,
    )

    if st.button("🔍 View All Batches", use_container_width=True):
        st.switch_page("pages/3_Batches.py")
else:
    st.info("No batches yet. Import participants to get started!")

# ---- Workflow Guide ----
st.markdown("---")
st.subheader("📖 How It Works")

wf_col1, wf_col2, wf_col3, wf_col4 = st.columns(4)
with wf_col1:
    st.markdown(
        """
        <div style="text-align: center; padding: 1rem; background: #f8f4ff; border-radius: 12px; border: 1px solid #e8dfff;">
            <h2 style="font-size: 2.5rem; margin: 0;">1️⃣</h2>
            <h5 style="margin: 0.5rem 0; color: #667eea;">Upload Template</h5>
            <p style="font-size: 0.85rem; color: #6c757d; margin: 0;">Upload certificate designs (PNG, JPG, PDF)</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
with wf_col2:
    st.markdown(
        """
        <div style="text-align: center; padding: 1rem; background: #f0f9ff; border-radius: 12px; border: 1px solid #d0edff;">
            <h2 style="font-size: 2.5rem; margin: 0;">2️⃣</h2>
            <h5 style="margin: 0.5rem 0; color: #667eea;">Import Data</h5>
            <p style="font-size: 0.85rem; color: #6c757d; margin: 0;">Upload participant list (CSV, Excel)</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
with wf_col3:
    st.markdown(
        """
        <div style="text-align: center; padding: 1rem; background: #f0fdf4; border-radius: 12px; border: 1px solid #d0f0d0;">
            <h2 style="font-size: 2.5rem; margin: 0;">3️⃣</h2>
            <h5 style="margin: 0.5rem 0; color: #667eea;">Generate</h5>
            <p style="font-size: 0.85rem; color: #6c757d; margin: 0;">Auto-generate personalized certificates</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
with wf_col4:
    st.markdown(
        """
        <div style="text-align: center; padding: 1rem; background: #fff8f0; border-radius: 12px; border: 1px solid #ffe0b0;">
            <h2 style="font-size: 2.5rem; margin: 0;">4️⃣</h2>
            <h5 style="margin: 0.5rem 0; color: #667eea;">Distribute</h5>
            <p style="font-size: 0.85rem; color: #6c757d; margin: 0;">Send via email or download as ZIP</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
