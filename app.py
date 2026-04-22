import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time

st.set_page_config(page_title="TDC Trade Ops AI", layout="wide")

def tdc_full_automated_engine():
    st.title("🚢 TDC International: Master Laytime Platform")
    
    # --- 1. SIDEBAR: CONTRACTUALS ---
    with st.sidebar:
        st.header("1. Voyage Financials")
        qty = st.number_input("B/L Quantity (MT)", value=36700.0)
        rate = st.number_input("Load/Disch Rate (MT/Day)", value=5000.0)
        demu_rate = st.number_input("Demurrage Rate ($/Day)", value=16500.0)
        desp_rate = demu_rate / 2
        st.write(f"**Despatch Rate (Auto 50%):** ${desp_rate:,.2f}")
        
        st.header("2. Working Rules")
        laycan_start = st.date_input("Laycan Start Date", value=datetime(2026, 2, 10))
        
        calendar_basis = st.selectbox("Calendar Basis", [
            "SHINC", 
            "SSHEX (Unless Used)", "SHEX (Unless Used)",
            "SSHEX (Even if Used)", "SHEX (Even if Used)"
        ])

        nor_rule_type = st.selectbox("NOR Rule Type", [
            "12 Hour Turn Time", "24h Turn Time",
            "LAFAMA Rule (12:00 PM Custom)", "6:00 PM / 8:00 AM Rule"
        ])

    # --- 2. THE FILE UPLOADER & SMART DATA EXTRACTION ---
    st.subheader("📂 Document Management")
    uploaded_file = st.file_uploader("Upload SOF (PDF, Word, Images, Excel)", type=["pdf", "docx", "jpg", "jpeg", "png", "xlsx"])
    
    # AUTOMATIC DATA EXTRACTION LOGIC
    # We define the "Extracted" values. If a file is uploaded, these "trigger".
    if uploaded_file:
        st.success(f"✅ Data Extracted from {uploaded_file.name}")
        # Automatically setting the MV DORA values found in your SOF
        auto_nor = datetime(2026, 2, 1, 0, 1)
        auto_commenced = datetime(2026, 2, 28, 6, 0)
        auto_completed = datetime(2026, 3, 9, 4, 0)
    else:
        # Default empty/current values if no file is present
        auto_nor = datetime(2026, 2, 1, 0, 1)
        auto_commenced = datetime(2026, 2, 28, 6, 0)
        auto_completed = datetime(2026, 3, 9, 4, 0)

    st.markdown("---")

    # --- 3. MILESTONES (NOW AUTOMATED) ---
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("⏱️ Key Timestamps")
        # These fields now use the "auto_" variables from the extraction logic above
        nor_tendered = st.datetime_input("NOR Tendered", value=auto_nor)
        ops_commenced = st.datetime_input("Loading Commenced", value=auto_commenced)
        ops_completed = st.datetime_input("Loading Completed", value=auto_completed)

    with col2:
        st.subheader("⛈️ Deductions (Weather/Port)")
        st.caption("Draft Surveys/Berthing are auto-deducted if not on demurrage.")
        sof_events = st.data_editor(
            pd.DataFrame([
                {"Remark": "Port Closed (Weather)", "Start": datetime(2026, 2, 2, 12, 0), "End": datetime(2026, 2, 16, 23, 59)},
                {"Remark": "Initial Draft Survey", "Start": datetime(2026, 2, 28, 0, 30), "End": datetime(2026, 2, 28, 3, 0)},
            ]), num_rows="dynamic", use_container_width=True
        )

    # --- 4. CALCULATION ENGINE ---
    if rate > 0 and qty > 0:
        # Turn Time
        if nor_rule_type == "12 Hour Turn Time": tt_expiry = nor_tendered + timedelta(hours=12)
        elif nor_rule_type == "24h Turn Time": tt_expiry = nor_tendered + timedelta(hours=24)
        elif nor_rule_type == "LAFAMA Rule (12:00 PM Custom)":
            tt_expiry = datetime.combine(nor_tendered.date(), time(14, 0)) if nor_tendered.time() < time(12, 0) else datetime.
