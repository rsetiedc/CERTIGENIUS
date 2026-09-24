"""
CertiGenius — Batches Page
View all certificate batches with their status and progress.
"""
import streamlit as st

from models import Certificate, CertificateBatch, Base
from utils.db import get_session, init_connection

st.set_page_config(page_title="Batches — CertiGenius", page_icon="📦", layout="wide")


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


engine = init_connection()
Base.metadata.create_all(engine)

st.title("📦 Certificate Batches")

session = get_session()
try:
    batches = (
        session.query(CertificateBatch)
        .order_by(CertificateBatch.created_at.desc())
        .all()
    )
finally:
    session.close()

if not batches:
    st.info("No batches yet. Import participants to create your first batch!")
    st.page_link("pages/2_Import_Participants.py", label="👥 Import Participants Now")
    st.stop()

rows = []
for b in batches:
    progress = "—"
    if b.total_count > 0:
        done = (b.generated_count or 0) + (b.sent_count or 0)
        progress = f"{done}/{b.total_count}"
    event_label = "ISA Event" if (b.event_type or "non_isa") == "isa" else "Non-ISA"
    rows.append({
        "ID": b.id,
        "Name": b.name,
        "Event Type": event_label,
        "Status": status_badge(b.status),
        "Total": b.total_count,
        "Generated": b.generated_count or 0,
        "Sent": b.sent_count or 0,
        "Failed": b.failed_count or 0,
        "Created": b.created_at.strftime("%b %d, %Y %H:%M") if b.created_at else "—",
    })

st.dataframe(
    rows,
    column_config={
        "ID": st.column_config.NumberColumn(width=60),
        "Name": st.column_config.TextColumn(width="20%"),
        "Status": st.column_config.TextColumn(width=130),
        "Total": st.column_config.NumberColumn(width=70),
        "Generated": st.column_config.NumberColumn(width=80),
        "Sent": st.column_config.NumberColumn(width=60),
        "Failed": st.column_config.NumberColumn(width=60),
        "Created": st.column_config.TextColumn(width=170),
    },
    use_container_width=True,
    hide_index=True,
)

st.markdown("---")

# Batch detail navigation
st.subheader("🔍 View Batch Details")
col1, col2 = st.columns([1, 4])
with col1:
    batch_id = st.number_input("Enter Batch ID:", min_value=1, step=1)
with col2:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🔍 View Batch", use_container_width=True, type="primary"):
        st.switch_page("pages/4_Batch_Detail.py")
        st.query_params["batch_id"] = str(batch_id)
