import sqlite3
import io
import zipfile
import logging
from datetime import date, timedelta

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import streamlit as st

# --------------------------------------------------
# 1. APPLICATION CONFIGURATION
# --------------------------------------------------

st.set_page_config(
    page_title="StudyPulse",
    page_icon="📚",
    layout="wide"
)

logging.basicConfig(
    filename="studypulse.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

DB_NAME = "studypulse.db"


# --------------------------------------------------
# 2. DATABASE SETUP
# --------------------------------------------------

def get_connection():
    return sqlite3.connect(DB_NAME)


def setup_database():
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS study_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject TEXT NOT NULL,
                study_date TEXT NOT NULL,
                hours REAL NOT NULL
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS exam_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject TEXT NOT NULL,
                exam_date TEXT NOT NULL,
                marks REAL NOT NULL
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS assignments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject TEXT NOT NULL,
                title TEXT NOT NULL,
                due_date TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Pending'
            )
        """)

        conn.commit()


def read_table(table_name):
    allowed_tables = {
        "study_sessions",
        "exam_results",
        "assignments"
    }

    if table_name not in allowed_tables:
        raise ValueError("Invalid table name")

    with get_connection() as conn:
        return pd.read_sql_query(
            f"SELECT * FROM {table_name}",
            conn
        )


def add_record(table_name, values):
    allowed_tables = {
        "study_sessions",
        "exam_results",
        "assignments"
    }

    if table_name not in allowed_tables:
        raise ValueError("Invalid table name")

    columns = {
        "study_sessions": "(subject, study_date, hours)",
        "exam_results": "(subject, exam_date, marks)",
        "assignments": "(subject, title, due_date, status)"
    }

    placeholders = ", ".join(["?"] * len(values))

    query = (
        f"INSERT INTO {table_name} "
        f"{columns[table_name]} VALUES ({placeholders})"
    )

    with get_connection() as conn:
        conn.execute(query, values)
        conn.commit()

    logging.info("Record added to %s", table_name)


def delete_record(table_name, record_id):
    allowed_tables = {
        "study_sessions",
        "exam_results",
        "assignments"
    }

    if table_name not in allowed_tables:
        raise ValueError("Invalid table name")

    with get_connection() as conn:
        conn.execute(
            f"DELETE FROM {table_name} WHERE id = ?",
            (record_id,)
        )
        conn.commit()

    logging.info(
        "Record %s deleted from %s",
        record_id,
        table_name
    )


def update_assignment_status(record_id, status):
    with get_connection() as conn:
        conn.execute(
            "UPDATE assignments SET status = ? WHERE id = ?",
            (status, record_id)
        )
        conn.commit()

    logging.info(
        "Assignment %s updated to %s",
        record_id,
        status
    )


setup_database()


# --------------------------------------------------
# 3. HELPER FUNCTIONS
# --------------------------------------------------

def csv_download_button(data, filename, label):
    csv_data = data.to_csv(index=False).encode("utf-8")

    st.download_button(
        label=label,
        data=csv_data,
        file_name=filename,
        mime="text/csv"
    )


def show_chart(fig):
    st.pyplot(fig)
    plt.close(fig)


def calculate_productivity(total_hours, average_marks):
    study_score = min(total_hours * 3, 100)

    if average_marks is None:
        return round(study_score, 1)

    score = (0.4 * study_score) + (0.6 * average_marks)

    return round(min(max(score, 0), 100), 1)


def make_zip_export():
    study = read_table("study_sessions")
    exams = read_table("exam_results")
    assignments = read_table("assignments")

    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(
        zip_buffer,
        mode="w",
        compression=zipfile.ZIP_DEFLATED
    ) as zip_file:
        zip_file.writestr(
            "study_sessions.csv",
            study.to_csv(index=False)
        )

        zip_file.writestr(
            "exam_results.csv",
            exams.to_csv(index=False)
        )

        zip_file.writestr(
            "assignments.csv",
            assignments.to_csv(index=False)
        )

    zip_buffer.seek(0)
    return zip_buffer.getvalue()


# --------------------------------------------------
# 4. SIDEBAR NAVIGATION
# --------------------------------------------------

st.sidebar.title("📚 StudyPulse")
st.sidebar.caption("Student Productivity Analyzer")

page = st.sidebar.radio(
    "Navigate",
    [
        "Dashboard",
        "Study Sessions",
        "Exam Results",
        "Assignments",
        "Analytics",
        "Recommendations",
        "Data Export"
    ]
)

st.sidebar.divider()

st.sidebar.info(
    "Track study habits, monitor academic performance, "
    "and manage assignments."
)


# --------------------------------------------------
# 5. DASHBOARD
# --------------------------------------------------

if page == "Dashboard":

    study = read_table("study_sessions")
    exams = read_table("exam_results")
    assignments = read_table("assignments")

    st.title("📊 Academic Overview")

    st.write(
        "Welcome to StudyPulse! Review your study activity "
        "and academic progress in one place."
    )

    # DAILY STUDY GOAL
    st.subheader("🎯 Daily Study Goal")

    daily_goal = st.number_input(
        "Set your daily study target (hours)",
        min_value=1.0,
        max_value=12.0,
        value=3.0,
        step=0.5
    )

    today = date.today().isoformat()

    if not study.empty:
        today_hours = study.loc[
            study["study_date"] == today,
            "hours"
        ].sum()
    else:
        today_hours = 0.0

    today_hours = float(today_hours)

    st.metric(
        "Today's Study Time",
        f"{today_hours:.1f} / {daily_goal:.1f} hours"
    )

    progress = min(today_hours / daily_goal, 1.0)
    st.progress(progress)

    if today_hours >= daily_goal:
        st.success("🎉 Daily study goal achieved!")
    else:
        remaining = daily_goal - today_hours

        st.info(
            f"Keep going! You have {remaining:.1f} hours "
            "left to reach your goal."
        )

    st.divider()

    # DATE FILTER
    date_filter = st.selectbox(
        "Study data time range",
        ["All Time", "Last 7 Days", "Last 30 Days"]
    )

    filtered_study = study.copy()

    if not filtered_study.empty and date_filter != "All Time":
        days = 7 if date_filter == "Last 7 Days" else 30

        cutoff = (
            date.today() - timedelta(days=days - 1)
        ).isoformat()

        filtered_study = filtered_study[
            filtered_study["study_date"] >= cutoff
        ]

    total_hours = (
        float(filtered_study["hours"].sum())
        if not filtered_study.empty else 0.0
    )

    average_marks = (
        float(exams["marks"].mean())
        if not exams.empty else None
    )

    productivity = calculate_productivity(
        total_hours,
        average_marks
    )

    pending_assignments = (
        int((assignments["status"] == "Pending").sum())
        if not assignments.empty else 0
    )

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("📖 Study Hours", f"{total_hours:.1f}")

    col2.metric(
        "📝 Average Marks",
        f"{average_marks:.1f}%"
        if average_marks is not None else "N/A"
    )

    col3.metric(
        "⚡ Productivity Score",
        f"{productivity}/100"
    )

    col4.metric(
        "📌 Pending Assignments",
        pending_assignments
    )

    st.divider()

    left, right = st.columns(2)

    with left:
        st.subheader("📈 Study Hours by Subject")

        if not filtered_study.empty:
            subject_hours = (
                filtered_study.groupby("subject")["hours"]
                .sum()
                .reset_index()
            )

            fig, ax = plt.subplots(figsize=(7, 4))

            sns.barplot(
                data=subject_hours,
                x="subject",
                y="hours",
                ax=ax
            )

            ax.set_xlabel("Subject")
            ax.set_ylabel("Study Hours")
            ax.tick_params(axis="x", rotation=30)
            fig.tight_layout()

            show_chart(fig)
        else:
            st.info("Add study sessions to see this chart.")

    with right:
        st.subheader("📊 Exam Performance")

        if not exams.empty:
            fig, ax = plt.subplots(figsize=(7, 4))

            sns.barplot(
                data=exams,
                x="subject",
                y="marks",
                ax=ax
            )

            ax.set_xlabel("Subject")
            ax.set_ylabel("Marks (%)")
            ax.set_ylim(0, 100)
            ax.tick_params(axis="x", rotation=30)
            fig.tight_layout()

            show_chart(fig)
        else:
            st.info("Add exam results to see this chart.")

    st.subheader("📌 Upcoming Pending Assignments")

    if not assignments.empty:
        pending = assignments[
            assignments["status"] == "Pending"
        ].copy()

        if not pending.empty:
            pending["due_date"] = pd.to_datetime(
                pending["due_date"],
                errors="coerce"
            )

            pending = pending.sort_values("due_date")

            st.dataframe(
                pending,
                use_container_width=True,
                hide_index=True
            )
        else:
            st.success("No pending assignments!")
    else:
        st.info("No assignments have been added yet.")


# --------------------------------------------------
# 6. STUDY SESSIONS
# --------------------------------------------------

elif page == "Study Sessions":

    st.title("📖 Study Sessions")

    st.write(
        "Record how much time you spend studying each subject."
    )

    with st.form("study_form", clear_on_submit=True):

        subject = st.text_input("Subject name")

        study_date = st.date_input(
            "Study date",
            value=date.today()
        )

        hours = st.number_input(
            "Study duration (hours)",
            min_value=0.5,
            max_value=24.0,
            value=1.0,
            step=0.5
        )

        submitted = st.form_submit_button("Add Study Session")

        if submitted:
            if not subject.strip():
                st.error("Please enter a subject name.")
            else:
                add_record(
                    "study_sessions",
                    (
                        subject.strip(),
                        study_date.isoformat(),
                        float(hours)
                    )
                )

                st.success("Study session added successfully!")
                st.rerun()

    st.divider()
    st.subheader("📋 Recorded Study Sessions")

    study = read_table("study_sessions")

    if not study.empty:
        st.dataframe(
            study.sort_values("study_date", ascending=False),
            use_container_width=True,
            hide_index=True
        )

        csv_download_button(
            study,
            "study_sessions.csv",
            "⬇️ Download Study Sessions CSV"
        )

        st.subheader("Delete a Study Session")

        record_id = st.selectbox(
            "Select session ID",
            study["id"].tolist(),
            key="delete_study_id"
        )

        if st.button("Delete Selected Study Session"):
            delete_record("study_sessions", int(record_id))
            st.success("Study session deleted.")
            st.rerun()
    else:
        st.info("No study sessions recorded yet.")


# --------------------------------------------------
# 7. EXAM RESULTS
# --------------------------------------------------

elif page == "Exam Results":

    st.title("📝 Exam Results")

    st.write(
        "Record and manage subject-wise examination marks."
    )

    with st.form("exam_form", clear_on_submit=True):

        subject = st.text_input("Subject name")

        exam_date = st.date_input(
            "Exam date",
            value=date.today()
        )

        marks = st.number_input(
            "Marks (%)",
            min_value=0.0,
            max_value=100.0,
            value=75.0,
            step=0.5
        )

        submitted = st.form_submit_button("Add Exam Result")

        if submitted:
            if not subject.strip():
                st.error("Please enter a subject name.")
            else:
                add_record(
                    "exam_results",
                    (
                        subject.strip(),
                        exam_date.isoformat(),
                        float(marks)
                    )
                )

                st.success("Exam result added successfully!")
                st.rerun()

    st.divider()
    st.subheader("📋 Recorded Exam Results")

    exams = read_table("exam_results")

    if not exams.empty:
        st.dataframe(
            exams.sort_values("exam_date", ascending=False),
            use_container_width=True,
            hide_index=True
        )

        csv_download_button(
            exams,
            "exam_results.csv",
            "⬇️ Download Exam Results CSV"
        )

        st.subheader("Edit an Exam Result")

        selected_id = st.selectbox(
            "Select exam record ID",
            exams["id"].tolist(),
            key="edit_exam_id"
        )

        selected_exam = exams[
            exams["id"] == selected_id
        ].iloc[0]

        with st.form("edit_exam_form"):

            new_subject = st.text_input(
                "Subject",
                value=str(selected_exam["subject"])
            )

            new_date = st.date_input(
                "Exam date",
                value=date.fromisoformat(
                    str(selected_exam["exam_date"])
                )
            )

            new_marks = st.number_input(
                "Marks (%)",
                min_value=0.0,
                max_value=100.0,
                value=float(selected_exam["marks"]),
                step=0.5
            )

            update_submitted = st.form_submit_button(
                "Update Exam Result"
            )

            if update_submitted:
                if not new_subject.strip():
                    st.error("Please enter a subject name.")
                else:
                    with get_connection() as conn:
                        conn.execute(
                            """
                            UPDATE exam_results
                            SET subject = ?, exam_date = ?, marks = ?
                            WHERE id = ?
                            """,
                            (
                                new_subject.strip(),
                                new_date.isoformat(),
                                float(new_marks),
                                int(selected_id)
                            )
                        )

                        conn.commit()

                    logging.info(
                        "Exam record %s updated",
                        selected_id
                    )

                    st.success("Exam result updated.")
                    st.rerun()

        st.subheader("Delete an Exam Result")

        delete_id = st.selectbox(
            "Select exam ID to delete",
            exams["id"].tolist(),
            key="delete_exam_id"
        )

        if st.button("Delete Selected Exam Result"):
            delete_record("exam_results", int(delete_id))
            st.success("Exam result deleted.")
            st.rerun()
    else:
        st.info("No exam results recorded yet.")


# --------------------------------------------------
# 8. ASSIGNMENTS
# --------------------------------------------------

elif page == "Assignments":

    st.title("📌 Assignment Manager")

    st.write(
        "Keep track of assignments and their deadlines."
    )

    with st.form("assignment_form", clear_on_submit=True):

        subject = st.text_input("Subject")
        title = st.text_input("Assignment title")

        due_date = st.date_input(
            "Due date",
            value=date.today() + timedelta(days=7)
        )

        submitted = st.form_submit_button("Add Assignment")

        if submitted:
            if not subject.strip() or not title.strip():
                st.error("Enter both subject and assignment title.")
            else:
                add_record(
                    "assignments",
                    (
                        subject.strip(),
                        title.strip(),
                        due_date.isoformat(),
                        "Pending"
                    )
                )

                st.success("Assignment added successfully!")
                st.rerun()

    st.divider()
    st.subheader("📋 Assignment List")

    assignments = read_table("assignments")

    if not assignments.empty:

        status_filter = st.selectbox(
            "Filter by status",
            ["All", "Pending", "Completed"]
        )

        filtered_assignments = assignments.copy()

        if status_filter != "All":
            filtered_assignments = filtered_assignments[
                filtered_assignments["status"] == status_filter
            ]

        st.dataframe(
            filtered_assignments.sort_values("due_date"),
            use_container_width=True,
            hide_index=True
        )

        csv_download_button(
            assignments,
            "assignments.csv",
            "⬇️ Download Assignments CSV"
        )

        st.subheader("Update Assignment Status")

        selected_id = st.selectbox(
            "Select assignment ID",
            assignments["id"].tolist(),
            key="assignment_status_id"
        )

        selected_assignment = assignments[
            assignments["id"] == selected_id
        ].iloc[0]

        new_status = st.selectbox(
            "New status",
            ["Pending", "Completed"],
            index=(
                0 if selected_assignment["status"] == "Pending" else 1
            )
        )

        if st.button("Update Assignment Status"):
            update_assignment_status(
                int(selected_id),
                new_status
            )

            st.success("Assignment status updated.")
            st.rerun()

        st.subheader("Delete an Assignment")

        delete_id = st.selectbox(
            "Select assignment ID to delete",
            assignments["id"].tolist(),
            key="delete_assignment_id"
        )

        if st.button("Delete Selected Assignment"):
            delete_record("assignments", int(delete_id))
            st.success("Assignment deleted.")
            st.rerun()

    else:
        st.info("No assignments have been added yet.")


# --------------------------------------------------
# 9. ANALYTICS
# --------------------------------------------------

elif page == "Analytics":

    st.title("📈 Academic Analytics")

    st.write(
        "Explore your study patterns and academic performance."
    )

    study = read_table("study_sessions")
    exams = read_table("exam_results")

    if not study.empty:

        st.subheader("Study Hours by Subject")

        subject_hours = (
            study.groupby("subject")["hours"]
            .sum()
            .reset_index()
            .sort_values("hours", ascending=False)
        )

        fig, ax = plt.subplots(figsize=(9, 5))

        sns.barplot(
            data=subject_hours,
            x="subject",
            y="hours",
            ax=ax
        )

        ax.set_xlabel("Subject")
        ax.set_ylabel("Total Study Hours")
        ax.tick_params(axis="x", rotation=30)
        fig.tight_layout()

        show_chart(fig)

        st.subheader("Daily Study Trend")

        daily_hours = (
            study.groupby("study_date")["hours"]
            .sum()
            .reset_index()
            .sort_values("study_date")
        )

        fig, ax = plt.subplots(figsize=(9, 5))

        sns.lineplot(
            data=daily_hours,
            x="study_date",
            y="hours",
            marker="o",
            ax=ax
        )

        ax.set_xlabel("Date")
        ax.set_ylabel("Study Hours")
        ax.tick_params(axis="x", rotation=30)
        fig.tight_layout()

        show_chart(fig)

        st.subheader("Study Statistics")

        st.write(
            f"Total recorded study hours: "
            f"{study['hours'].sum():.1f}"
        )

        st.write(
            f"Average session duration: "
            f"{study['hours'].mean():.2f} hours"
        )

        st.write(
            f"Longest study session: "
            f"{study['hours'].max():.1f} hours"
        )

    else:
        st.info("Add study sessions to view study analytics.")

    st.divider()

    if not exams.empty:

        st.subheader("Exam Performance by Subject")

        fig, ax = plt.subplots(figsize=(9, 5))

        sns.barplot(
            data=exams,
            x="subject",
            y="marks",
            ax=ax
        )

        ax.set_xlabel("Subject")
        ax.set_ylabel("Marks (%)")
        ax.set_ylim(0, 100)
        ax.tick_params(axis="x", rotation=30)
        fig.tight_layout()

        show_chart(fig)

        st.subheader("Exam Statistics")

        st.write(f"Average marks: {exams['marks'].mean():.2f}%")
        st.write(f"Highest marks: {exams['marks'].max():.2f}%")
        st.write(f"Lowest marks: {exams['marks'].min():.2f}%")

        if len(exams) >= 2:
            sorted_exams = exams.sort_values("exam_date")

            first_marks = float(sorted_exams.iloc[0]["marks"])
            latest_marks = float(sorted_exams.iloc[-1]["marks"])

            difference = latest_marks - first_marks

            if difference > 0:
                st.success(
                    f"Your latest recorded mark is up by "
                    f"{difference:.1f} percentage points."
                )
            elif difference < 0:
                st.warning(
                    f"Your latest recorded mark is down by "
                    f"{abs(difference):.1f} percentage points."
                )
            else:
                st.info(
                    "Your first and latest recorded marks are equal."
                )

    else:
        st.info("Add exam results to view performance analytics.")


# --------------------------------------------------
# 10. PERSONALIZED RECOMMENDATIONS
# --------------------------------------------------

elif page == "Recommendations":

    st.title("💡 Personalized Recommendations")

    study = read_table("study_sessions")
    exams = read_table("exam_results")
    assignments = read_table("assignments")

    if study.empty:
        st.info(
            "Add some study sessions to receive "
            "study-related recommendations."
        )
    else:
        total_hours = float(study["hours"].sum())
        average_session = float(study["hours"].mean())

        st.subheader("📖 Study Habits")

        if total_hours < 10:
            st.warning(
                "Your recorded study time is below 10 hours. "
                "Try setting a realistic daily study target."
            )
        else:
            st.success(
                f"You have recorded {total_hours:.1f} study hours. "
                "Keep building a consistent routine!"
            )

        if average_session < 1:
            st.info(
                "Your average study session is short. "
                "Consider longer focused sessions with breaks."
            )
        else:
            st.info(
                f"Your average study session is "
                f"{average_session:.1f} hours."
            )

        subject_hours = (
            study.groupby("subject")["hours"]
            .sum()
            .sort_values()
        )

        if not subject_hours.empty:
            st.subheader("📚 Subject Study Balance")

            st.write(
                f"Your lowest recorded study time is for "
                f"**{subject_hours.index[0]}** "
                f"({subject_hours.iloc[0]:.1f} hours). "
                "Consider allocating more study time to this subject "
                "if it is important to your goals."
            )

    if not exams.empty:
        average_marks = float(exams["marks"].mean())

        st.subheader("📝 Academic Performance")

        if average_marks < 50:
            st.warning(
                "Your average recorded marks are below 50%. "
                "Review difficult topics and practice questions regularly."
            )
        elif average_marks < 75:
            st.info(
                "Your average marks are moderate. "
                "Use revision sessions and practice tests to improve."
            )
        else:
            st.success(
                "Your average recorded marks are strong. "
                "Continue revising to maintain your performance."
            )

        subject_marks = (
            exams.groupby("subject")["marks"]
            .mean()
            .sort_values()
        )

        if not subject_marks.empty:
            st.write(
                f"Your lowest average subject mark is "
                f"**{subject_marks.index[0]}** "
                f"({subject_marks.iloc[0]:.1f}%). "
                "Consider giving this subject additional revision time."
            )

    if not assignments.empty:
        pending_count = int(
            (assignments["status"] == "Pending").sum()
        )

        st.subheader("📌 Assignment Management")

        if pending_count > 0:
            st.warning(
                f"You have {pending_count} pending assignment(s). "
                "Prioritize those with the nearest due dates."
            )
        else:
            st.success("All recorded assignments are completed!")

        today_date = date.today().isoformat()

        pending = assignments[
            assignments["status"] == "Pending"
        ]

        overdue = pending[pending["due_date"] < today_date]

        if not overdue.empty:
            st.error(
                f"You have {len(overdue)} overdue assignment(s). "
                "Review their deadlines and plan your next steps."
            )

    st.caption(
        "Recommendations are generated using simple rules based "
        "on the data entered; they are not professional academic advice."
    )


# --------------------------------------------------
# 11. DATA EXPORT
# --------------------------------------------------

elif page == "Data Export":

    st.title("📦 Data Export")

    st.write(
        "Download your StudyPulse data for backup or further analysis."
    )

    study = read_table("study_sessions")
    exams = read_table("exam_results")
    assignments = read_table("assignments")

    st.subheader("Export Individual Datasets")

    col1, col2, col3 = st.columns(3)

    with col1:
        csv_download_button(
            study,
            "study_sessions.csv",
            "⬇️ Study Sessions"
        )

    with col2:
        csv_download_button(
            exams,
            "exam_results.csv",
            "⬇️ Exam Results"
        )

    with col3:
        csv_download_button(
            assignments,
            "assignments.csv",
            "⬇️ Assignments"
        )

    st.divider()

    st.subheader("Export All Data")

    st.write(
        "Download all three datasets together in a single ZIP file."
    )

    zip_data = make_zip_export()

    st.download_button(
        label="📥 Download Complete Data Backup",
        data=zip_data,
        file_name="studypulse_backup.zip",
        mime="application/zip"
    )

    st.success(
        "Your data remains stored locally in the SQLite database "
        "until you delete it or remove the database file."
    )


# --------------------------------------------------
# 12. FOOTER
# --------------------------------------------------

st.sidebar.divider()
st.sidebar.caption("StudyPulse | Python Micro Project")