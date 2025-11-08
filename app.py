import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import date

# ---------------- GOOGLE SHEETS CONNECTION ----------------
SCOPE = ["https://www.googleapis.com/auth/spreadsheets",
         "https://www.googleapis.com/auth/drive"]

creds = Credentials.from_service_account_file("credentials.json", scopes=SCOPE)
client = gspread.authorize(creds)

SHEET_ID = "1xRzv1vE3cz-bN7En0qFpgkGbkxabSuM0eBKzMDhpXq0"
sheet = client.open_by_key(SHEET_ID)

inventory_ws = sheet.worksheet("Inventory")
sales_ws = sheet.worksheet("Sales")
purchases_ws = sheet.worksheet("Purchases")

# ---------------- HELPER FUNCTIONS ----------------
def get_df(ws):
    df = pd.DataFrame(ws.get_all_records())
    df.columns = [c.strip().title() for c in df.columns]
    return df

def update_stock(item_name, change):
    inv_df = get_df(inventory_ws)
    if item_name not in inv_df["Item Name"].values:
        return
    row_index = inv_df.index[inv_df["Item Name"] == item_name].tolist()[0] + 2
    current_stock = int(inv_df.loc[inv_df["Item Name"] == item_name, "Stock"].values[0])
    inventory_ws.update_cell(row_index, 4, current_stock + change)

def add_new_item(item_name, buy_price, initial_stock):
    inventory_ws.append_row([item_name, buy_price, 0, initial_stock])

# ---------------- STREAMLIT PAGE CONFIG ----------------
st.set_page_config(page_title="Inventory Dashboard", page_icon="📦", layout="wide")

# ---------- CSS FOR AESTHETIC STYLE ----------
st.markdown("""
<style>
/* ---------------- Global ---------------- */
body {
    background-color: #0E1117 !important;
    color: #FAFAFA !important;
    font-family: 'Inter', sans-serif;
}
h1, h2, h3, h4 {
    color: #FFFFFF !important;
    font-weight: 600 !important;
    letter-spacing: -0.3px;
}
hr {
    border: none;
    border-top: 1px solid #2E2E2E;
    margin: 2rem 0;
}

/* ---------------- Sidebar ---------------- */
section[data-testid="stSidebar"] {
    background-color: #151515 !important;
    padding: 25px 20px 20px 20px !important;
    border-right: 1px solid #222;
}
.sidebar-title {
    color: #B3B3B3;
    font-size: 1.1rem;
    margin-bottom: 12px;
    font-weight: 500;
}
div[data-testid="stSidebar"] .stButton > button {
    background-color: #202020 !important;
    color: #EAEAEA !important;
    border-radius: 8px !important;
    border: 1px solid #333 !important;
    text-align: left !important;
    font-weight: 500 !important;
    margin-bottom: 4px !important;
    padding: 8px 14px !important;
    transition: all 0.15s ease-in-out !important;
}
div[data-testid="stSidebar"] .stButton > button:hover {
    background-color: #333333 !important;
    border-color: #444 !important;
}

/* ---------------- Metric Cards ---------------- */
.metric-card {
    background: #181818;
    border-radius: 10px;
    padding: 24px;
    box-shadow: 0 2px 6px rgba(0,0,0,0.25);
    text-align: center;
    color: #F8F9FA;
    transition: all 0.2s ease;
}
.metric-card:hover {
    transform: translateY(-2px);
}
.metric-value {
    font-size: 2rem;
    font-weight: 700;
    color: #00C67A;
    margin-top: 8px;
}

/* ---------------- Tables ---------------- */
thead tr th {
    background-color: #202020 !important;
    color: #CCCCCC !important;
    font-weight: 600 !important;
    font-size: 0.95rem !important;
    border-bottom: 1px solid #333 !important;
}
tbody tr:nth-child(odd) {
    background-color: #151515 !important;
}
tbody tr:nth-child(even) {
    background-color: #1A1A1A !important;
}
tbody tr:hover {
    background-color: #222 !important;
}
table {
    border-radius: 6px !important;
    overflow: hidden !important;
}
</style>
""", unsafe_allow_html=True)

# ---------------- NAVIGATION ----------------
if "page" not in st.session_state:
    st.session_state.page = "Dashboard"

st.sidebar.markdown("<p class='sidebar-title'>Menu</p>", unsafe_allow_html=True)

def nav_button(label):
    if st.sidebar.button(label, use_container_width=True):
        st.session_state.page = label

pages = ["Dashboard", "Record Sale", "Record Purchase", "View Inventory"]
for p in pages:
    nav_button(p)

choice = st.session_state.page

# ---------------- DASHBOARD ----------------
if choice == "Dashboard":
    st.title("Dashboard")
    inv_df = get_df(inventory_ws)
    sales_df = get_df(sales_ws)

    if not sales_df.empty:
        merged = pd.merge(sales_df, inv_df, on="Item Name", how="left")
        merged["Profit"] = (merged["Sell Price"] - merged["Buy Price"]) * merged["Units Sold"]
        total_sales = (merged["Units Sold"] * merged["Sell Price"]).sum()
        total_cost = (merged["Units Sold"] * merged["Buy Price"]).sum()
        total_profit = merged["Profit"].sum()

        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(f"<div class='metric-card'><p>Total Revenue</p><div class='metric-value'>₹{round(total_sales):,}</div></div>", unsafe_allow_html=True)
        with c2:
            st.markdown(f"<div class='metric-card'><p>Total Cost</p><div class='metric-value'>₹{round(total_cost):,}</div></div>", unsafe_allow_html=True)
        with c3:
            st.markdown(f"<div class='metric-card'><p>Total Profit</p><div class='metric-value'>₹{round(total_profit):,}</div></div>", unsafe_allow_html=True)

        # spacing before chart
        st.markdown("<div style='height:40px;'></div>", unsafe_allow_html=True)

        st.subheader("Most Sold Items")
        sold_chart = merged.groupby("Item Name")["Units Sold"].sum().sort_values(ascending=False)
        st.bar_chart(sold_chart)
    else:
        st.info("No sales recorded yet.")

# ---------------- RECORD SALE ----------------
elif choice == "Record Sale":
    st.title("Record Sale")
    inv_df = get_df(inventory_ws)

    if inv_df.empty:
        st.error("Your inventory is empty. Please record purchases first.")
    else:
        item_name = st.selectbox("Select Item", inv_df["Item Name"])
        stock_available = int(inv_df.loc[inv_df["Item Name"] == item_name, "Stock"].values[0])
        sell_price = st.number_input("Selling Price (₹)", min_value=0.0, value=float(inv_df.loc[inv_df["Item Name"] == item_name, "Sell Price"].values[0]), step=0.5)
        units_sold = st.number_input("Units Sold", min_value=1, max_value=stock_available, step=1)
        sale_date = st.date_input("Date of Sale", value=date.today())

        st.markdown("<div style='margin-top:10px'></div>", unsafe_allow_html=True)

        if st.button("Record Sale"):
            sales_ws.append_row([str(sale_date), item_name, units_sold, sell_price])
            update_stock(item_name, -units_sold)
            inventory_ws.update_cell(inv_df.index[inv_df["Item Name"] == item_name].tolist()[0] + 2, 3, sell_price)
            st.success(f"Sale recorded for {item_name} on {sale_date}. Stock reduced by {units_sold}.")
            st.balloons()

        st.divider()
        st.subheader("Delete Sale Record")
        sales_df = get_df(sales_ws)
        if not sales_df.empty:
            sales_df["Display"] = sales_df["Date"] + " | " + sales_df["Item Name"] + " | " + sales_df["Units Sold"].astype(str)
            selected = st.selectbox("Select sale to delete", sales_df["Display"])
            if st.button("Delete Selected Sale"):
                idx = int(sales_df[sales_df["Display"] == selected].index[0])
                item = sales_df.loc[idx, "Item Name"]
                units = int(sales_df.loc[idx, "Units Sold"])
                sales_ws.delete_rows(int(idx + 2))
                update_stock(item, units)
                st.success(f"Deleted sale of {units} units of {item}. Stock restored.")
        else:
            st.info("No sales to delete.")

# ---------------- RECORD PURCHASE ----------------
elif choice == "Record Purchase":
    st.title("Record Purchase")
    purchases_df = get_df(purchases_ws)
    existing_items = purchases_df["Item Name"].unique().tolist() if not purchases_df.empty else []
    inv_df = get_df(inventory_ws)

    item_name = st.selectbox("Select or Type Item", options=existing_items + ["<Add new item>"])
    if item_name == "<Add new item>":
        item_name = st.text_input("Enter New Item Name").strip()

    buy_price = st.number_input("Buying Price (₹)", min_value=0.0, step=0.5)
    units_bought = st.number_input("Units Bought", min_value=1, step=1)
    purchase_date = st.date_input("Date of Purchase", value=date.today())

    if st.button("Record Purchase"):
        if not item_name:
            st.error("Please enter an item name.")
        else:
            if item_name not in inv_df["Item Name"].values:
                add_new_item(item_name, buy_price, units_bought)
                st.info(f"Added new item '{item_name}' to inventory.")
            else:
                update_stock(item_name, units_bought)
            purchases_ws.append_row([str(purchase_date), item_name, units_bought, buy_price])
            st.success(f"Purchase recorded for {item_name} on {purchase_date}. Stock increased by {units_bought}.")
            st.balloons()

    st.divider()
    st.subheader("Delete Purchase Record")
    if not purchases_df.empty:
        purchases_df["Display"] = purchases_df["Date"] + " | " + purchases_df["Item Name"] + " | " + purchases_df["Units Bought"].astype(str)
        selected = st.selectbox("Select purchase to delete", purchases_df["Display"])
        if st.button("Delete Selected Purchase"):
            idx = int(purchases_df[purchases_df["Display"] == selected].index[0])
            item = purchases_df.loc[idx, "Item Name"]
            units = int(purchases_df.loc[idx, "Units Bought"])
            purchases_ws.delete_rows(int(idx + 2))
            update_stock(item, -units)
            st.success(f"Deleted purchase of {units} units of {item}. Stock reduced.")
    else:
        st.info("No purchases to delete.")

# ---------------- VIEW INVENTORY ----------------
elif choice == "View Inventory":
    st.title("Inventory")
    inv_df = get_df(inventory_ws)
    st.dataframe(inv_df, use_container_width=True)
