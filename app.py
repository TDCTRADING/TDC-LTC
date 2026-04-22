import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time
import re

st.set_page_config(page_title="TDC AI Trade Desk", layout="wide")

def tdc_ai_engine():
    st.title("🚢 TDC International: AI Statement of Facts Processor")
    st.markdown("---")

    # --- 1. SIDEBAR: CONTRACTUALS ---
    with st.sidebar:
        st.header("Contract Terms")
        qty = st.number_input("B/L Quantity (MT)", value=36700.0) # Updated for MV DORA
        rate = st.number_input("Load Rate (MT/Day)", value=5000.0)
        demu_rate = st.number_input("Demurrage Rate ($/Day)", value=16500.0)
        desp_rate = st.number_input("Despatch Rate ($/Day)", value=demu_rate / 2)
        
        calendar_basis = st.selectbox("Calendar Basis", ["SHINC", "SSHEX", "SHEX"])
        nor_rule = st.selectbox("NOR Rule", ["Custom: 12:00 PM Rule", "12 Hours Free", "24 Hours Free"])

    # --- 2. MULTIMODAL UPLOADER ---
    st.subheader("📂 Upload SOF (PDF/Image/Word)")
    uploaded_file = st.file_uploader("Drop MV DORA SOF here", type=["pdf", "docx", "jpg", "png"])
    
    # --- 3. TIMESTAMPS & INTERRUPTIONS ---
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("⏱️ Key Milestones")
        nor_tendered = st.datetime_input("NOR Tendered", value=datetime(2026, 2, 1, 0, 1))
        ops_commenced = st.datetime_input("Loading Commenced", value=datetime(2026, 2, 28, 6, 0))
        ops_completed = st.datetime_input("Loading Completed", value=datetime(2026, 3, 9, 4, 0))

    with col2:
        st.subheader("⛈️ Detected Deductions")
        st.caption("The AI scans remarks for Rain, Port Closed, Wind, and Shifting.")
        
        # MV DORA Specific Auto-Population Logic
        initial_data = [
            {"Remark": "Port Closed (Bad Weather)", "Start": datetime(2026, 2, 2, 12, 0), "End": datetime(2026, 2, 16, 23, 59)},
            {"Remark": "Rain / Shifting / Swell", "Start": datetime(2026, 3, 5, 1, 0), "End": datetime(2026, 3, 7, 15, 0)},
        ]
        
        sof_events = st.data_editor(
            pd.DataFrame(initial_data), num_rows="dynamic", use_container_width=True
        )

    # --- 4. FLOATING WALL ENGINE ---
    # NOR logic
    if nor_rule == "Custom: 12:00 PM Rule":
        if nor_tendered.time() >= time(12, 0):
            official_start = datetime.combine((nor_tendered + timedelta(days=1)).date(), time(8, 0))
        else:
            official_start = datetime.combine(nor_tendered.date(), time(14, 0))
    else:
        hours = 12 if "12" in nor_rule else 24
        official_start = nor_tendered + timedelta(hours=hours)

    laytime_start = min(official_start, ops_commenced)
    allowed_seconds = (qty / rate) * 86400
    
    # Process Chronologically in 10-minute steps
    events = sof_events.copy()
    events['Start'] = pd.to_datetime(events['Start'])
    events['End'] = pd.to_datetime(events['End'])
    
    curr = laytime_start
    used_sec = 0
    deduct_sec = 0
    step = 600 # 10 mins

    while used_sec < allowed_seconds and curr < ops_completed:
        excluded = False
        # Weekend Check
        if calendar_basis == "SSHEX" and curr.weekday() >= 5: excluded = True
        
        # Weather/Remark Check
        for _, row in events.iterrows():
            if row['Start'] <= curr < row['End']:
                rem = str(row['Remark']).upper()
                if any(k in rem for k in ["RAIN", "WIND", "CLOSED", "WEATHER", "SWELL", "SHIFT", "STOP"]):
                    excluded = True
                    break
        
        if excluded: deduct_sec += step
        else: used_sec += step
        curr += timedelta(seconds=step)

    final_expiry = curr

    # --- 5. FINAL FINANCIALS ---
    st.markdown("---")
    res1, res2 = st.columns(2)
    if ops_completed > final_expiry:
        diff_days = (ops_completed - final_expiry).total_seconds() / 86400
        res1.error(f"STATUS: ON DEMURRAGE\n\nTotal Due: ${diff_days * demu_rate:,.2f}")
    else:
        diff_days = (final_expiry - ops_completed).total_seconds() / 86400
        res1.success(f"STATUS: IN DESPATCH\n\nTotal Earned: ${diff_days * desp_rate:,.2f}")

    res2.write(f"**Laytime Start:** {laytime_start}")
    res2.write(f"**Expiry (The Wall):** {final_expiry}")
    res2.write(f"**Total Days Saved/Owed:** {diff_days:.4f} Days")

if __name__ == "__main__":
    tdc_ai_engine()
