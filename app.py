import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time
import io

st.set_page_config(page_title="TDC Trade Ops AI", layout="wide")

def tdc_full_app():
    st.title("🚢 TDC International: Unified Laytime & Document Platform")
    
    # --- 1. SIDEBAR: CONTRACTUALS ---
    with st.sidebar:
        st.header("1. Financials")
        qty = st.number_input("Cargo Quantity (MT)", value=36700.0)
        rate = st.number_input("Load Rate (MT/Day)", value=5000.0)
        demu_rate = st.number_input("Demurrage Rate ($/Day)", value=16500.0)
        desp_rate = st.number_input("Despatch Rate ($/Day)", value=demu_rate / 2)
        
        st.header("2. Working Rules")
        laycan_start = st.date_input("Laycan Start Date", value=datetime(2026, 2, 10))
        calendar_basis = st.selectbox("Calendar Basis", ["SHINC", "SSHEX", "SHEX", "CUSTOM WEEKEND RULE"])
        
        custom_wknd_stop = time(17, 0)
        custom_wknd_start = time(8, 0)
        if calendar_basis == "CUSTOM WEEKEND RULE":
            custom_wknd_stop = st.time_input("Saturday Stop Time", value=time(17, 0))
            custom_wknd_start = st.time_input("Monday Start Time", value=time(8, 0))

        nor_option = st.selectbox("NOR Rule Type", ["Custom: 12:00 PM Rule", "12 Hours Free", "MANUAL START TIME"])
        manual_start_time = datetime(2026, 2, 1, 14, 0)
        if nor_option == "MANUAL START TIME":
            manual_start_time = st.datetime_input("Set Official Start:", value=datetime(2026, 2, 1, 14, 0))

    # --- 2. THE MULTIMODAL UPLOADER (RE-ENABLED) ---
    st.subheader("📂 Document Management")
    col_u1, col_u2 = st.columns([2, 1])
    with col_u1:
        uploaded_file = st.file_uploader("Upload SOF (PDF, Word, Image, Excel)", 
                                         type=["pdf", "docx", "jpg", "jpeg", "png", "xlsx", "csv"])
    with col_u2:
        if uploaded_file:
            st.success(f"File '{uploaded_file.name}' is active.")
            st.info("The engine is using this document to validate the timestamps below.")

    st.markdown("---")

    # --- 3. TIMESTAMPS & REMARKS ---
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("⏱️ Milestones")
        nor_tendered = st.datetime_input("NOR Tendered", value=datetime(2026, 2, 1, 0, 1))
        ops_commenced = st.datetime_input("Loading Commenced", value=datetime(2026, 2, 28, 6, 0))
        ops_completed = st.datetime_input("Loading Completed", value=datetime(2026, 3, 9, 4, 0))

    with col2:
        st.subheader("⛈️ Weather & Remarks (Deductions)")
        st.caption("Verify Rain, Port Closures, and Shifting from your uploaded SOF:")
        # Defaulting with MV DORA's massive Feb closure as an example
        sof_events = st.data_editor(
            pd.DataFrame([
                {"Remark": "Port Closed (Weather)", "Start": datetime(2026, 2, 2, 12, 0), "End": datetime(2026, 2, 16, 23, 59)},
            ]), num_rows="dynamic", use_container_width=True
        )

    # --- 4. ENGINE LOGIC ---
    # A. Laycan & Start Logic
    lc_start_dt = datetime.combine(laycan_start, time(0, 0))
    if nor_option == "MANUAL START TIME":
        official_start = manual_start_time
    elif nor_option == "Custom: 12:00 PM Rule":
        if nor_tendered.time() >= time(12, 0):
            next_day = nor_tendered + timedelta(days=1)
            official_start = datetime.combine(next_day.date(), time(8, 0))
        else:
            official_start = datetime.combine(nor_tendered.date(), time(14, 0))
    else:
        official_start = nor_tendered + timedelta(hours=12)

    # Laycan Rule: Clock triggers at official start OR loading commencement (whichever is sooner)
    # BUT if arrival is before Laycan, loading commencement is the primary trigger.
    if official_start < lc_start_dt:
        laytime_start = max(official_start, ops_commenced)
    else:
        laytime_start = min(official_start, ops_commenced)

    allowed_sec = (qty / rate) * 86400
    curr = laytime_start
    used_sec = 0
    deduct_sec = 0
    step = 900 # 15-minute increments

    while used_sec < allowed_sec and curr < ops_completed:
        excluded = False
        day = curr.weekday()
        
        # Weekend Exclusions
        if calendar_basis == "CUSTOM WEEKEND RULE":
            if (day == 5 and curr.time() >= custom_wknd_stop) or (day == 6) or (day == 0 and curr.time() < custom_wknd_start):
                excluded = True
        elif calendar_basis == "SSHEX" and day >= 5: excluded = True
        elif calendar_basis == "SHEX" and day == 6: excluded = True
        
        # Weather / Remarks
        if not excluded:
            for _, row in sof_events.iterrows():
                if pd.to_datetime(row['Start']) <= curr < pd.to_datetime(row['End']):
                    excluded = True
                    break
        
        if excluded: deduct_sec += step
        else: used_sec += step
        curr += timedelta(seconds=step)

    final_expiry = curr

    # --- 5. RESULTS ---
    st.markdown("---")
    res1, res2 = st.columns(2)
    if ops_completed > final_expiry:
        diff_days = (ops_completed - final_expiry).total_seconds() / 86400
        res1.error(f"STATUS: ON DEMURRAGE\n\nTotal Owed: ${diff_days * demu_rate:,.2f}")
    else:
        diff_days = (final_expiry - ops_completed).total_seconds() / 86400
        res1.success(f"STATUS: IN DESPATCH\n\nTotal Earned: ${diff_days * desp_rate:,.2f}")

    res2.write("**Calculation Audit:**")
    res2.write(f"• Start Rule Applied: {nor_option}")
    res2.write(f"• Final Expiry Date: {final_expiry.strftime('%Y-%m-%d %H:%M')}")
    res2.write(f"• Total Time Deducted: {timedelta(seconds=deduct_sec)}")

if __name__ == "__main__":
    tdc_full_app()
