import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import date

# ------------------- PAGE CONFIG -------------------
st.set_page_config(page_title="Small Business Inventory & Sales Manager", layout="wide")

# ------------------- STYLING -------------------
st.markdown("""
    <style>
    [data-testid="stSidebar"] {
        background-color: #0e1117;
        padding: 20px;
    }
    .sidebar-title {
        color: white;
        font-size: 1.3rem;
        font-weight: 600;
        margin-bottom: 1rem;
    }
    .sidebar-button {
        display: block;
        width: 100%;
        padding: 12px 18px;
        margin-bottom: 10px;
        background-color: #1c1c1e;
        border: 1px solid #333;
        color: white;
        font-weight: 500;
        border-radius: 8px;
        text-align: left;
        cursor: pointer;
    }
    .sidebar-button:hover {
        background-color: #2c2c2e;
        border-color: #444;
    }
    .metric-card {
        background: #1e1e1e;
        padding: 20px;
        border-radius: 12px;
        text-align: center;
        color: #fff;
    }
    .metric-value {
        font-size: 1.6rem;
        font-weight: 700;
        margin-top: 5px;
    }
    </style>
""", unsafe_allow_html=True)

# ------------------- GOOGLE SHEETS SETUP -------------------
SCOPE = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_file("credentials.json", scopes=SCOPE)
client = gspread.authorize(creds)

SHEET_NAME = "Business"  # replace if different
sheet = client.open(SHEET_NAME)
inventory_ws = sheet.worksheet("Inventory")
sales_ws = sheet.worksheet("Sales")
purchases_ws = sheet.worksheet("Purchases")

# ------------------- UTILITIES -------------------
def get_df(ws):
    data = ws.get_all_records()
    df = pd.DataFrame(data)
    df.columns = [c.strip().title() for c in df.columns]
    return df

def append_row_dynamic(ws, data_dict):
    headers = [h.strip() for h in ws.row_values(1)]
    row = []
    for hdr in headers:
        value = ""
        for k, v in data_dict.items():
            if k.strip().lower() == hdr.lower():
                value = v
                break
        row.append(value)
    ws.append_row(row, value_input_option="USER_ENTERED")

def delete_row(ws, match_dict):
    df = get_df(ws)
    for i, row in df.iterrows():
        match = True
        for k, v in match_dict.items():
            if str(row.get(k, "")).strip() != str(v).strip():
                match = False
                break
        if match:
            ws.delete_rows(i + 2)
            return True
    return False

# ------------------- SIDEBAR -------------------
st.sidebar.markdown("<div class='sidebar-title'>Menu</div>", unsafe_allow_html=True)
menu_options = ["Dashboard", "Record Sale", "Record Purchase", "View Inventory"]

if "menu" not in st.session_state:
    st.session_state.menu = "Dashboard"

for option in menu_options:
    if st.sidebar.button(option, key=option, use_container_width=True):
        st.session_state.menu = option

menu = st.session_state.menu

# ------------------- DASHBOARD -------------------
if menu == "Dashboard":
    st.title("Dashboard")

    sales_df = get_df(sales_ws)
    purchases_df = get_df(purchases_ws)

    # Calculate totals
    sales_df["Total"] = sales_df.get("Units Sold", 0) * sales_df.get("Selling Price", 0)
    purchases_df["Total"] = purchases_df.get("Units Bought", 0) * purchases_df.get("Buying Price", 0)

    total_revenue = sales_df["Total"].sum() if not sales_df.empty else 0
    total_expense = purchases_df["Total"].sum() if not purchases_df.empty else 0
    profit = total_revenue - total_expense

    # Dashboard cards
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f"<div class='metric-card'><div><b>Total Revenue</b></div><div class='metric-value'>₹{total_revenue:,.2f}</div></div>", unsafe_allow_html=True)
    with c2:
        st.markdown(f"<div class='metric-card'><div><b>Total Expense</b></div><div class='metric-value'>₹{total_expense:,.2f}</div></div>", unsafe_allow_html=True)
    with c3:
        color = "#00c67a" if profit >= 0 else "#e05b5b"
        st.markdown(f"<div class='metric-card'><div><b>Profit / Loss</b></div><div class='metric-value' style='color:{color}'>₹{profit:,.2f}</div></div>", unsafe_allow_html=True)

# ------------------- RECORD SALE -------------------
elif menu == "Record Sale":
    st.title("Record a Sale")

    inv_df = get_df(inventory_ws)
    items = inv_df["Item Name"].tolist() if not inv_df.empty else []
    selected_item = st.selectbox("Select Item", items)
    units_sold = st.number_input("Units Sold", min_value=1, step=1)
    sell_price = st.number_input("Selling Price (per unit ₹)", min_value=0.0, step=0.5)
    sale_date = st.date_input("Date of Sale", value=date.today())

    total = units_sold * sell_price
    st.markdown(f"**Total:** ₹{total:,.2f}")

    if st.button("Record Sale"):
        append_row_dynamic(sales_ws, {
            "Date": str(sale_date),
            "Item Name": selected_item,
            "Units Sold": int(units_sold),
            "Selling Price": float(sell_price)
        })
        st.success("✅ Sale recorded successfully!")

    st.markdown("---")
    st.subheader("Delete a Sale Record")
    sales_df = get_df(sales_ws)
    if sales_df.empty:
        st.info("No sale records to delete.")
    else:
        sale_to_delete = st.selectbox("Select sale to delete", sales_df.apply(lambda x: f"{x['Item Name']} | {x['Date']}", axis=1))
        if st.button("Delete Selected Sale"):
            row = sales_df[sales_df.apply(lambda x: f"{x['Item Name']} | {x['Date']}", axis=1) == sale_to_delete].iloc[0]
            deleted = delete_row(sales_ws, {"Date": row["Date"], "Item Name": row["Item Name"], "Units Sold": row["Units Sold"]})
            if deleted:
                st.success("🗑️ Sale record deleted successfully.")
            else:
                st.error("Record not found or already deleted.")

# ------------------- RECORD PURCHASE -------------------
elif menu == "Record Purchase":
    st.title("Record a Purchase")

    item = st.text_input("Item Name (existing or new)")
    units_bought = st.number_input("Units Bought", min_value=1, step=1)
    buy_price = st.number_input("Buying Price (per unit ₹)", min_value=0.0, step=0.5)
    purchase_date = st.date_input("Date of Purchase", value=date.today())

    total = units_bought * buy_price
    st.markdown(f"**Total:** ₹{total:,.2f}")

    if st.button("Record Purchase"):
        append_row_dynamic(purchases_ws, {
            "Date": str(purchase_date),
            "Item Name": item,
            "Units Bought": int(units_bought),
            "Buying Price": float(buy_price)
        })
        st.success("✅ Purchase recorded successfully!")

    st.markdown("---")
    st.subheader("Delete a Purchase Record")
    purchases_df = get_df(purchases_ws)
    if purchases_df.empty:
        st.info("No purchase records to delete.")
    else:
        purchase_to_delete = st.selectbox("Select purchase to delete", purchases_df.apply(lambda x: f"{x['Item Name']} | {x['Date']}", axis=1))
        if st.button("Delete Selected Purchase"):
            row = purchases_df[purchases_df.apply(lambda x: f"{x['Item Name']} | {x['Date']}", axis=1) == purchase_to_delete].iloc[0]
            deleted = delete_row(purchases_ws, {"Date": row["Date"], "Item Name": row["Item Name"], "Units Bought": row["Units Bought"]})
            if deleted:
                st.success("🗑️ Purchase record deleted successfully.")
            else:
                st.error("Record not found or already deleted.")

# ------------------- VIEW INVENTORY -------------------
elif menu == "View Inventory":
    st.title("View Inventory")
    inv_df = get_df(inventory_ws)
    if inv_df.empty:
        st.info("No inventory data available.")
    else:
        st.dataframe(inv_df, use_container_width=True)
