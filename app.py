
import streamlit as st
import sqlite3
import hashlib
import secrets
import pandas as pd
from datetime import date

st.set_page_config(
    page_title="Smart Expense Tracker",
    page_icon="💰"
)

DB = "expenses.db"


def get_db():
    return sqlite3.connect(DB)


def make_password(password, salt=None):
    if salt is None:
        salt = secrets.token_hex(16)

    hashed = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        200000
    ).hex()

    return salt, hashed


def setup():
    with get_db() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                salt TEXT NOT NULL,
                password_hash TEXT NOT NULL
            )
        """)

        con.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                item TEXT NOT NULL,
                category TEXT NOT NULL,
                amount REAL NOT NULL,
                expense_date TEXT NOT NULL
            )
        """)


def register(username, password):
    username = username.strip().lower()

    if not username or len(password) < 8:
        return False, "Username required; password must be 8+ characters."

    salt, hashed = make_password(password)

    try:
        with get_db() as con:
            con.execute(
                """INSERT INTO users
                   (username, salt, password_hash)
                   VALUES (?, ?, ?)""",
                (username, salt, hashed)
            )
        return True, "Account created! Please log in."
    except sqlite3.IntegrityError:
        return False, "Username already exists."


def login(username, password):
    with get_db() as con:
        user = con.execute(
            """SELECT id, salt, password_hash
               FROM users WHERE username = ?""",
            (username.strip().lower(),)
        ).fetchone()

    if user:
        _, hashed = make_password(password, user[1])

        if secrets.compare_digest(hashed, user[2]):
            return user[0]

    return None


setup()

if "user_id" not in st.session_state:
    st.session_state.user_id = None

if "username" not in st.session_state:
    st.session_state.username = ""

st.title("💰 Smart Daily Expense Tracker")
st.write("Track your daily expenses easily!")

if st.session_state.user_id is None:

    login_tab, register_tab = st.tabs(
        ["Login", "Create Account"]
    )

    with login_tab:
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input(
                "Password", type="password"
            )
            submit = st.form_submit_button("Login")

            if submit:
                uid = login(username, password)

                if uid is not None:
                    st.session_state.user_id = uid
                    st.session_state.username = username.strip().lower()
                    st.rerun()
                else:
                    st.error("Wrong username or password.")

    with register_tab:
        with st.form("register_form"):
            new_user = st.text_input("Choose username")
            new_pass = st.text_input(
                "Choose password (8+ characters)",
                type="password"
            )
            confirm = st.text_input(
                "Confirm password", type="password"
            )
            create = st.form_submit_button("Register")

            if create:
                if new_pass != confirm:
                    st.error("Passwords do not match.")
                else:
                    ok, message = register(new_user, new_pass)

                    if ok:
                        st.success(message)
                    else:
                        st.error(message)

else:
    uid = st.session_state.user_id

    st.sidebar.write(
        "Logged in: " + st.session_state.username
    )

    if st.sidebar.button("Logout"):
        st.session_state.user_id = None
        st.session_state.username = ""
        st.rerun()

    page = st.sidebar.radio(
        "Choose Page",
        ["Dashboard", "Add Expense", "History"]
    )

    with get_db() as con:
        df = pd.read_sql_query(
            """SELECT item, category, amount, expense_date
               FROM expenses WHERE user_id = ?
               ORDER BY expense_date DESC""",
            con,
            params=(uid,)
        )

    if page == "Dashboard":
        st.subheader("📊 My Dashboard")

        total = df["amount"].sum() if not df.empty else 0

        today_total = (
            df.loc[
                df["expense_date"] == str(date.today()),
                "amount"
            ].sum()
            if not df.empty else 0
        )

        col1, col2 = st.columns(2)
        col1.metric("Total Spending", f"₹{total:.2f}")
        col2.metric("Today's Spending", f"₹{today_total:.2f}")

        if not df.empty:
            st.subheader("Category-wise Spending")
            st.bar_chart(df.groupby("category")["amount"].sum())
            st.dataframe(df, use_container_width=True)
        else:
            st.info("No expenses added yet.")

    elif page == "Add Expense":
        st.subheader("➕ Add Daily Expense")

        with st.form("expense_form"):
            item = st.text_input("Expense name")

            category = st.selectbox(
                "Category",
                [
                    "Food", "Travel", "Education",
                    "Shopping", "Bills", "Health", "Other"
                ]
            )

            amount = st.number_input(
                "Amount (₹)", min_value=0.0, step=10.0
            )

            expense_date = st.date_input(
                "Expense date", value=date.today()
            )

            save = st.form_submit_button("Save Expense")

            if save:
                if not item.strip() or amount <= 0:
                    st.error("Enter an item and amount greater than zero.")
                else:
                    with get_db() as con:
                        con.execute(
                            """INSERT INTO expenses
                               (user_id, item, category,
                                amount, expense_date)
                               VALUES (?, ?, ?, ?, ?)""",
                            (
                                uid, item.strip(), category,
                                amount, str(expense_date)
                            )
                        )

                    st.success("Expense saved!")
                    st.rerun()

    elif page == "History":
        st.subheader("📒 My Expense History")

        if df.empty:
            st.info("No expense records found.")
        else:
            st.dataframe(df, use_container_width=True)

            st.download_button(
                "Download CSV",
                df.to_csv(index=False).encode("utf-8"),
                file_name="my_expenses.csv",
                mime="text/csv"
            )
