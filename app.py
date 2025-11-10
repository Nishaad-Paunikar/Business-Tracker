import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# =========================
# PAGE CONFIG
# =========================
st.set_page_config(page_title="Inventory & Sales Manager", layout="wide")

st.markdown("""
<style>
[data-testid="stSidebar"] {
    background-color: #0e1117;
    padding-top: 1rem;
}
.sidebar-button {
    display: block;
    width: 100%;
    text-align: center;
    background-color: #1c1c1c;
    color: white;
    border: 1px solid #333;
    border-radius: 10px;
    padding: 0.5rem 0;
    margin: 0.3rem 0;
    text-decoration: none;
    transition: 0.2s all;
    font-weight: 500;
}
.sidebar-button:hover {
    background-color: #2a2a2a;
    border-color: #444;
}
.metric-card {
    background-color: #1e1e1e;
    padding: 1.5rem;
    border-radius: 15px;
    text-align: center;
    color: white;
    box-shadow: 0 0 10px rgba(255,255,255,0.08);
}
h1, h2, h3 {
    color: white !important;
}
.block-container {
    padding-top: 2rem;
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

SHEET_ID = "1xRzv1vE3cz-bN7En0qFpgkGbkxabSuM0eBKzMDhpXq0"
sheet = client.open_by_key(SHEET_ID)

inventory_ws = sheet.worksheet("Inventory")
sales_ws = sheet.worksheet("Sales")
purchases_ws = sheet.worksheet("Purchases")

# =========================
# HELPER FUNCTIONS
# =========================
def get_df(ws):
    """Reads a Google Sheet into a DataFrame"""
    data = ws.get_all_records()
    df = pd.DataFrame(data)
    if not df.empty:
        df.columns = [c.strip().title() for c in df.columns]
    return df

def append_row_dynamic(ws, data_dict):
    """
    Appends a row to a Google Sheet following the exact column order.
    Automatically matches headers case-insensitively.
    """
    headers = [h.strip() for h in ws.row_values(1)]
    lower_headers = [h.lower() for h in headers]

    row_data = []
    for header in headers:
        key = header.lower()
        matched = None
        for dict_key in data_dict.keys():
            if dict_key.lower() == key:
                matched = dict_key
                break
        row_data.append(data_dict.get(matched, ""))

    # Ensure same number of columns as headers
    row_data = row_data[:len(headers)]
    ws.append_row(row_data, value_input_option="USER_ENTERED")

# =========================
# SIDEBAR MENU
# =========================
st.sidebar.title("Menu")

menu = st.session_state.get("menu", "Dashboard")

def menu_button(label, key):
    if st.sidebar.button(label, key=key, use_container_width=True):
        st.session_state["menu"] = label
        st.rerun()

menu_button("Dashboard", "dashboard")
menu_button("Record Sale", "record_sale")
menu_button("Record Purchase", "record_purchase")
menu_button("View Inventory", "view_inventory")

if "menu" not in st.session_state:
    st.session_state["menu"] = "Dashboard"
menu = st.session_state["menu"]


# =========================
# DASHBOARD
# =========================
if menu == "Dashboard":
    st.title("Dashboard")

    inv_df = get_df(inventory_ws)
    sales_df = get_df(sales_ws)
    purchases_df = get_df(purchases_ws)

    for col in ["Units Sold", "Selling Price"]:
        if col not in sales_df.columns:
            sales_df[col] = 0
    for col in ["Units Bought", "Buying Price"]:
        if col not in purchases_df.columns:
            purchases_df[col] = 0

    sales_df["Total"] = sales_df["Units Sold"] * sales_df["Selling Price"]
    purchases_df["Total"] = purchases_df["Units Bought"] * purchases_df["Buying Price"]

    total_revenue = sales_df["Total"].sum()
    total_expense = purchases_df["Total"].sum()
    profit = total_revenue - total_expense

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f"<div class='metric-card'><h3>Total Revenue</h3><h2>₹{total_revenue:,.2f}</h2></div>", unsafe_allow_html=True)
    with col2:
        st.markdown(f"<div class='metric-card'><h3>Total Expense</h3><h2>₹{total_expense:,.2f}</h2></div>", unsafe_allow_html=True)
    with col3:
        color = "green" if profit >= 0 else "red"
        st.markdown(f"<div class='metric-card'><h3>Profit / Loss</h3><h2 style='color:{color};'>₹{profit:,.2f}</h2></div>", unsafe_allow_html=True)

    st.markdown("<div style='height:40px'></div>", unsafe_allow_html=True)
    st.markdown("### 📊 Most Sold Items")

    if not sales_df.empty and "Item Name" in sales_df.columns:
        top_sales = sales_df.groupby("Item Name")["Units Sold"].sum().sort_values(ascending=False).head(5)
        st.bar_chart(top_sales)
    else:
        st.info("No sales data available yet.")

# =========================
# RECORD SALE
# =========================
elif menu == "Record Sale":
    st.title("Record a Sale")

    inv_df = get_df(inventory_ws)

    if inv_df.empty:
        st.warning("No items in inventory yet.")
    else:
        item = st.selectbox("Select Item", inv_df["Item Name"])
        qty = st.number_input("Units Sold", min_value=1, step=1)
        date = st.date_input("Date of Sale", datetime.today())
        price = st.number_input("Selling Price (per unit ₹)", min_value=0.0, step=0.1)

        total = qty * price
        st.markdown(f"**Total:** ₹{total:.2f}")

        if st.button("Record Sale"):
            append_row_dynamic(sales_ws, {
                "Date": str(date),
                "Item Name": item,
                "Units Sold": qty,
                "Selling Price": price
            })

            if "Stock" in inv_df.columns:
                current_stock = int(inv_df.loc[inv_df["Item Name"] == item, "Stock"].values[0])
                inventory_ws.update_cell(inv_df.index[inv_df["Item Name"] == item][0] + 2, 4, current_stock - qty)

            st.success("✅ Sale recorded successfully!")

# =========================
# RECORD PURCHASE
# =========================
elif menu == "Record Purchase":
    st.title("Record a Purchase")

    inv_df = get_df(inventory_ws)
    existing_items = inv_df["Item Name"].tolist() if not inv_df.empty else []

    item = st.text_input("Item Name (existing or new)")
    qty = st.number_input("Units Bought", min_value=1, step=1)
    buy_price = st.number_input("Buying Price (per unit ₹)", min_value=0.0, step=0.1)
    date = st.date_input("Date of Purchase", datetime.today())

    total = qty * buy_price
    st.markdown(f"**Total:** ₹{total:.2f}")

    if st.button("Record Purchase"):
        append_row_dynamic(purchases_ws, {
            "Date": str(date),
            "Item Name": item,
            "Units Bought": qty,
            "Buying Price": buy_price
        })

        if item in existing_items:
            new_stock = int(inv_df.loc[inv_df["Item Name"] == item, "Stock"].values[0]) + qty
            inventory_ws.update_cell(inv_df.index[inv_df["Item Name"] == item][0] + 2, 4, new_stock)
        else:
            inventory_ws.append_row([item, buy_price, buy_price * 1.2, qty])

        st.success("✅ Purchase recorded successfully!")

# =========================
# VIEW INVENTORY
# =========================
elif menu == "View Inventory":
    st.title("Inventory Overview")

    inv_df = get_df(inventory_ws)

    if inv_df.empty:
        st.info("Inventory is empty.")
    else:
        st.dataframe(inv_df)
