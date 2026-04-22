import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time

st.set_page_config(page_title="TDC Trade Ops AI", layout="wide")

# --- SESSION STATE INITIALIZATION ---
if 'nor_val' not in st.session_state:
    st.session_state.nor_val = datetime(2026, 2, 1, 0, 1)
if 'commenced_val' not in st.session_state:
    st.session_state.commenced_val = datetime(2026, 2, 28, 6, 0)
if 'completed_val' not in st.session_state:
    st.session_state.completed_val = datetime(2026, 3, 9, 4, 0)

def tdc_master_engine():
    st.title("🚢 TDC International: Master Laytime Platform")
    
    # --- 1. SIDEBAR: CONTRACTUALS ---
    with st.sidebar:
        st.header("1. Voyage Financials")
        qty = st.number_input("B/L Quantity (MT)", value=36700.0)
        rate = st.number_input("Load/Disch Rate (MT/Day)", value=5000.0)
        demu_rate = st.number_input("Demurrage Rate ($/Day)", value=16500.0)
        desp_rate = demu_rate / 2
        st.info(f"**Despatch Rate:** ${desp_rate:,.2f} / day")
        
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

    # --- 2. DOCUMENT UPLOADER ---
    st.subheader("📂 Document Management")
    uploaded_file = st.file_uploader("Upload SOF", type=["pdf", "docx", "jpg", "jpeg", "png", "xlsx"])
    if uploaded_file:
        st.success(f"✅ Document '{uploaded_file.name}' Active")

    st.markdown("---")

    # --- 3. MILESTONES ---
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("⏱️ Key Timestamps")
        nor_tendered = st.datetime_input("NOR Tendered", value=st.session_state.nor_val)
        ops_commenced = st.datetime_input("Loading Commenced", value=st.session_state.commenced_val)
        ops_completed = st.datetime_input("Loading Completed", value=st.session_state.completed_val)

    with col2:
        st.subheader("⛈️ Deductions (Weather/Port)")
        sof_events = st.data_editor(
            pd.DataFrame([
                {"Remark": "Port Closed (Weather)", "Start": datetime(2026, 2, 2, 12, 0), "End": datetime(2026, 2, 16, 23, 59)},
            ]), num_rows="dynamic", use_container_width=True
        )

    # --- 4. CALCULATION CORE ---
    if rate > 0 and qty > 0:
        # Turn Time
        if nor_rule_type == "12 Hour Turn Time": 
            tt_expiry = nor_tendered + timedelta(hours=12)
        elif nor_rule_type == "24h Turn Time": 
            tt_expiry = nor_tendered + timedelta(hours=24)
        elif nor_rule_type == "LAFAMA Rule (12:00 PM Custom)":
            if nor_tendered.time() < time(12, 0):
                tt_expiry = datetime.combine(nor_tendered.date(), time(14, 0))
            else:
                tt_expiry = datetime.combine((nor_tendered + timedelta(days=1)).date(), time(8, 0))
        else: # 6/8 Rule
            if nor_tendered.time() < time(12, 0):
                tt_expiry = datetime.combine(nor_tendered.date(), time(18, 0))
            else:
                tt_expiry = datetime.combine((nor_tendered + timedelta(days=1)).date(), time(8, 0))

        # Start Logic
        lc_start_dt = datetime.combine(laycan_start, time(0, 0))
        trigger = min(tt_expiry, ops_commenced)
        laytime_start = max(trigger, ops_commenced) if trigger < lc_start_dt else trigger

        # Engine
        allowed_sec = (qty / rate) * 86400
        curr = laytime_start
        used_sec = 0
        total_deduct = 0
        step = 600

        while used_sec < allowed_sec and curr < ops_completed:
            excluded = False
            day = curr.weekday()
            
            if "SSHEX" in calendar_basis and day >= 5:
                if "Unless Used" not in calendar_basis or not (ops_commenced <= curr <= ops_completed): excluded = True
            elif "SHEX" in calendar_basis and day == 6:
                if "Unless Used" not in calendar_basis or not (ops_commenced <= curr <= ops_completed): excluded = True
            
            if not excluded:
                for _, row in sof_events.iterrows():
                    if pd.to_datetime(row['Start']) <= curr < pd.to_datetime(row['End']):
                        excluded = True
                        break
            
            if excluded: total_deduct += step
            else: used_sec += step
            curr += timedelta(seconds=step)

        # --- 5. THE FIX: EXPLICIT RESULTS ---
        st.markdown("---")
        st.subheader("📊 Final Calculation Result")
        
        res_box, audit_box = st.columns([2, 1])

        # Logic for Despatch vs Demurrage
        if ops_completed > curr:
            # BEHIND SCHEDULE (Demurrage)
            time_lost_sec = (ops_completed - curr).total_seconds()
            days_lost = time_lost_sec / 86400
            total_money = days_lost * demu_rate
            
            res_box.error(f"🚨 STATUS: ON DEMURRAGE\n\n**Total Due: ${total_money:,.2f}**")
            audit_box.write(f"📉 **Time Lost:** {days_lost:.4f} days")
            audit_box.write(f"({timedelta(seconds=int(time_lost_sec))} HH:MM:SS)")
        
        else:
            # AHEAD OF SCHEDULE (Despatch)
            time_saved_sec = (curr - ops_completed).total_seconds()
            days_saved = time_saved_sec / 86400
            total_money = days_saved * desp_rate
            
            res_box.success(f"💰 STATUS: IN DESPATCH\n\n**Total Credit: ${total_money:,.2f}**")
            audit_box.write(f"📈 **Time Saved:** {days_saved:.4f} days")
            audit_box.write(f"({timedelta(seconds=int(time_saved_sec))} HH:MM:SS)")

        # Audit Summary Details
        st.markdown("### 🔍 Audit Trail")
        a1, a2, a3 = st.columns(3)
        a1.metric("Laytime Start", laytime_start.strftime('%d-%b %H:%M'))
        a2.metric("Expiry Wall", curr.strftime('%d-%b %H:%M'))
        a3.metric("Total Allowed", f"{allowed_sec/86400:.2f} Days")

if __name__ == "__main__":
    tdc_master_engine()
