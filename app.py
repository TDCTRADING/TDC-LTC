import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time

st.set_page_config(page_title="TDC Trade Ops AI", layout="wide")

def tdc_final_engine():
    st.title("🚢 TDC International: Master Laytime Platform")
    
    # --- 1. SIDEBAR: CONTRACTUALS ---
    with st.sidebar:
        st.header("1. Voyage Financials")
        qty = st.number_input("B/L Quantity (MT)", value=36700.0)
        rate = st.number_input("Load/Disch Rate (MT/Day)", value=5000.0)
        demu_rate = st.number_input("Demurrage Rate ($/Day)", value=16500.0)
        
        # Despatch is strictly 50% of Demurrage
        desp_rate = demu_rate / 2
        st.write(f"**Calculated Despatch Rate:** ${desp_rate:,.2f}")
        
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

    # --- 2. MILESTONES ---
    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("⏱️ Key Timestamps")
        nor_tendered = st.datetime_input("NOR Tendered", value=datetime(2026, 2, 1, 0, 1))
        ops_commenced = st.datetime_input("Loading Commenced", value=datetime(2026, 2, 28, 6, 0))
        ops_completed = st.datetime_input("Loading Completed", value=datetime(2026, 3, 9, 4, 0))

    with col2:
        st.subheader("⛈️ Deductions (Weather/Port)")
        sof_events = st.data_editor(
            pd.DataFrame([
                {"Remark": "Port Closed", "Start": datetime(2026, 2, 2, 12, 0), "End": datetime(2026, 2, 16, 23, 59)},
            ]), num_rows="dynamic", use_container_width=True
        )

    # --- 3. CALCULATION ENGINE ---
    if rate > 0:
        # A. NOR Rule
        if nor_rule_type == "12 Hour Turn Time": tt_expiry = nor_tendered + timedelta(hours=12)
        elif nor_rule_type == "24h Turn Time": tt_expiry = nor_tendered + timedelta(hours=24)
        elif nor_rule_type == "LAFAMA Rule":
            tt_expiry = datetime.combine(nor_tendered.date(), time(14, 0)) if nor_tendered.time() < time(12,0) else datetime.combine((nor_tendered + timedelta(days=1)).date(), time(8, 0))
        else: # 6/8 Rule
            tt_expiry = datetime.combine(nor_tendered.date(), time(18, 0)) if nor_tendered.time() < time(12,0) else datetime.combine((nor_tendered + timedelta(days=1)).date(), time(8, 0))

        # B. Start Logic
        lc_start_dt = datetime.combine(laycan_start, time(0, 0))
        trigger = min(tt_expiry, ops_commenced)
        laytime_start = max(trigger, ops_commenced) if trigger < lc_start_dt else trigger

        # C. The Loop
        allowed_sec = (qty / rate) * 86400
        curr = laytime_start
        used_sec = 0
        total_deduct = 0
        step = 600

        while used_sec < allowed_sec and curr < ops_completed:
            excluded = False
            day = curr.weekday()
            
            # Weekend Check
            if "SSHEX" in calendar_basis and day >= 5:
                if "Unless Used" not in calendar_basis or not (ops_commenced <= curr <= ops_completed): excluded = True
            elif "SHEX" in calendar_basis and day == 6:
                if "Unless Used" not in calendar_basis or not (ops_commenced <= curr <= ops_completed): excluded = True
            
            # Weather Check
            if not excluded:
                for _, row in sof_events.iterrows():
                    if pd.to_datetime(row['Start']) <= curr < pd.to_datetime(row['End']):
                        excluded = True
                        break
            
            if excluded: total_deduct += step
            else: used_sec += step
            curr += timedelta(seconds=step)

        # --- 4. THE RESULTS (FIXED) ---
        st.markdown("---")
        res_col1, res_col2 = st.columns(2)

        if ops_completed > curr: # Demurrage Case
            diff = (ops_completed - curr).total_seconds() / 86400
            amt = diff * demu_rate
            res_col1.error(f"⚠️ ON DEMURRAGE\n\nTotal Owed: ${amt:,.2f}")
            res_col2.write(f"**Time on Demurrage:** {diff:.4f} days")
        else: # Despatch Case
            diff = (curr - ops_completed).total_seconds() / 86400
            amt = diff * desp_rate
            res_col1.success(f"✅ IN DESPATCH\n\nTotal Earned: ${amt:,.2f}")
            res_col2.write(f"**Time Saved (Despatch):** {diff:.4f} days")

        res_col2.write(f"**Allowed Time:** {allowed_sec/86400:.4f} days")
        res_col2.write(f"**Laytime Start:** {laytime_start.strftime('%Y-%m-%d %H:%M')}")
        res_col2.write(f"**Expiry Date:** {curr.strftime('%Y-%m-%d %H:%M')}")

if __name__ == "__main__":
    tdc_final_engine()
