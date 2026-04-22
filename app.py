import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time

st.set_page_config(page_title="TDC Universal Laytime", layout="wide")

def tdc_universal_engine():
    st.title("🚢 TDC International: Master Laytime Platform")
    
    # --- 1. SIDEBAR: CONTRACTUALS ---
    with st.sidebar:
        st.header("1. Financials")
        qty = st.number_input("Cargo Quantity (MT)", value=0.0)
        rate = st.number_input("Load/Disch Rate (MT/Day)", value=0.0)
        demu_rate = st.number_input("Demurrage Rate ($/Day)", value=0.0)
        desp_rate = st.number_input("Despatch Rate ($/Day)", value=0.0)
        
        st.header("2. Working Rules")
        laycan_start = st.date_input("Laycan Start Date")
        
        calendar_basis = st.selectbox("Calendar Basis", [
            "SHINC", 
            "SSHEX (Unless Used)", 
            "SHEX (Unless Used)",
            "SSHEX (Even if Used)", 
            "SHEX (Even if Used)"
        ])

        nor_rule_type = st.selectbox("NOR Rule Type", [
            "12 Hour Turn Time",
            "24h Turn Time",
            "LAFAMA Rule (12:00 PM Custom)",
            "6:00 PM / 8:00 AM Rule"
        ])

    # --- 2. DOCUMENT UPLOADER ---
    st.subheader("📂 Document Management")
    uploaded_file = st.file_uploader("Upload SOF", type=["pdf", "docx", "jpg", "jpeg", "png", "xlsx"])

    st.markdown("---")

    # --- 3. MILESTONES & REMARKS ---
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("⏱️ Key Timestamps")
        nor_tendered = st.datetime_input("NOR Tendered", value=datetime.now())
        ops_commenced = st.datetime_input("Loading/Disch Commenced", value=datetime.now())
        ops_completed = st.datetime_input("Loading/Disch Completed", value=datetime.now())

    with col2:
        st.subheader("⛈️ Deductions")
        st.caption("Berthing, Shifting, and Surveys are auto-deducted if not on demurrage.")
        sof_events = st.data_editor(
            pd.DataFrame([
                {"Remark": "", "Start": datetime.now(), "End": datetime.now()},
            ]), num_rows="dynamic", use_container_width=True
        )

    # --- 4. CALCULATION LOGIC ---
    if rate > 0 and qty > 0:
        # A. NOR Rule Calculation
        if nor_rule_type == "12 Hour Turn Time":
            turn_time_expiry = nor_tendered + timedelta(hours=12)
        elif nor_rule_type == "24h Turn Time":
            turn_time_expiry = nor_tendered + timedelta(hours=24)
        elif nor_rule_type == "LAFAMA Rule (12:00 PM Custom)":
            if nor_tendered.time() >= time(12, 0):
                turn_time_expiry = datetime.combine((nor_tendered + timedelta(days=1)).date(), time(8, 0))
            else:
                turn_time_expiry = datetime.combine(nor_tendered.date(), time(14, 0))
        else: # 6:00 PM / 8:00 AM Rule
            if nor_tendered.time() < time(12, 0):
                turn_time_expiry = datetime.combine(nor_tendered.date(), time(18, 0))
            else:
                turn_time_expiry = datetime.combine((nor_tendered + timedelta(days=1)).date(), time(8, 0))

        # B. Official Start Logic (Laycan & Commencement)
        lc_start_dt = datetime.combine(laycan_start, time(0, 0))
        official_trigger = min(turn_time_expiry, ops_commenced)
        
        if official_trigger < lc_start_dt:
            laytime_start = max(official_trigger, ops_commenced)
        else:
            laytime_start = official_trigger

        # C. The Engine
        allowed_sec = (qty / rate) * 86400
        curr = laytime_start
        used_sec = 0
        total_deduct = 0
        step = 600 # 10-minute precision

        while used_sec < allowed_sec and curr < ops_completed:
            excluded = False
            day = curr.weekday() # 5=Sat, 6=Sun
            
            # 1. Calendar Logic
            if "SSHEX" in calendar_basis and day >= 5:
                if "Unless Used" in calendar_basis:
                    # If NOT between commenced and completed, it's excluded. 
                    # If we are loading, it counts.
                    if not (ops_commenced <= curr <= ops_completed): excluded = True
                else: # Even if used
                    excluded = True
            
            elif "SHEX" in calendar_basis and day == 6:
                if "Unless Used" in calendar_basis:
                    if not (ops_commenced <= curr <= ops_completed): excluded = True
                else: # Even if used
                    excluded = True
            
            # 2. Weather & Keywords (Only if not already excluded by weekend)
            if not excluded:
                for _, row in sof_events.iterrows():
                    if pd.to_datetime(row['Start']) <= curr < pd.to_datetime(row['End']):
                        rem = str(row['Remark']).upper()
                        # Keywords for auto-exclusion
                        if any(k in rem for k in ["RAIN", "WIND", "WEATHER", "CLOSED", "SURVEY", "BERTH", "SHIFT"]):
                            excluded = True
                            break
            
            if excluded: total_deduct += step
            else: used_sec += step
            curr += timedelta(seconds=step)

        final_expiry = curr

        # --- 5. RESULTS ---
        st.markdown("---")
        r1, r2 = st.columns(2)
        if ops_completed > final_expiry:
            diff = (ops_completed - final_expiry).total_seconds() / 86400
            r1.error(f"STATUS: ON DEMURRAGE\n\nTotal Due: ${diff * demu_rate:,.2f}")
        else:
            diff = (final_expiry - ops_completed).total_seconds() / 86400
            r1.success(f"STATUS: IN DESPATCH\n\nTotal Earned: ${diff * desp_rate:,.2f}")

        r2.write("**Final Audit:**")
        r2.write(f"• Laytime Start: {laytime_start.strftime('%Y-%m-%d %H:%M')}")
        r2.write(f"• Expiry (Wall): {final_expiry.strftime('%Y-%m-%d %H:%M')}")
        r2.write(f"• Total Time Deducted: {timedelta(seconds=total_deduct)}")
    else:
        st.warning("Awaiting Quantity and Rate input...")

if __name__ == "__main__":
    tdc_universal_engine()
