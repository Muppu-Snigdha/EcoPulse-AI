"""
dashboard/profile.py
--------------------
User profile page — view account info, update name, change password.
"""
from __future__ import annotations
import streamlit as st
from auth.db import get_user_by_email, update_full_name, verify_password, reset_password
from auth.session import current_user, login

_MIN_PASSWORD_LENGTH = 8


def render() -> None:
    user = current_user()
    db_user = get_user_by_email(user["email"])

    st.markdown("""
    <div class="ep-page-header">
        <div class="ep-page-title">👤 Profile</div>
        <div class="ep-page-subtitle">Manage your EcoPulse AI account</div>
    </div>
    """, unsafe_allow_html=True)

    if db_user is None:
        st.error("Could not load profile. Please log out and sign in again.")
        return

    # ---- Profile header card -----------------------------------------------
    initials = "".join(w[0].upper() for w in db_user["full_name"].split()[:2])
    joined = db_user.get("created_at", "")[:10]

    st.markdown(f"""
    <div class="ep-profile-card">
        <div class="ep-profile-header">
            <div class="ep-profile-avatar-lg">{initials}</div>
            <div>
                <div class="ep-profile-name">{db_user["full_name"]}</div>
                <div class="ep-profile-email">{db_user["email"]}</div>
                <div class="ep-profile-joined">Member since {joined}</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    col_left, col_right = st.columns(2)

    # ---- Update display name -----------------------------------------------
    with col_left:
        st.markdown('<div class="ep-card"><div class="ep-card-title">Update Display Name</div></div>',
                    unsafe_allow_html=True)
        with st.form("update_name_form"):
            new_name = st.text_input(
                "Full Name",
                value=db_user["full_name"],
                placeholder="Your full name",
            )
            save_name = st.form_submit_button("Save Name", use_container_width=True, type="primary")

        if save_name:
            if not new_name or not new_name.strip():
                st.error("Name cannot be empty.")
            elif new_name.strip() == db_user["full_name"]:
                st.info("No change detected.")
            else:
                ok = update_full_name(user["email"], new_name.strip())
                if ok:
                    # Update session state with new name
                    login(user["email"], new_name.strip())
                    st.success("✅ Name updated successfully.")
                    st.rerun()
                else:
                    st.error("Could not update name. Please try again.")

    # ---- Change password ---------------------------------------------------
    with col_right:
        st.markdown('<div class="ep-card"><div class="ep-card-title">Change Password</div></div>',
                    unsafe_allow_html=True)

        # Toggle: only show the form after the user explicitly clicks the button
        if "show_change_password" not in st.session_state:
            st.session_state.show_change_password = False

        if not st.session_state.show_change_password:
            if st.button("🔒 Change Password", use_container_width=True, key="toggle_change_pass"):
                st.session_state.show_change_password = True
                st.rerun()
        else:
            with st.form("change_password_form"):
                current_pass = st.text_input(
                    "Current Password", type="password", placeholder="Enter current password"
                )
                new_pass = st.text_input(
                    "New Password",
                    type="password",
                    placeholder=f"Min {_MIN_PASSWORD_LENGTH} characters",
                )
                confirm_pass = st.text_input(
                    "Confirm New Password", type="password", placeholder="Repeat new password"
                )
                col_save, col_cancel = st.columns(2)
                with col_save:
                    save_pass = st.form_submit_button("Save", use_container_width=True, type="primary")
                with col_cancel:
                    cancel = st.form_submit_button("Cancel", use_container_width=True)

            if cancel:
                st.session_state.show_change_password = False
                st.rerun()

            if save_pass:
                if not current_pass:
                    st.error("Please enter your current password.")
                elif not verify_password(user["email"], current_pass):
                    st.error("Current password is incorrect.")
                elif len(new_pass) < _MIN_PASSWORD_LENGTH:
                    st.error(f"New password must be at least {_MIN_PASSWORD_LENGTH} characters.")
                elif new_pass != confirm_pass:
                    st.error("New passwords do not match.")
                elif new_pass == current_pass:
                    st.error("New password must be different from current password.")
                else:
                    ok = reset_password(user["email"], new_pass)
                    if ok:
                        st.session_state.show_change_password = False
                        st.success("✅ Password changed successfully.")
                    else:
                        st.error("Could not update password. Please try again.")

    # ---- Account info (read-only) ------------------------------------------
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<div class="ep-card"><div class="ep-card-title">Account Information</div></div>',
                unsafe_allow_html=True)
    info_rows = {
        "Email address": db_user["email"],
        "Account type": "Local (SQLite)",
        "Data scope": "Session only — no cloud storage",
        "Password storage": "bcrypt hash — never stored in plaintext",
        "Member since": joined,
    }
    for label, value in info_rows.items():
        col_l, col_r = st.columns([1, 2])
        col_l.caption(label)
        col_r.markdown(f"**{value}**")
