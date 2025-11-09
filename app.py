import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import date

# ---------------- PAGE CONFIG ----------------
st.set_page_config(page_title="Inventory Dashboard", layout="wide")

# ---------------- STYLES (rectangular buttons, compact) ----------------
st.markdown("""
<style>
/* Sidebar look */
section[data-testid="stSidebar"] { background-color:#0f1114 !important; padding:18px !important; }
.sidebar-title { color:#cfcfcf; font-size:1rem; margin-bottom:8px; }

/* Streamlit button inside sidebar - rectangular and compact */
div[data-testid="stSidebar"] .stButton > button {
    background-color: #1c1c1e !important;
    color: #fff !important;
    border-radius: 8px !important;
    border: 1px solid #333 !important;
    padding: 7px 12px !important;
    margin-bottom: 4px !important;  /* tight spacing */
    text-align: left !important;
    font-weight: 600 !important;
    width: 100% !important;
}
div[data-testid="stSidebar"] .stButton > button:hover {
    background-color: #2b2b2d !important;
}

/* metric cards */
.metric-card { background:#18181a; border-radius:12px; padding:20px; text-align:center; color:#fff; }
.metric-value { font-size:1.6rem; font-weight:700; color:#00c67a; margin-top:6px; }

/* reduce default container top padding */
.block-container { padding-top: 18px; }
</style>
""", unsafe_allow_html=True)

# ---------------- GOOGLE SHEETS AUTH (via Streamlit Secrets) ----------------
SCOPE = ["https://www.googleapis.com/auth/spreadsheets",
         "https://www.googleapis.com/auth/drive"]

try:
    creds_dict = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(dict(creds_dict), scopes=SCOPE)
    client = gspread.authorize(creds)
except Exception as e:
    st.error("Error reading Google credentials from Streamlit Secrets. "
             "Make sure you added your service account under Settings → Secrets as [gcp_service_account].")
    st.stop()

# ---------------- SHEET OPEN (friendly error if sheet not shared / id incorrect) ----------------
SHEET_ID = "1xRzv1vE3cz-bN7En0qFpgkGbkxabSuM0eBKzMDhpXq0"  # <--- replace if needed
try:
    sheet = client.open_by_key(SHEET_ID)
except Exception as e:
    st.error(
        "Unable to open Google Sheet. Steps to fix:\n"
        "1) Confirm `SHEET_ID` in app.py is correct.\n"
        "2) Share the Google Sheet with the service account email found in your credentials (client_email).\n"
        "3) In Streamlit Cloud Secrets, ensure private key is properly formatted (multi-line) and saved.\n\n"
        "If you already did that, open the app logs (Manage app → Logs) for details."
    )
    st.stop()

# worksheets: will raise if tab names differ — handle later in get_df
try:
    inventory_ws = sheet.worksheet("Inventory")
    sales_ws = sheet.worksheet("Sales")
    purchases_ws = sheet.worksheet("Purchases")
except Exception as e:
    st.error("One or more worksheets (Inventory, Sales, Purchases) not found. "
             "Please ensure the Google Sheet has these exact tab names (case-sensitive).")
    st.stop()

# ---------------- HELPERS ----------------
def get_df(ws):
    """Return a cleaned DataFrame from worksheet; normalise column names."""
    df = pd.DataFrame(ws.get_all_records())
    if df.empty:
        return df
    # normalize column names to predictable canonical forms
    col_map = {}
    # strip, title-case
    df.columns = [c.strip() for c in df.columns]
    # map common variants -> canonical names
    for c in df.columns:
        key = c.lower().replace(" ", "")
        if key in ("item","itemname","item_name","iteamname","itename"):
            col_map[c] = "Item"
        elif key in ("quantity","qty","units","unitssold","units_sold","unitsbought","units_bought"):
            # keep both interpretations possible in different sheets,
            # downstream code will look for "Quantity" or "UnitsBought"
            col_map[c] = "Quantity"
        elif key in ("sellprice","sellingprice","price","unitprice"):
            col_map[c] = "Sell Price"
        elif key in ("buyprice","buyingprice","cost","costperunit"):
            col_map[c] = "Buy Price"
        elif key in ("total","amount","totalamount","costtotal"):
            col_map[c] = "Total"
        elif key in ("date","dates","transactiondate"):
            col_map[c] = "Date"
    if col_map:
        df = df.rename(columns=col_map)
    return df

def safe_numeric_series(s, default=0):
    return pd.to_numeric(s, errors="coerce").fillna(default)

# ---------------- SIDEBAR NAVIGATION (RECTANGULAR BUTTONS) ----------------
if "page" not in st.session_state:
    st.session_state.page = "Dashboard"

st.sidebar.markdown("<div class='sidebar-title'>Menu</div>", unsafe_allow_html=True)

def nav_button(label):
    # key ensures unique button elements
    if st.sidebar.button(label, key=f"btn_{label}", use_container_width=True):
        st.session_state.page = label

for p in ["Dashboard", "Record Sale", "Record Purchase", "View Inventory"]:
    nav_button(p)

page = st.session_state.page

# ---------------- DASHBOARD (robust totals and spacing) ----------------
if page == "Dashboard":
    st.title("Dashboard")

    inv_df = get_df(inventory_ws)
    sales_df = get_df(sales_ws)
    purchases_df = get_df(purchases_ws)

    # Ensure DataFrames have canonical columns and 'Total' if possible
    # Sales: If 'Total' missing, try Quantity * Sell Price
    if not sales_df.empty:
        if "Total" not in sales_df.columns:
            if ("Quantity" in sales_df.columns) and ("Sell Price" in sales_df.columns):
                sales_df["Total"] = safe_numeric_series(sales_df["Quantity"]) * safe_numeric_series(sales_df["Sell Price"])
            else:
                sales_df["Total"] = 0
    else:
        sales_df = pd.DataFrame(columns=["Total"])

    # Purchases: If 'Total' missing, try Quantity * Buy Price
    if not purchases_df.empty:
        if "Total" not in purchases_df.columns:
            if ("Quantity" in purchases_df.columns) and ("Buy Price" in purchases_df.columns):
                purchases_df["Total"] = safe_numeric_series(purchases_df["Quantity"]) * safe_numeric_series(purchases_df["Buy Price"])
            else:
                purchases_df["Total"] = 0
    else:
        purchases_df = pd.DataFrame(columns=["Total"])

    total_revenue = sales_df["Total"].sum() if "Total" in sales_df.columns else 0
    total_expense = purchases_df["Total"].sum() if "Total" in purchases_df.columns else 0
    profit = total_revenue - total_expense

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f"<div class='metric-card'><div>Total Revenue</div><div class='metric-value'>₹{total_revenue:,.2f}</div></div>", unsafe_allow_html=True)
    with c2:
        st.markdown(f"<div class='metric-card'><div>Total Expense</div><div class='metric-value'>₹{total_expense:,.2f}</div></div>", unsafe_allow_html=True)
    with c3:
        color = "#00c67a" if profit >= 0 else "#e05b5b"
        st.markdown(f"<div class='metric-card'><div>Profit / Loss</div><div class='metric-value' style='color:{color};'>₹{profit:,.2f}</div></div>", unsafe_allow_html=True)

    # breathing space before chart
    st.markdown("<div style='height:36px'></div>", unsafe_allow_html=True)

    st.subheader("Most Sold Items")
    if not sales_df.empty and ("Item" in sales_df.columns) and ("Quantity" in sales_df.columns):
        grouped = sales_df.groupby("Item")["Quantity"].sum().sort_values(ascending=False)
        st.bar_chart(grouped)
    else:
        st.info("No sales data yet for the Most Sold Items chart (ensure Sales sheet has Item and Quantity columns).")

# ---------------- RECORD SALE (keeps it simple + validation) ----------------
elif page == "Record Sale":
    st.title("Record Sale")
    inv_df = get_df(inventory_ws)

    if inv_df.empty:
        st.warning("Inventory is empty. Please record purchases first.")
    else:
        # show dropdown of inventory items (Item column expected)
        if "Item" not in inv_df.columns:
            st.error("Inventory sheet does not have an 'Item' column. Please fix the sheet headers.")
            st.stop()

        item = st.selectbox("Select Item", inv_df["Item"].tolist())
        qty = st.number_input("Units Sold", min_value=1, step=1, value=1)
        sale_date = st.date_input("Date of Sale", value=date.today())

        # determine sell price if present; otherwise ask user
        default_sell = inv_df.loc[inv_df["Item"] == item, "Sell Price"].iloc[0] if "Sell Price" in inv_df.columns else 0.0
        sell_price = st.number_input("Selling Price (per unit ₹)", min_value=0.0, step=0.1, value=float(default_sell))

        total_sale = qty * sell_price
        st.write(f"**Total:** ₹{total_sale:,.2f}")

        if st.button("Record Sale"):
            # append row to Sales: keep columns consistent: Item, Quantity, Sell Price, Total, Date
            sales_ws.append_row([item, int(qty), float(sell_price), float(total_sale), str(sale_date)])
            # update inventory stock (if Stock column exists)
            if "Stock" in inv_df.columns:
                cur_stock = int(inv_df.loc[inv_df["Item"] == item, "Stock"].iloc[0])
                new_stock = max(0, cur_stock - int(qty))
                inventory_ws.update_cell(inv_df.index[inv_df["Item"] == item][0] + 2, inv_df.columns.get_loc("Stock") + 1, new_stock)
            st.success("Sale recorded and inventory updated (if Stock column exists).")

    # delete sale: separate on this page
    st.markdown("---")
    st.subheader("Delete Sale Record")
    sales_df = get_df(sales_ws)
    if not sales_df.empty:
        # create display column
        display_col = []
        for i, r in sales_df.iterrows():
            itm = r.get("Item", "")
            q = r.get("Quantity", r.get("Qty", ""))
            d = r.get("Date", "")
            display_col.append(f"{i} | {itm} | {q} | {d}")
        sel = st.selectbox("Select sale to delete", options=display_col)
        if st.button("Delete Selected Sale"):
            try:
                idx = int(sel.split("|")[0].strip())
                sales_ws.delete_rows(int(idx + 2))
                st.success("Sale deleted.")
            except Exception as e:
                st.error("Could not delete selected sale. Check logs.")

# ---------------- RECORD PURCHASE ----------------
elif page == "Record Purchase":
    st.title("Record Purchase")
    inv_df = get_df(inventory_ws)

    item = st.text_input("Item Name (existing or new)", value="")
    qty = st.number_input("Units Bought", min_value=1, step=1, value=1)
    buy_price = st.number_input("Buy Price (per unit ₹)", min_value=0.0, step=0.1, value=0.0)
    purchase_date = st.date_input("Date of Purchase", value=date.today())

    total_cost = qty * buy_price
    st.write(f"**Total cost:** ₹{total_cost:,.2f}")

    if st.button("Record Purchase"):
        if not item:
            st.error("Enter an item name.")
        else:
            purchases_ws.append_row([item, int(qty), float(buy_price), float(total_cost), str(purchase_date)])
            # update inventory: if item exists, increase stock; else append new row
            if not inv_df.empty and "Item" in inv_df.columns and item in inv_df["Item"].values:
                cur_stock = int(inv_df.loc[inv_df["Item"] == item, "Stock"].iloc[0]) if "Stock" in inv_df.columns else 0
                new_stock = cur_stock + int(qty)
                if "Stock" in inv_df.columns:
                    inventory_ws.update_cell(inv_df.index[inv_df["Item"] == item][0] + 2, inv_df.columns.get_loc("Stock") + 1, new_stock)
            else:
                # append [Item, Buy Price, Sell Price(=1.2*buy), Stock]
                inventory_ws.append_row([item, float(buy_price), float(round(buy_price * 1.2, 2)), int(qty)])
            st.success("Purchase recorded and inventory updated.")

    st.markdown("---")
    st.subheader("Delete Purchase Record")
    purchases_df = get_df(purchases_ws)
    if not purchases_df.empty:
        display_col = []
        for i, r in purchases_df.iterrows():
            itm = r.get("Item", "")
            q = r.get("Quantity", r.get("Qty", ""))
            d = r.get("Date", "")
            display_col.append(f"{i} | {itm} | {q} | {d}")
        sel = st.selectbox("Select purchase to delete", options=display_col, key="del_pur")
        if st.button("Delete Selected Purchase"):
            try:
                idx = int(sel.split("|")[0].strip())
                purchases_ws.delete_rows(int(idx + 2))
                st.success("Purchase deleted.")
            except Exception as e:
                st.error("Could not delete selected purchase. Check logs.")

# ---------------- VIEW INVENTORY ----------------
elif page == "View Inventory":
    st.title("Inventory")
    inv_df = get_df(inventory_ws)
    if inv_df.empty:
        st.info("No inventory yet.")
    else:
        st.dataframe(inv_df, use_container_width=True)
