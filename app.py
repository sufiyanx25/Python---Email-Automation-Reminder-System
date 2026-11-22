"""
app.py
------
Streamlit Dashboard for Email Automation & Reminder System.

A clean, responsive dashboard displaying:
- Real-time metrics (Contacts, Reminders, Upcoming, Completed, Failed)
- Dry-run safety status indicator
- Filterable tables for Reminders and Contacts
- Interactive Email Personalization Preview
- One-click Safe Simulation Runner
- CSV Audit Report generation & direct download
- Activity logs viewer
"""

import os
from pathlib import Path
import pandas as pd
import streamlit as st

from src.contact_manager import ContactManager
from src.email_template import TemplateManager
from src.email_sender import EmailSender
from src.scheduler import ReminderScheduler, get_current_time
from src.report_generator import ReportGenerator

# Page Configuration
st.set_page_config(
    page_title="Email Automation & Reminder System",
    page_icon="📬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for clean UI styling
st.markdown("""
<style>
    .main-title {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1E3A8A;
        margin-bottom: 0.2rem;
    }
    .sub-title {
        font-size: 1.05rem;
        color: #4B5563;
        margin-bottom: 1.5rem;
    }
    .metric-card {
        background-color: #F8FAFC;
        border-radius: 8px;
        padding: 12px;
        border: 1px solid #E2E8F0;
    }
    .preview-box {
        background-color: #F1F5F9;
        border-left: 4px solid #2563EB;
        padding: 16px;
        border-radius: 4px;
        font-family: monospace;
        white-space: pre-wrap;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def load_managers():
    """Initializes and caches core system managers."""
    contact_mgr = ContactManager("data/contacts.csv")
    template_mgr = TemplateManager("templates")
    scheduler = ReminderScheduler("data/reminders.csv")
    sender = EmailSender(dry_run=True)
    report_gen = ReportGenerator("outputs")
    return contact_mgr, template_mgr, scheduler, sender, report_gen


contact_mgr, template_mgr, scheduler, sender, report_gen = load_managers()

# Sidebar: Controls & Safety status
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/mail-automation.png", width=70)
    st.title("System Controls")
    
    st.info(
        "🛡️ **Dry-Run Mode Active**\n\n"
        "All email sending is simulated safely. "
        "No live SMTP connections are established."
    )

    st.markdown("---")
    st.markdown("### 🕒 System Time")
    ist_time = get_current_time().strftime("%Y-%m-%d %H:%M:%S")
    st.code(f"Asia/Kolkata:\n{ist_time}")

    st.markdown("---")
    if st.button("🔄 Refresh Data & Status", use_container_width=True):
        contact_mgr.load_contacts()
        scheduler.load_reminders()
        st.success("Data reloaded successfully!")

    if st.button("🧹 Reset Duplicate Tracker", use_container_width=True):
        scheduler.tracker.reset()
        scheduler.load_reminders()
        st.warning("Processed reminders tracker reset!")


# Header section
st.markdown('<div class="main-title">📬 Email Automation & Reminder System</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-title">A beginner-friendly, modular automation platform for contact management, '
    'personalized email templating, scheduling, and audit reporting.</div>',
    unsafe_allow_html=True
)

# Fetch current metrics
contact_summary = contact_mgr.get_contacts_summary()
rem_summary = scheduler.get_summary()

# Top KPI Metric Cards
col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.metric(label="👥 Total Contacts", value=contact_summary["total"], delta=f"{contact_summary['valid']} Valid")
with col2:
    st.metric(label="⏰ Total Reminders", value=rem_summary["total"])
with col3:
    st.metric(label="🚨 Due Reminders", value=rem_summary["due"])
with col4:
    st.metric(label="📅 Upcoming", value=rem_summary["upcoming"])
with col5:
    st.metric(label="✅ Completed", value=rem_summary["completed"])

st.markdown("---")

# Main Navigation Tabs
tab_reminders, tab_contacts, tab_preview, tab_simulation, tab_reports = st.tabs([
    "⏰ Reminders & Schedules",
    "👥 Contacts Directory",
    "✉️ Template & Live Preview",
    "🚀 Safe Simulation Runner",
    "📊 Reports & Activity Logs"
])

# -----------------------------------------------------------------------------
# TAB 1: REMINDERS & SCHEDULES
# -----------------------------------------------------------------------------
with tab_reminders:
    st.subheader("Scheduled Reminders Overview")
    
    col_table, col_chart = st.columns([2, 1])
    
    with col_table:
        status_filter = st.multiselect(
            "Filter by Status:",
            options=["Due", "Upcoming", "Completed", "Invalid Date"],
            default=["Due", "Upcoming", "Completed"]
        )
        
        display_df = scheduler.reminders_df.copy()
        if status_filter:
            display_df = display_df[display_df["status"].isin(status_filter)]
            
        st.dataframe(
            display_df[["id", "recipient_email", "subject", "scheduled_time", "frequency", "status"]],
            use_container_width=True,
            hide_index=True
        )

    with col_chart:
        st.markdown("#### Status Breakdown")
        status_counts = scheduler.reminders_df["status"].value_counts()
        if not status_counts.empty:
            st.bar_chart(status_counts, color="#3B82F6")
        else:
            st.info("No reminder records available.")


# -----------------------------------------------------------------------------
# TAB 2: CONTACTS DIRECTORY
# -----------------------------------------------------------------------------
with tab_contacts:
    st.subheader("Contacts Management & Validation")
    st.caption("Validates recipient email formatting and assigns default names to missing contact records.")

    search_query = st.text_input("🔍 Search contact by name or email:", "")

    contacts_df = contact_mgr.df.copy()
    if search_query:
        mask = (
            contacts_df["name"].str.contains(search_query, case=False, na=False) |
            contacts_df["email"].str.contains(search_query, case=False, na=False)
        )
        contacts_df = contacts_df[mask]

    st.dataframe(
        contacts_df[["name", "email", "validation_status"]],
        use_container_width=True,
        hide_index=True
    )

    if contact_summary["invalid"] > 0:
        st.warning(
            f"⚠️ Detected {contact_summary['invalid']} contact(s) with invalid or malformed email addresses. "
            "These will be safely flagged and skipped during dispatches."
        )


# -----------------------------------------------------------------------------
# TAB 3: TEMPLATE & LIVE PREVIEW
# -----------------------------------------------------------------------------
with tab_preview:
    st.subheader("Dynamic Email Template Personalization")
    st.markdown(
        "Select a contact and a reminder to preview how placeholders "
        "(`{name}`, `{subject}`, `{message}`, `{date}`) are personalized."
    )

    raw_template = template_mgr.load_template("email_template.txt")

    col_sel1, col_sel2 = st.columns(2)
    
    # Available emails for preview
    all_emails = contact_mgr.df["email"].tolist()
    valid_emails = [e for e in all_emails if ContactManager.validate_email(e)]
    if not valid_emails:
        valid_emails = ["alice.johnson@example.com"]

    with col_sel1:
        selected_email = st.selectbox("Choose Contact for Preview:", valid_emails)
        contact_name = contact_mgr.get_contact_name(selected_email)

    with col_sel2:
        reminders_list = scheduler.reminders_df.to_dict(orient="records")
        rem_options = {f"[{r.get('id', 'N/A')}] {r.get('subject', 'Untitled')}": r for r in reminders_list}
        selected_rem_key = st.selectbox("Choose Reminder for Preview:", list(rem_options.keys()))
        selected_rem = rem_options[selected_rem_key]

    # Render personalized content
    context = {
        "name": contact_name,
        "subject": selected_rem.get("subject", "Notification"),
        "message": selected_rem.get("message", "Reminder message content"),
        "date": selected_rem.get("scheduled_time", "Upcoming"),
        "scheduled_time": selected_rem.get("scheduled_time", "Upcoming")
    }
    rendered_email = template_mgr.render_template(raw_template, context)
    extracted_subj, extracted_body = template_mgr.extract_subject_and_body(rendered_email)

    col_raw, col_rendered = st.columns(2)
    with col_raw:
        st.markdown("**Raw Template (`templates/email_template.txt`):**")
        st.code(raw_template, language="text")

    with col_rendered:
        st.markdown(f"**Personalized Email Preview (To: {selected_email}):**")
        st.markdown(f"**Subject:** `{extracted_subj}`")
        st.markdown(f'<div class="preview-box">{extracted_body}</div>', unsafe_allow_html=True)


# -----------------------------------------------------------------------------
# TAB 4: SAFE SIMULATION RUNNER
# -----------------------------------------------------------------------------
with tab_simulation:
    st.subheader("Safe Simulation Execution Center")
    st.markdown(
        "Run the dispatch pipeline in safe simulation mode. "
        "Each email is personalized, validated, and logged without contacting live SMTP servers."
    )

    sim_mode = st.radio(
        "Choose Simulation Scope:",
        ["Process Due Reminders Only", "Simulate All Reminders (Demo Full Batch)"],
        horizontal=True
    )

    if st.button("🚀 Run Safe Simulation Now", type="primary", use_container_width=True):
        raw_template = template_mgr.load_template("email_template.txt")
        scheduler.load_reminders()

        if sim_mode == "Process Due Reminders Only":
            items_to_process = scheduler.get_due_reminders()
            mark_done = True
        else:
            items_to_process = scheduler.reminders_df.to_dict(orient="records")
            mark_done = False

        if not items_to_process:
            st.info("ℹ️ No due reminders found at this moment.")
        else:
            results = []
            progress_bar = st.progress(0)
            
            for idx, item in enumerate(items_to_process):
                rec_email = item.get("recipient_email", "").strip().lower()
                rem_id = item.get("id", "N/A")
                subj = item.get("subject", "Reminder")
                msg_content = item.get("message", "")
                sched_time = item.get("scheduled_time", "N/A")

                # Validate
                if not ContactManager.validate_email(rec_email):
                    rec_name = "Unknown"
                    status = "SKIPPED_INVALID_EMAIL"
                    err = f"Malformed email address: '{rec_email}'"
                else:
                    rec_name = contact_mgr.get_contact_name(rec_email)
                    ctx = {
                        "name": rec_name,
                        "subject": subj,
                        "message": msg_content,
                        "date": sched_time
                    }
                    personalized = template_mgr.render_template(raw_template, ctx)
                    mail_subj, mail_body = template_mgr.extract_subject_and_body(personalized)
                    ok, status, err = sender.send_email(
                        recipient_email=rec_email,
                        subject=mail_subj,
                        body=mail_body,
                        recipient_name=rec_name
                    )
                    if ok and mark_done:
                        scheduler.tracker.mark_processed(rem_id, get_current_time())

                report_gen.record_result(
                    recipient_name=rec_name,
                    recipient_email=rec_email,
                    subject=subj,
                    reminder_date_time=sched_time,
                    status=status,
                    error_message=err if status != "SIMULATED" else ""
                )

                results.append({
                    "Reminder ID": rem_id,
                    "Recipient": rec_email,
                    "Subject": subj,
                    "Status": status,
                    "Notes": err if err else "Simulated successfully"
                })

                progress_bar.progress((idx + 1) / len(items_to_process))

            # Export fresh report
            report_gen.export_csv("dashboard_simulation_report.csv")
            scheduler.load_reminders()

            st.success(f"🎉 Simulation completed! Processed {len(results)} reminder(s).")
            st.dataframe(pd.DataFrame(results), use_container_width=True, hide_index=True)


# -----------------------------------------------------------------------------
# TAB 5: REPORTS & ACTIVITY LOGS
# -----------------------------------------------------------------------------
with tab_reports:
    st.subheader("Audit Reports & Execution History")
    
    current_report_df = report_gen.to_dataframe()

    if not current_report_df.empty:
        col_down1, col_down2 = st.columns([3, 1])
        with col_down1:
            st.dataframe(current_report_df, use_container_width=True, hide_index=True)
        with col_down2:
            st.markdown("#### Download Report")
            csv_data = current_report_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="📥 Download CSV Report",
                data=csv_data,
                file_name="email_reminder_audit_report.csv",
                mime="text/csv",
                use_container_width=True
            )
    else:
        st.info("No execution records in memory yet. Run a simulation to populate the report.")

    st.markdown("---")
    st.subheader("📜 Activity Log Stream")
    log_file_path = Path("logs/email_system.log")

    if log_file_path.exists():
        log_text = log_file_path.read_text(encoding="utf-8")
        recent_logs = "\n".join(log_text.splitlines()[-30:])
        st.code(recent_logs, language="text")
    else:
        st.info("No log file found in logs/ directory.")
