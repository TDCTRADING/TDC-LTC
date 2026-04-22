import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time

st.set_page_config(page_title="TDC Trade Ops AI", layout="wide")

# --- PERSISTENT FILE HANDLING ---
if 'uploaded_file_name' not in st.session_state:
    st.session_state.uploaded_file_name = None

def tdc_final_engine():
    st.title("🚢 TDC International: Master Laytime Platform")
    
    # --- 1. SIDEBAR: IDENTITY & FINANCIALS ---
    with st.sidebar:
        st.header("🚢 Voyage Identity")
        vessel_name = st.text_input("Vessel Name", value="MV DORA")
        bl_date = st.date_input("B/L Date", value=datetime(2026, 3, 1))
        
        st.header("💰 Financials")
        qty = st.number_input("B/L Quantity (MT)", value=7827.0)
        rate = st.number_input("Load/Disch Rate (MT/Day)", value=3200.0)
        demu_rate = st.number_input("Demurrage Rate ($/Day)", value=6000.0)
        desp_rate = demu_rate / 2
        st.info(f"**Despatch Rate:** ${desp_rate:,.2f} / day")
        
        st.header("⚖️ Rules")
        calendar_basis = st.selectbox("Calendar Basis", [
            "SHINC", "SSHEX (Unless Used)", "SHEX (Unless Used)",
            "SSHEX (Even if Used)", "SHEX (Even if Used)"
        ])
        nor_rule_type = st.selectbox("NOR Rule Type", ["12 Hour Turn Time", "24h Turn Time", "LAFAMA Rule", "6:00 PM / 8:00 AM Rule"])

    # --- 2. THE UPLOADER (STABILIZED) ---
    st.subheader("📂 Document Management")
    # Using a unique key to keep it in session state
    uploaded_file = st.file_uploader("Upload SOF", type=["pdf", "docx", "jpg", "jpeg", "png", "xlsx"], key="sof_loader")
    
    if uploaded_file:
        st.session_state.uploaded_file_name = uploaded_file.name
        st.success(f"✅ Document '{st.session_state.uploaded_file_name}' is currently active.")

    st.markdown("---")

    # --- 3. MILESTONES & DEDUCTIONS ---
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("⏱️ Key Timestamps")
        nor_t = st.datetime_input("NOR Tendered", value=datetime(2026, 3, 8, 7, 0))
        ops_s = st.datetime_input("Loading Commenced", value=datetime(2026, 3, 10, 21, 30))
        ops_e = st.datetime_input("Loading Completed", value=datetime(2026, 3, 13, 3, 40))

    with col2:
        st.subheader("⛈️ Deductions (Keyword Active)")
        sof_events = st.data_editor(
            pd.DataFrame([
                {"Remark": "Draft Survey", "Start": datetime(2026, 3, 10, 18, 0), "End": datetime(2026, 3, 10, 20, 0)},
                {"Remark": "Cleaning of Holds", "Start": datetime(2026, 3, 11, 8, 0), "End": datetime(2026, 3, 11, 12, 0)},
            ]), num_rows="dynamic", use_container_width=True
        )

    # --- 4. ENGINE ---
    if rate > 0:
        # Turn Time
        if nor_rule_type == "12 Hour Turn Time": tt_exp = nor_t + timedelta(hours=12)
        elif nor_rule_type == "24h Turn Time": tt_exp = nor_t + timedelta(hours=24)
        else: tt_exp = nor_t 

        total_allowed_sec = (qty / rate) * 86400
        curr = max(tt_exp, ops_s)
        used_sec = 0
        
        while used_sec < total_allowed_sec:
            excluded = False
            day = curr.weekday()
            
            # Weekend Logic
            if "SSHEX" in calendar_basis and day >= 5:
                if "Unless Used" not in calendar_basis or not (ops_s <= curr <= ops_e): excluded = True
            elif "SHEX" in calendar_basis and day == 6:
                if "Unless Used" not in calendar_basis or not (ops_s <= curr <= ops_e): excluded = True
            
            # Keyword Logic
            if not excluded:
                for _, row in sof_events.iterrows():
                    if pd.to_datetime(row['Start']) <= curr < pd.to_datetime(row['End']):
                        if any(k in str(row['Remark']).upper() for k in ["CLEANING", "SURVEY", "BERTH", "WEATHER", "RAIN", "WIND"]):
                            excluded = True
                            break
            
            if not excluded: used_sec += 60
            curr += timedelta(seconds=60)

        # --- 5. RESULTS & EXPORT ---
        st.markdown("---")
        diff_sec = (curr - ops_e).total_seconds()
        days_diff = abs(diff_sec) / 86400
        
        res_col, share_col = st.columns([2, 1])
        
        if diff_sec < 0:
            total_money = days_diff * demu_rate
            res_col.error(f"🚨 {vessel_name} | STATUS: ON DEMURRAGE\n\n**Total Due: ${total_money:,.2f}**")
        else:
            total_money = days_diff * desp_rate
            res_col.success(f"💰 {vessel_name} | STATUS: IN DESPATCH\n\n**Total Credit: ${total_money:,.2f}**")

        share_col.write(f"**B/L Date:** {bl_date}")
        share_col.write(f"**Time Saved/Lost:** {days_diff:.4f} days")
        
        # Share functionality
        st.download_button(
            label="Download Statement for Client (CSV)",
            data=sof_events.to_csv(),
            file_name=f"{vessel_name}_Laytime_Statement.csv",
            mime="text/csv"
        )

if __name__ == "__main__":
    tdc_final_engine()
