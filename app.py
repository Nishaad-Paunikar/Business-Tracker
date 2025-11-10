import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import date, datetime

# ---------------- Page config & styles ----------------
st.set_page_config(page_title="Inventory & Sales Manager", layout="wide")

st.markdown(
    """
    <style>
    [data-testid="stSidebar"] { background-color: #0e1117; padding: 16px; }
    .sidebar-button { display:block; width:100%; text-align:left; background:#1c1c1e; color:#fff; border-radius:10px;
                      padding:10px 14px; margin-bottom:8px; border:1px solid #333; font-weight:600; }
    .sidebar-button:hover { background:#2a2a2a; }
    .metric-card { background:#1e1e1e; padding:18px; border-radius:12px; color:#fff; text-align:center; }
    .metric-value { font-size:1.5rem; font-weight:700; margin-top:6px; }
    .small-note { color:#bdbdbd; font-size:0.9rem; }
    .block-container { padding-top: 18px; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------- Google Sheets auth (Streamlit secrets) ----------------
SCOPE = ["https://www.googleapis.com/auth/spreadsheets",
         "https://www.googleapis.com/auth/drive"]

try:
    creds_dict = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(dict(creds_dict), scopes=SCOPE)
    client = gspread.authorize(creds)
except Exception as e:
    st.error("Google credentials not found in Streamlit Secrets or invalid. "
             "Add gcp_service_account in Settings → Secrets.")
    st.stop()

# ---------------- Sheet open (set your sheet id) ----------------
SHEET_ID = "1xRzv1vE3cz-bN7En0qFpgkGbkxabSuM0eBKzMDhpXq0"  # <--- replace if needed
try:
    sheet = client.open_by_key(SHEET_ID)
except Exception as e:
    st.error("Unable to open Google Sheet. Check SHEET_ID and share the sheet with your service account email.")
    st.stop()

# Ensure required worksheets exist
try:
    inventory_ws = sheet.worksheet("Inventory")
    sales_ws = sheet.worksheet("Sales")
    purchases_ws = sheet.worksheet("Purchases")
except Exception as e:
    st.error("One or more worksheets named Inventory, Sales, Purchases were not found. Create them (case-sensitive).")
    st.stop()

# ---------------- Helper functions ----------------
def get_df(ws):
    """Return DataFrame (headers normalized Title Case)."""
    data = ws.get_all_records()
    df = pd.DataFrame(data)
    if not df.empty:
        df.columns = [c.strip().title() for c in df.columns]
    return df

def append_row_dynamic(ws, data_dict):
    """
    Append a row matching keys in data_dict to the header row of ws.
    Case-insensitive header matching and preserves header order.
    """
    headers = [h.strip() for h in ws.row_values(1)]
    # Build row in header order
    row = []
    for hdr in headers:
        # find matching key in data_dict (case-insensitive)
        matched = None
        for k in data_dict.keys():
            if k.strip().lower() == hdr.lower():
                matched = k
                break
        row.append(data_dict.get(matched, ""))
    # Trim or pad to header length
    row = row[:len(headers)]
    try:
        ws.append_row(row, value_input_option="USER_ENTERED")
    except Exception as e:
        st.error("Failed to append row to sheet. Check sheet permissions and quotas.")
        st.stop()

def find_and_delete_row(ws, match_dict):
    """
    Find first row in ws that matches all non-empty values in match_dict.
    match_dict keys should match header names (not case-sensitive).
    Returns True on success, False otherwise.
    """
    headers = [h.strip().title() for h in ws.row_values(1)]
    df = get_df(ws)
    if df.empty:
        return False, "Sheet is empty."

    # normalize match keys to header-case
    match = {}
    for k, v in match_dict.items():
        for h in headers:
            if k.strip().lower() == h.lower():
                match[h] = v
                break

    # iterate df rows to find first full match
    for idx, row in df.iterrows():
        ok = True
        for k, v in match.items():
            # compare as strings
            cell = row.get(k, "")
            if str(cell).strip() != str(v).strip():
                ok = False
                break
        if ok:
            # delete row at spreadsheet index (idx starts at 0 and header is at row 1)
            sheet_row = int(idx) + 2
            try:
                ws.delete_rows(sheet_row)
                return True, None
            except Exception as e:
                return False, f"API error when deleting row: {e}"
    return False, "No matching row found."

# ---------------- Session state init ----------------
if "menu" not in st.session_state:
    st.session_state["menu"] = "Dashboard"
menu = st.session_state["menu"]

# ---------------- Sidebar (rectangular buttons) ----------------
st.sidebar.title("Menu")
def nav_btn(label):
    if st.sidebar.button(label, key=f"btn_{label}", use_container_width=True):
        st.session_state["menu"] = label
        st.experimental_rerun()

for label in ["Dashboard", "Record Sale", "Record Purchase", "View Inventory"]:
    st.sidebar.markdown(f"<button class='sidebar-button'>{label}</button>", unsafe_allow_html=True)
    # Using a hidden Streamlit button to capture clicks reliably:
    if st.sidebar.button("", key=f"hidden_{label}", help=label):
        st.session_state["menu"] = label
        st.experimental_rerun()

menu = st.session_state["menu"]

# ---------------- Dashboard ----------------
if menu == "Dashboard":
    st.title("Inventory & Sales Dashboard")

    inv_df = get_df(inventory_ws)
    sales_df = get_df(sales_ws)
    purchases_df = get_df(purchases_ws)

    # Defensive column names (normalize)
    if not sales_df.empty:
        if "Units Sold" not in sales_df.columns and "Quantity" in sales_df.columns:
            sales_df["Units Sold"] = sales_df["Quantity"]
        if "Selling Price" not in sales_df.columns and "Sell Price" in sales_df.columns:
            sales_df["Selling Price"] = sales_df["Sell Price"]
    if not purchases_df.empty:
        if "Units Bought" not in purchases_df.columns and "Quantity" in purchases_df.columns:
            purchases_df["Units Bought"] = purchases_df["Quantity"]
        if "Buying Price" not in purchases_df.columns and "Buy Price" in purchases_df.columns:
            purchases_df["Buying Price"] = purchases_df["Buy Price"]

    # ensure numeric columns
    if not sales_df.empty:
        sales_df["Units Sold"] = pd.to_numeric(sales_df.get("Units Sold", 0), errors="coerce").fillna(0)
        sales_df["Selling Price"] = pd.to_numeric(sales_df.get("Selling Price", 0), errors="coerce").fillna(0)
    else:
        sales_df = pd.DataFrame(columns=["Units Sold", "Selling Price"])

    if not purchases_df.empty:
        purchases_df["Units Bought"] = pd.to_numeric(purchases_df.get("Units Bought", 0), errors="coerce").fillna(0)
        purchases_df["Buying Price"] = pd.to_numeric(purchases_df.get("Buying Price", 0), errors="coerce").fillna(0)
    else:
        purchases_df = pd.DataFrame(columns=["Units Bought", "Buying Price"])

    sales_df["Total"] = sales_df["Units Sold"] * sales_df["Selling Price"]
    purchases_df["Total"] = purchases_df["Units Bought"] * purchases_df["Buying Price"]

    total_revenue = sales_df["Total"].sum()
    total_expense = purchases_df["Total"].sum()
    profit = total_revenue - total_expense

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f"<div class='metric-card'><div>Total Revenue</div><div class='metric-value'>₹{total_revenue:,.2f}</div></div>", unsafe_allow_html=True)
    with c2:
        st.markdown(f"<div class='metric-card'><div>Total Expense</div><div class='metric-value'>₹{total_expense:,.2f}</div></div>", unsafe_allow_html=True)
    with c3:
        color = "#00c67a" if profit >= 0 else "#e05b5b"
        st.markdown(f"<div class='metric-card'><div>Profit / Loss</div><div class='metric-value' style='color:{color};'>₹{profit:,.2f}</div></div>", unsafe_allow_html=True)

    st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
    st.subheader("Most Sold Items")
    if not sales_df.empty and "Item Name" in sales_df.columns:
        grouped = sales_df.groupby("Item Name")["Units Sold"].sum().sort_values(ascending=False).head(10)
        st.bar_chart(grouped)
    else:
        st.info("No sales data to show most-sold items. Ensure Sales sheet has Item Name and Units Sold columns.")

# ---------------- Record Sale ----------------
elif menu == "Record Sale":
    st.title("Record Sale")

    inv_df = get_df(inventory_ws)
    # If inventory exists but column is 'Item' or other variants, try to find the correct column name
    if not inv_df.empty:
        # prefer "Item Name" else fallback to first column
        item_col = "Item Name" if "Item Name" in inv_df.columns else inv_df.columns[0]
        items = inv_df[item_col].tolist()
    else:
        items = []

    if not items:
        st.warning("No items in inventory yet. Record a purchase first or enter a new item when recording a purchase.")
    else:
        item = st.selectbox("Select Item", items)
        qty = st.number_input("Units Sold", min_value=1, step=1, value=1)
        sale_date = st.date_input("Date of Sale", value=date.today())
        # default selling price from inventory if available
        default_price = 0.0
        if not inv_df.empty:
            if "Selling Price" in inv_df.columns:
                default_price = inv_df.loc[inv_df[item_col] == item, "Selling Price"].iloc[0]
            elif "Sell Price" in inv_df.columns:
                default_price = inv_df.loc[inv_df[item_col] == item, "Sell Price"].iloc[0]
        selling_price = st.number_input("Selling Price (per unit ₹)", min_value=0.0, step=0.1, value=float(default_price))

        total = qty * selling_price
        st.markdown(f"**Total:** ₹{total:,.2f}")

        if st.button("Record Sale"):
            # append row with dynamic header alignment
            append_row_dynamic(sales_ws, {
                "Date": str(sale_date),
                "Item Name": item,
                "Units Sold": int(qty),
                "Selling Price": float(selling_price)
            })
            # update inventory stock (if Stock column exists)
            if not inv_df.empty and "Stock" in inv_df.columns:
                try:
                    row_index = int(inv_df.index[inv_df[item_col] == item][0])  # 0-based
                    cur_stock = int(inv_df.loc[inv_df[item_col] == item, "Stock"].iloc[0])
                    new_stock = max(0, cur_stock - int(qty))
                    inventory_ws.update_cell(row_index + 2, inv_df.columns.get_loc("Stock") + 1, new_stock)
                except Exception:
                    # non-fatal
                    pass
            st.success("✅ Sale recorded and inventory updated (if Stock column exists).")

    st.markdown("---")
    st.subheader("Delete Sale Record")
    sales_df = get_df(sales_ws)
    if sales_df.empty:
        st.info("No sales to delete.")
    else:
        # create display list: index | item | qty | date
        display = []
        for i, r in sales_df.iterrows():
            d = r.get("Date", "")
            it = r.get("Item Name", r.get("Item", ""))
            q = r.get("Units Sold", "")
            display.append(f"{i} | {it} | {q} | {d}")
        chosen = st.selectbox("Select sale to delete", display)
        if st.button("Delete Selected Sale"):
            try:
                idx = int(chosen.split("|")[0].strip())
                # prepare match dict to find the correct row robustly
                row = sales_df.iloc[idx]
                match = {"Date": row.get("Date", ""), "Item Name": row.get("Item Name", ""), "Units Sold": row.get("Units Sold", "")}
                ok, err = find_and_delete_row(sales_ws, match)
                if ok:
                    st.success("Sale deleted.")
                else:
                    st.error(f"Could not delete sale: {err}")
            except Exception as e:
                st.error("Failed to delete sale. Try again or check app logs.")

# ---------------- Record Purchase ----------------
elif menu == "Record Purchase":
    st.title("Record Purchase")

    inv_df = get_df(inventory_ws)
    existing_items = inv_df["Item Name"].tolist() if (not inv_df.empty and "Item Name" in inv_df.columns) else []

    item = st.text_input("Item Name (existing or new)", value="")
    qty = st.number_input("Units Bought", min_value=1, step=1, value=1)
    buy_price = st.number_input("Buying Price (per unit ₹)", min_value=0.0, step=0.1, value=0.0)
    purchase_date = st.date_input("Date of Purchase", value=date.today())

    total = qty * buy_price
    st.markdown(f"**Total:** ₹{total:,.2f}")

    if st.button("Record Purchase"):
        if not item:
            st.error("Enter an item name.")
        else:
            append_row_dynamic(purchases_ws, {
                "Date": str(purchase_date),
                "Item Name": item,
                "Units Bought": int(qty),
                "Buying Price": float(buy_price)
            })

            # update inventory: if exists, increase stock; else add new row following inventory columns
            if (not inv_df.empty) and ("Item Name" in inv_df.columns) and (item in inv_df["Item Name"].values):
                try:
                    row_index = int(inv_df.index[inv_df["Item Name"] == item][0])
                    cur_stock = int(inv_df.loc[inv_df["Item Name"] == item, "Stock"].iloc[0]) if "Stock" in inv_df.columns else 0
                    new_stock = cur_stock + int(qty)
                    if "Stock" in inv_df.columns:
                        inventory_ws.update_cell(row_index + 2, inv_df.columns.get_loc("Stock") + 1, new_stock)
                except Exception:
                    pass
            else:
                # append new inventory row with columns assumed: Item Name, Buy Price, Sell Price, Stock
                try:
                    inventory_ws.append_row([item, float(buy_price), float(round(buy_price * 1.2, 2)), int(qty)], value_input_option="USER_ENTERED")
                except Exception:
                    # fallback: append minimal
                    inventory_ws.append_row([item, float(buy_price), int(qty)], value_input_option="USER_ENTERED")
            st.success("✅ Purchase recorded and inventory updated.")

    st.markdown("---")
    st.subheader("Delete Purchase Record")
    purchases_df = get_df(purchases_ws)
    if purchases_df.empty:
        st.info("No purchases to delete.")
    else:
        display = []
        for i, r in purchases_df.iterrows():
            d = r.get("Date", "")
            it = r.get("Item Name", "")
            q = r.get("Units Bought", "")
            display.append(f"{i} | {it} | {q} | {d}")
        chosen = st.selectbox("Select purchase to delete", display, key="del_purchase")
        if st.button("Delete Selected Purchase"):
            try:
                idx = int(chosen.split("|")[0].strip())
                row = purchases_df.iloc[idx]
                match = {"Date": row.get("Date", ""), "Item Name": row.get("Item Name", ""), "Units Bought": row.get("Units Bought", "")}
                ok, err = find_and_delete_row(purchases_ws, match)
                if ok:
                    st.success("Purchase deleted.")
                else:
                    st.error(f"Could not delete purchase: {err}")
            except Exception as e:
                st.error("Failed to delete purchase. Try again or check app logs.")

# ---------------- View Inventory ----------------
elif menu == "View Inventory":
    st.title("Inventory Overview")
    inv_df = get_df(inventory_ws)
    if inv_df.empty:
        st.info("Inventory is empty.")
    else:
        st.dataframe(inv_df, use_container_width=True)
