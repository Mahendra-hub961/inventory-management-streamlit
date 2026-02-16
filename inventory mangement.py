import streamlit as st
import sqlite3
import pandas as pd
import hashlib
from datetime import datetime

# ================= DATABASE =================

conn = sqlite3.connect("inventory.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    username TEXT PRIMARY KEY,
    password TEXT,
    role TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sku TEXT UNIQUE,
    name TEXT,
    category TEXT,
    quantity INTEGER,
    price REAL,
    low_stock INTEGER
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS sales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_name TEXT,
    quantity INTEGER,
    total REAL,
    date TEXT
)
""")

conn.commit()

# ================= SECURITY =================

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# Default admin
cursor.execute("SELECT * FROM users WHERE username='admin'")
if not cursor.fetchone():
    cursor.execute(
        "INSERT INTO users VALUES (?,?,?)",
        ("admin", hash_password("admin123"), "Admin")
    )
    conn.commit()

# ================= SESSION =================

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.role = None
    st.session_state.username = None

# ================= LOGIN PAGE =================

def login():
    st.title("📦 Inventory Management System")
    st.subheader("🔐 User Login")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        user = cursor.execute(
            "SELECT * FROM users WHERE username=?",
            (username,)
        ).fetchone()

        if user and user[1] == hash_password(password):
            st.session_state.logged_in = True
            st.session_state.role = user[2]
            st.session_state.username = username
            st.success("Login Successful")
            st.rerun()
        else:
            st.error("Invalid credentials")

if not st.session_state.logged_in:
    login()
    st.stop()

# ================= SIDEBAR =================

st.sidebar.title(f"👤 {st.session_state.username}")
menu = st.sidebar.selectbox("Menu", [
    "Dashboard",
    "Products",
    "Stock Movement",
    "Sales",
    "Reports",
    "User Management"
])

if st.sidebar.button("Logout"):
    st.session_state.logged_in = False
    st.rerun()

# ================= DASHBOARD =================

if menu == "Dashboard":
    st.title("📊 Dashboard")

    products = pd.read_sql("SELECT * FROM products", conn)
    sales = pd.read_sql("SELECT * FROM sales", conn)

    if not products.empty:
        total_products = len(products)
        total_value = (products["quantity"] * products["price"]).sum()
        low_stock = len(products[products["quantity"] <= products["low_stock"]])

        col1, col2, col3 = st.columns(3)
        col1.metric("Total Products", total_products)
        col2.metric("Inventory Value", f"${total_value:.2f}")
        col3.metric("Low Stock Alerts", low_stock)

        st.subheader("Stock Overview")
        st.bar_chart(products.set_index("name")["quantity"])

    if not sales.empty:
        st.subheader("Revenue Overview")
        st.metric("Total Revenue", f"${sales['total'].sum():.2f}")
        st.bar_chart(sales.groupby("product_name")["quantity"].sum())

# ================= PRODUCTS =================

elif menu == "Products":
    st.title("📦 Product Management")
    action = st.radio("Select Action", ["Add", "View", "Update", "Delete"])

    if action == "Add":
        sku = st.text_input("SKU")
        name = st.text_input("Product Name")
        category = st.text_input("Category")
        quantity = st.number_input("Quantity", min_value=0)
        price = st.number_input("Price", min_value=0.0)
        low_stock = st.number_input("Low Stock Threshold", min_value=1)

        if st.button("Add Product"):
            try:
                cursor.execute("""
                INSERT INTO products (sku,name,category,quantity,price,low_stock)
                VALUES (?,?,?,?,?,?)
                """, (sku, name, category, quantity, price, low_stock))
                conn.commit()
                st.success("Product Added Successfully")
            except:
                st.error("SKU must be unique")

    elif action == "View":
        df = pd.read_sql("SELECT * FROM products", conn)
        st.dataframe(df)

    elif action == "Update":
        df = pd.read_sql("SELECT * FROM products", conn)
        if not df.empty:
            sku = st.selectbox("Select SKU", df["sku"])
            new_qty = st.number_input("New Quantity", min_value=0)
            new_price = st.number_input("New Price", min_value=0.0)

            if st.button("Update"):
                cursor.execute(
                    "UPDATE products SET quantity=?, price=? WHERE sku=?",
                    (new_qty, new_price, sku)
                )
                conn.commit()
                st.success("Product Updated")

    elif action == "Delete":
        df = pd.read_sql("SELECT * FROM products", conn)
        if not df.empty:
            sku = st.selectbox("Select SKU to Delete", df["sku"])

            if st.button("Delete"):
                cursor.execute("DELETE FROM products WHERE sku=?", (sku,))
                conn.commit()
                st.success("Product Deleted")

# ================= STOCK MOVEMENT =================

elif menu == "Stock Movement":
    st.title("🔄 Stock Movement")

    df = pd.read_sql("SELECT * FROM products", conn)
    if not df.empty:
        sku = st.selectbox("Select SKU", df["sku"])
        movement = st.radio("Type", ["Stock In", "Stock Out"])
        qty = st.number_input("Quantity", min_value=1)

        if st.button("Submit"):
            current = cursor.execute(
                "SELECT quantity FROM products WHERE sku=?",
                (sku,)
            ).fetchone()[0]

            if movement == "Stock In":
                new_qty = current + qty
            else:
                if qty > current:
                    st.error("Not enough stock")
                    st.stop()
                new_qty = current - qty

            cursor.execute(
                "UPDATE products SET quantity=? WHERE sku=?",
                (new_qty, sku)
            )
            conn.commit()
            st.success("Stock Updated")

# ================= SALES =================

elif menu == "Sales":
    st.title("🧾 Sales Module")

    df = pd.read_sql("SELECT * FROM products", conn)
    if not df.empty:
        sku = st.selectbox("Select SKU", df["sku"])
        qty = st.number_input("Quantity Sold", min_value=1)

        if st.button("Complete Sale"):
            product = cursor.execute(
                "SELECT name, quantity, price FROM products WHERE sku=?",
                (sku,)
            ).fetchone()

            if qty > product[1]:
                st.error("Not enough stock")
            else:
                total = qty * product[2]
                new_qty = product[1] - qty

                cursor.execute(
                    "UPDATE products SET quantity=? WHERE sku=?",
                    (new_qty, sku)
                )

                cursor.execute("""
                INSERT INTO sales (product_name,quantity,total,date)
                VALUES (?,?,?,?)
                """, (product[0], qty, total,
                      datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

                conn.commit()
                st.success(f"Sale Completed | Total ${total:.2f}")

# ================= REPORTS =================

elif menu == "Reports":
    st.title("📁 Sales Reports")

    sales_df = pd.read_sql("SELECT * FROM sales", conn)

    if not sales_df.empty:
        st.dataframe(sales_df)

        st.download_button(
            "Download Sales CSV",
            sales_df.to_csv(index=False),
            "sales_report.csv"
        )
    else:
        st.info("No sales data available.")

# ================= USER MANAGEMENT =================

elif menu == "User Management":

    if st.session_state.role != "Admin":
        st.error("Only Admin can manage users")
        st.stop()

    st.title("👥 User Management")

    new_user = st.text_input("New Username")
    new_pass = st.text_input("New Password", type="password")
    role = st.selectbox("Role", ["Admin", "Staff"])

    if st.button("Create User"):
        try:
            cursor.execute(
                "INSERT INTO users VALUES (?,?,?)",
                (new_user, hash_password(new_pass), role)
            )
            conn.commit()
            st.success("User Created Successfully")
        except:
            st.error("Username already exists")
