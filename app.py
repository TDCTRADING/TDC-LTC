import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time

st.set_page_config(page_title="TDC Trade Ops AI", layout="wide")

# --- APP INITIALIZATION ---
if 'file_status' not in st.session_state:
    st.session_state.file_status = "No file attached"

def tdc_full_format_engine():
    st.title("🚢 TDC International: Master Laytime Platform")
    
    # --- 1. SIDEBAR: IDENTITY & CONTRACT ---
    with st.sidebar:
        st.header("🚢 Voyage Identity")
        vessel_name = st.text_input("Vessel Name", value="MV DORA")
        bl_date = st.date_input("B/L Date", value=datetime(2026, 4, 22))
        
        st.header("💰 Financials")
        qty = st.number_input("B/L Quantity (MT)", value=7827.0)
        rate = st.number_input("Load/Disch Rate (MT/Day)", value=3200.0)
        demu_rate = st.number_input("Demurrage Rate ($/Day)", value=6000.0)
        desp_rate = demu_rate / 2
        st.info(f"**Despatch Rate:** ${desp_rate:,.2f}")
        
        st.header("⚖️ Rules")
        calendar_basis = st.selectbox("Calendar Basis", [
            "SHINC", "SSHEX (Unless Used)", "SHEX (Unless Used)",
            "SSHEX (Even if Used)", "SHEX (Even if Used)"
        ])
        nor_rule = st.selectbox("NOR Rule", ["12 Hour Turn Time", "24h Turn Time", "LAFAMA Rule", "6/8 Rule"])

    # --- 2. MULTI-FORMAT UPLOADER ---
    st.subheader("📂 Document Management (Word, PDF, Images)")
    # Expanded type list to ensure Word (.docx) is accepted
    uploaded_file = st.file_uploader(
        "Drop SOF here", 
        type=["pdf", "docx", "doc", "jpg", "jpeg", "png", "xlsx"],
        help="Supports Word, PDF, Excel, and Photo formats."
    )
    
    if uploaded_file is not None:
        st.session_state.file_status = f"✅ {uploaded_file.name} is ACTIVE"
        st.success(st.session_state.file_status)

    st.markdown("---")

    # --- 3. MILESTONES & DEDUCTIONS ---
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("⏱️ Key Timestamps")
        nor_t = st.datetime_input("NOR Tendered", value=datetime(2026, 3, 8, 7, 0))
        ops_s = st.datetime_input("Loading Commenced", value=datetime(2026, 3, 10, 21, 30))
        ops_e = st.datetime_input("Loading Completed", value=datetime(2026, 3, 13, 3, 40))

    with col2:
        st.subheader("⛈️ Deductions")
        sof_events = st.data_editor(
            pd.DataFrame([
                {"Remark": "Draft Survey", "Start": datetime(2026, 3, 10, 18, 0), "End": datetime(2026, 3, 10, 20, 0)},
                {"Remark": "Cleaning holds", "Start": datetime(2026, 3, 11, 8, 0), "End": datetime(2026, 3, 11, 12, 0)},
            ]), num_rows="dynamic", use_container_width=True
        )

    # --- 4. CALCULATION CORE ---
    if rate > 0:
        # Turn Time
        tt_exp = nor_t + timedelta(hours=12) if "12 Hour" in nor_rule else nor_t + timedelta(hours=24)
        
        # Calculation
        total_allowed = (qty / rate) * 86400
        curr = max(tt_exp, ops_s)
        used_sec = 0
        
        while used_sec < total_allowed:
            excluded = False
            day = curr.weekday()
            
            # Weekend Check
            if "SSHEX" in calendar_basis and day >= 5:
                if "Unless Used" not in calendar_basis or not (ops_s <= curr <= ops_e): excluded = True
            elif "SHEX" in calendar_basis and day == 6:
                if "Unless Used" not in calendar_basis or not (ops_s <= curr <= ops_e): excluded = True
            
            # Auto-Keyword Deductions
            if not excluded:
                for _, row in sof_events.iterrows():
                    if pd.to_datetime(row['Start']) <= curr < pd.to_datetime(row['End']):
                        rem = str(row['Remark']).upper()
                        if any(k in rem for k in ["CLEANING", "SURVEY", "BERTH", "WEATHER", "RAIN", "WIND", "SHIFT"]):
                            excluded = True
                            break
            
            if not excluded: used_sec += 60
            curr += timedelta(seconds=60)

        # --- 5. RESULTS ---
        st.markdown("---")
        diff_sec = (curr - ops_e).total_seconds()
        days_diff = abs(diff_sec) / 86400
        
        r_col, s_col = st.columns([2, 1])
        
        if diff_sec < 0:
            val = days_diff * demu_rate
            r_col.error(f"🚨 {vessel_name} | ON DEMURRAGE: ${val:,.2f}")
        else:
            val = days_diff * desp_rate
            r_col.success(f"💰 {vessel_name} | IN DESPATCH: ${val:,.2f}")

        s_col.write(f"**B/L Date:** {bl_date}")
        s_col.write(f"**Saved/Lost:** {days_diff:.4f} days")
        
        # Export
        st.download_button("Download CSV for Client", data=sof_events.to_csv(), file_name=f"{vessel_name}_calc.csv")

if __name__ == "__main__":
    tdc_full_format_engine()
