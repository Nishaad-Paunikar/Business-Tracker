import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# =========================
# PAGE CONFIG
# =========================
st.set_page_config(page_title="Inventory & Sales Manager", layout="wide")

# =========================
# STYLING
# =========================
st.markdown("""
    <style>
    /* Hide Streamlit default footer & menu */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background-color: #0e1117;
        padding-top: 1.5rem;
    }
    .sidebar-button {
        display: block;
        text-align: center;
        background-color: #1e1e1e;
        color: white;
        border-radius: 10px;
        padding: 0.6rem;
        margin: 0.4rem 0;
        text-decoration: none;
        transition: all 0.2s;
        font-weight: 500;
    }
    .sidebar-button:hover {
        background-color: #2c2c2c;
    }
    h1, h2, h3 {
        color: white !important;
    }
    .metric-card {
        background-color: #1e1e1e;
        padding: 1rem;
        border-radius: 12px;
        text-align: center;
        color: white;
        box-shadow: 0 0 10px rgba(255,255,255,0.1);
    }
    </style>
""", unsafe_allow_html=True)

# =========================
# GOOGLE SHEETS CONNECTION
# =========================
SCOPE = ["https://www.googleapis.com/auth/spreadsheets",
         "https://www.googleapis.com/auth/drive"]

creds_dict = st.secrets["gcp_service_account"]
creds = Credentials.from_service_account_info(dict(creds_dict), scopes=SCOPE)
client = gspread.authorize(creds)

SHEET_ID = "1xRzv1vE3cz-bN7En0qFpgkGbkxabSuM0eBKzMDhpXq0"  # Replace with your Google Sheet ID
sheet = client.open_by_key(SHEET_ID)

inventory_ws = sheet.worksheet("Inventory")
sales_ws = sheet.worksheet("Sales")
purchases_ws = sheet.worksheet("Purchases")

# =========================
# SIDEBAR NAVIGATION
# =========================
st.sidebar.title("📦 Menu")

menu_option = st.sidebar.radio(
    "Navigation", 
    ["Dashboard", "Record Sale", "Record Purchase", "View Inventory"],
    label_visibility="collapsed"
)

# =========================
# DASHBOARD
# =========================
if menu_option == "Dashboard":
    st.title("Inventory & Sales Dashboard")

    # Load data
    inv_df = pd.DataFrame(inventory_ws.get_all_records())
    sales_df = pd.DataFrame(sales_ws.get_all_records())
    purchase_df = pd.DataFrame(purchases_ws.get_all_records())

    col1, col2, col3 = st.columns(3)

    with col1:
        total_revenue = sales_df["Total"].sum() if not sales_df.empty else 0
        st.markdown(f"<div class='metric-card'><h3>Total Revenue</h3><h2>₹{total_revenue:,.2f}</h2></div>", unsafe_allow_html=True)

    with col2:
        total_expense = purchase_df["Total"].sum() if not purchase_df.empty else 0
        st.markdown(f"<div class='metric-card'><h3>Total Expense</h3><h2>₹{total_expense:,.2f}</h2></div>", unsafe_allow_html=True)

    with col3:
        profit = total_revenue - total_expense
        profit_color = "green" if profit >= 0 else "red"
        st.markdown(f"<div class='metric-card'><h3>Profit / Loss</h3><h2 style='color:{profit_color};'>₹{profit:,.2f}</h2></div>", unsafe_allow_html=True)

    st.markdown("### ")
    st.markdown("### 📊 Most Sold Items")

    if not sales_df.empty:
        top_sales = sales_df.groupby("Item")["Quantity"].sum().sort_values(ascending=False).head(5)
        st.bar_chart(top_sales)
    else:
        st.info("No sales data yet.")

# =========================
# RECORD A SALE
# =========================
elif menu_option == "Record Sale":
    st.title("💰 Record a Sale")

    inv_df = pd.DataFrame(inventory_ws.get_all_records())

    if inv_df.empty:
        st.warning("No items in inventory.")
    else:
        item = st.selectbox("Select Item", inv_df["Item"])
        quantity = st.number_input("Quantity Sold", min_value=1, step=1)
        date = st.date_input("Date of Sale", datetime.today())

        selected_item = inv_df[inv_df["Item"] == item].iloc[0]
        price = selected_item["Sell Price"]
        total = quantity * price

        st.write(f"**Total Sale Amount:** ₹{total:,.2f}")

        if st.button("Record Sale"):
            new_sale = [item, quantity, price, total, str(date)]
            sales_ws.append_row(new_sale)
            current_stock = int(selected_item["Stock"]) - quantity
            inventory_ws.update_cell(inv_df.index[inv_df["Item"] == item][0] + 2, 4, current_stock)
            st.success("✅ Sale recorded successfully!")

# =========================
# RECORD A PURCHASE
# =========================
elif menu_option == "Record Purchase":
    st.title("📦 Record a Purchase")

    inv_df = pd.DataFrame(inventory_ws.get_all_records())
    existing_items = list(inv_df["Item"]) if not inv_df.empty else []

    item = st.text_input("Item Name (exact or new)")
    quantity = st.number_input("Quantity Purchased", min_value=1, step=1)
    buy_price = st.number_input("Buy Price per Unit (₹)", min_value=0.0, step=0.1)
    date = st.date_input("Date of Purchase", datetime.today())

    total = quantity * buy_price
    st.write(f"**Total Purchase Cost:** ₹{total:,.2f}")

    if st.button("Record Purchase"):
        purchases_ws.append_row([item, quantity, buy_price, total, str(date)])

        if item in existing_items:
            current_stock = int(inv_df.loc[inv_df["Item"] == item, "Stock"].values[0]) + quantity
            inventory_ws.update_cell(inv_df.index[inv_df["Item"] == item][0] + 2, 4, current_stock)
        else:
            inventory_ws.append_row([item, buy_price, buy_price * 1.2, quantity])  # auto-add new item with sell price = 1.2x buy
        st.success("✅ Purchase recorded successfully!")

# =========================
# VIEW INVENTORY
# =========================
elif menu_option == "View Inventory":
    st.title("📋 Inventory Overview")

    inv_df = pd.DataFrame(inventory_ws.get_all_records())

    if inv_df.empty:
        st.info("Inventory is empty.")
    else:
        st.dataframe(inv_df)
