"""
app.py — Databricks App: Support Ticketing System

Views:
  - All Tickets: browse every ticket, click into one to see its thread
  - Ticket Detail: view messages, add a message, update status
  - New Ticket: create a ticket

All data is read from / written to Lakebase (Postgres) via lakebase.py — nothing
in this file is hard-coded application data.
"""

import streamlit as st
import lakebase

st.set_page_config(page_title="Support Tickets", page_icon="🎫", layout="wide")

if "selected_ticket_id" not in st.session_state:
    st.session_state.selected_ticket_id = None


def show_ticket_list():
    st.title("🎫 Support Tickets")

    with st.expander("➕ Create a new ticket"):
        with st.form("new_ticket_form", clear_on_submit=True):
            title = st.text_input("Title", max_chars=50)
            created_by = st.text_input("Your username", max_chars=50)
            submitted = st.form_submit_button("Create ticket")
            if submitted:
                if not title.strip() or not created_by.strip():
                    st.error("Title and username are required.")
                else:
                    new_id = lakebase.create_ticket(title.strip(), created_by.strip())
                    st.success(f"Created ticket #{new_id}")
                    st.rerun()

    st.divider()

    tickets = lakebase.get_all_tickets()
    if not tickets:
        st.info("No tickets yet. Create one above.")
        return

    for t in tickets:
        cols = st.columns([1, 4, 2, 2, 2, 1])
        cols[0].write(f"#{t['ticket_id']}")
        cols[1].write(t["title"])
        cols[2].write(_status_badge(t["status"]))
        cols[3].write(t["created_by"])
        cols[4].write(t["created_at"].strftime("%Y-%m-%d %H:%M"))
        if cols[5].button("Open", key=f"open_{t['ticket_id']}"):
            st.session_state.selected_ticket_id = t["ticket_id"]
            st.rerun()


def show_ticket_detail(ticket_id: int):
    ticket = lakebase.get_ticket(ticket_id)
    if not ticket:
        st.error("Ticket not found.")
        st.session_state.selected_ticket_id = None
        return

    if st.button("← Back to all tickets"):
        st.session_state.selected_ticket_id = None
        st.rerun()

    st.title(f"#{ticket['ticket_id']} — {ticket['title']}")
    st.caption(f"Opened by {ticket['created_by']} on {ticket['created_at'].strftime('%Y-%m-%d %H:%M')}")

    status_cols = st.columns([2, 2, 6])
    with status_cols[0]:
        new_status = st.selectbox(
            "Status",
            lakebase.STATUS_OPTIONS,
            index=lakebase.STATUS_OPTIONS.index(ticket["status"])
            if ticket["status"] in lakebase.STATUS_OPTIONS else 0,
        )
    with status_cols[1]:
        st.write("")
        st.write("")
        if st.button("Update status"):
            lakebase.update_ticket_status(ticket_id, new_status)
            st.success("Status updated.")
            st.rerun()

    st.divider()
    st.subheader("Messages")

    messages = lakebase.get_messages(ticket_id)
    for m in messages:
        role_icon = "🧑" if m["author_role"] == "customer" else "🛠️"
        with st.chat_message("user" if m["author_role"] == "customer" else "assistant"):
            st.markdown(f"{role_icon} **{m['author']}** · {m['created_at'].strftime('%Y-%m-%d %H:%M')}")
            st.write(m["message_text"])

    st.divider()
    st.subheader("Add a message")
    with st.form("new_message_form", clear_on_submit=True):
        cols = st.columns([3, 2])
        author = cols[0].text_input("Your name", max_chars=50)
        role = cols[1].selectbox("Role", lakebase.ROLE_OPTIONS)
        message_text = st.text_area("Message", max_chars=50)
        submitted = st.form_submit_button("Send")
        if submitted:
            if not author.strip() or not message_text.strip():
                st.error("Name and message are required.")
            else:
                lakebase.add_message(ticket_id, message_text.strip(), author.strip(), role)
                st.rerun()


def _status_badge(status: str) -> str:
    return {
        "open": "🟢 open",
        "in_progress": "🟡 in_progress",
        "resolved": "🔵 resolved",
    }.get(status, status)


if st.session_state.selected_ticket_id is None:
    show_ticket_list()
else:
    show_ticket_detail(st.session_state.selected_ticket_id)