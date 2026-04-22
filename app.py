import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time

st.set_page_config(page_title="TDC Trade Ops AI", layout="wide")

# --- SESSION STATE FOR PERSISTENT DATA ---
if 'nor_val' not in st.session_state:
    st.session_state.nor_val = datetime(2026, 3, 8, 7, 0)
if 'commenced_val' not in st.session_state:
    st.session_state.commenced_val = datetime(2026, 3, 10, 21, 30)
if 'completed_val' not in st.session_state:
    st.session_state.completed_val = datetime(2026, 3, 13, 3, 40)

def tdc_final_engine():
    st.title("🚢 TDC International: Master Laytime Platform")
    
    # --- 1. SIDEBAR ---
    with st.sidebar:
        st.header("1. Voyage Financials")
        qty = st.number_input("B/L Quantity (MT)", value=7827.0)
        rate = st.number_input("Load/Disch Rate (MT/Day)", value=3200.0)
        demu_rate = st.number_input("Demurrage Rate ($/Day)", value=6000.0)
        desp_rate = demu_rate / 2
        st.info(f"**Despatch Rate:** ${desp_rate:,.2f} / day")
        
        st.header("2. Working Rules")
        laycan_start = st.date_input("Laycan Start Date", value=datetime(2026, 3, 9))
        calendar_basis = st.selectbox("Calendar Basis", [
            "SHINC", 
            "SSHEX (Unless Used)", 
            "SHEX (Unless Used)",
            "SSHEX (Even if Used)", 
            "SHEX (Even if Used)"
        ])
        nor_rule_type = st.selectbox("NOR Rule Type", [
            "12 Hour Turn Time", "24h Turn Time",
            "LAFAMA Rule (12:00 PM Custom)", "6:00 PM / 8:00 AM Rule"
        ])

    # --- 2. FILE UPLOADER ---
    st.subheader("📂 Document Management")
    uploaded_file = st.file_uploader("Upload SOF", type=["pdf", "docx", "jpg", "jpeg", "png", "xlsx"])
    if uploaded_file:
        st.success(f"✅ Document '{uploaded_file.name}' Active")

    st.markdown("---")

    # --- 3. MILESTONES ---
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("⏱️ Key Timestamps")
        nor_t = st.datetime_input("NOR Tendered", value=st.session_state.nor_val)
        ops_s = st.datetime_input("Loading Commenced", value=st.session_state.commenced_val)
        ops_e = st.datetime_input("Loading Completed", value=st.session_state.completed_val)

    with col2:
        st.subheader("⛈️ Deductions")
        sof_events = st.data_editor(
            pd.DataFrame([{"Remark": "Weather", "Start": datetime(2026, 1, 1), "End": datetime(2026, 1, 1)}]),
            num_rows="dynamic", use_container_width=True
        )

    # --- 4. CALCULATION ---
    if rate > 0:
        # Turn Time
        if nor_rule_type == "12 Hour Turn Time": tt_exp = nor_t + timedelta(hours=12)
        elif nor_rule_type == "24h Turn Time": tt_exp = nor_t + timedelta(hours=24)
        elif "LAFAMA" in nor_rule_type:
            tt_exp = datetime.combine(nor_t.date(), time(14, 0)) if nor_t.time() < time(12,0) else datetime.combine((nor_t + timedelta(days=1)).date(), time(8, 0))
        else: # 6/8 Rule
            tt_exp = datetime.combine(nor_t.date(), time(18, 0)) if nor_t.time() < time(12,0) else datetime.combine((nor_t + timedelta(days=1)).date(), time(8, 0))

        # Start Logic
        lc_start = datetime.combine(laycan_start, time(0,0))
        trigger = min(tt_exp, ops_s)
        l_start = max(trigger, ops_s) if trigger < lc_start else trigger

        # Engine Logic
        total_allowed_sec = (qty / rate) * 86400
        curr = l_start
        used_sec = 0
        step = 60 # 1-minute precision
        
        while used_sec < total_allowed_sec:
            excluded = False
            day = curr.weekday() # 5=Sat, 6=Sun
            
            # THE FIX: HARD CALENDAR LOGIC
            if "SSHEX" in calendar_basis and day >= 5: # Saturday & Sunday
                if "Unless Used" in calendar_basis:
                    # If we are loading, it COUNTS (not excluded)
                    if not (ops_s <= curr <= ops_e): excluded = True
                else: # Even if Used
                    excluded = True
            
            elif "SHEX" in calendar_basis and day == 6: # Sunday Only
                if "Unless Used" in calendar_basis:
                    if not (ops_s <= curr <= ops_e): excluded = True
                else: # Even if Used
                    excluded = True
            
            # Weather / Remark Check
            if not excluded:
                for _, row in sof_events.iterrows():
                    if pd.to_datetime(row['Start']) <= curr < pd.to_datetime(row['End']):
                        excluded = True
                        break
            
            if not excluded: used_sec += step
            curr += timedelta(seconds=step)

        # --- 5. RESULTS ---
        st.markdown("---")
        res_col, audit_col = st.columns([2, 1])

        diff_sec = (curr - ops_e).total_seconds()
        days_diff = abs(diff_sec) / 86400

        if diff_sec < 0: # Demurrage (Completed AFTER Expiry)
            amt = days_diff * demu_rate
            res_col.error(f"🚨 STATUS: ON DEMURRAGE\n\n**Total Due: ${amt:,.2f}**")
            audit_col.write(f"📉 Time Lost: {days_diff:.4f} days")
        else: # Despatch (Completed BEFORE Expiry)
            amt = days_diff * desp_rate
            res_col.success(f"💰 STATUS: IN DESPATCH\n\n**Total Credit: ${amt:,.2f}**")
            audit_col.write(f"📈 Time Saved: {days_diff:.4f} days")

        audit_col.write(f"**Allowed:** {total_allowed_sec/86400:.4f} Days")
        audit_col.write(f"**Start:** {l_start.strftime('%d-%b %Y %H:%M')}")
        audit_col.write(f"**Expiry Wall:** {curr.strftime('%d-%b %Y %H:%M')}")

if __name__ == "__main__":
    tdc_final_engine()
