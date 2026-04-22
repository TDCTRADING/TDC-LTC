import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time

st.set_page_config(page_title="TDC Universal Laytime", layout="wide")

def tdc_universal_engine():
    st.title("🚢 TDC International: Universal Laytime Platform")
    st.info("Upload your SOF and enter contract terms below to generate a professional laytime statement.")
    
    # --- 1. SIDEBAR: CONTRACTUALS ---
    with st.sidebar:
        st.header("1. Voyage Financials")
        qty = st.number_input("B/L Quantity (MT)", value=0.0)
        rate = st.number_input("Load/Disch Rate (MT/Day)", value=0.0)
        demu_rate = st.number_input("Demurrage Rate ($/Day)", value=0.0)
        desp_rate = st.number_input("Despatch Rate ($/Day)", value=0.0)
        
        st.header("2. Contract Rules")
        laycan_start = st.date_input("Laycan Start Date")
        
        calendar_basis = st.selectbox("Calendar Basis", [
            "SHINC", "SSHEX", "SHEX", "SSHEX UNLESS USED", "SHEX UNLESS USED"
        ])

        nor_rule_type = st.selectbox("NOR Rule Type", [
            "12 Hour Turn Time",
            "24h Turn Time",
            "LAFAMA Rule (12:00 PM Custom)",
            "6:00 PM / 8:00 AM Rule"
        ])

    # --- 2. MULTI-FORMAT UPLOADER ---
    st.subheader("📂 Document Management")
    uploaded_file = st.file_uploader("Upload SOF (PDF, Word, Images, Excel)", type=["pdf", "docx", "jpg", "jpeg", "png", "xlsx"])
    if uploaded_file:
        st.success(f"Document '{uploaded_file.name}' attached.")

    st.markdown("---")

    # --- 3. MILESTONES ---
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("⏱️ Key Timestamps")
        nor_tendered = st.datetime_input("NOR Tendered", value=datetime.now())
        ops_commenced = st.datetime_input("Loading/Disch Commenced", value=datetime.now())
        ops_completed = st.datetime_input("Loading/Disch Completed", value=datetime.now())

    with col2:
        st.subheader("⛈️ Deductions (Weather/Port)")
        st.caption("Add Rain, Wind, Shifting, or Surveys. These are ignored if vessel is already on demurrage.")
        sof_events = st.data_editor(
            pd.DataFrame([
                {"Remark": "", "Start": datetime.now(), "End": datetime.now()},
            ]), num_rows="dynamic", use_container_width=True
        )

    # --- 4. CALCULATION ENGINE ---
    
    # A. NOR Turn Time Calculation
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
    
    # If arrival/turn-time is before Laycan, only loading commencement can trigger early.
    if official_trigger < lc_start_dt:
        laytime_start = max(official_trigger, ops_commenced)
    else:
        laytime_start = official_trigger

    # C. Dynamic Floating Wall Engine
    if rate > 0 and qty > 0:
        allowed_sec = (qty / rate) * 86400
        curr = laytime_start
        used_sec = 0
        total_deduct = 0
        step = 600 # 10-minute precision

        while used_sec < allowed_sec and curr < ops_completed:
            excluded = False
            day = curr.weekday() # 5=Sat, 6=Sun
            
            # Weekend Logic
            is_weekend = (calendar_basis in ["SSHEX", "SSHEX UNLESS USED"] and day >= 5) or \
                         (calendar_basis in ["SHEX", "SHEX UNLESS USED"] and day == 6)
            
            if is_weekend:
                if "UNLESS USED" in calendar_basis:
                    if not (ops_commenced <= curr <= ops_completed):
                        excluded = True
                else:
                    excluded = True
            
            # Weather & Keywords
            if not excluded:
                for _, row in sof_events.iterrows():
                    # Check if current time falls within a remark period
                    if pd.to_datetime(row['Start']) <= curr < pd.to_datetime(row['End']):
                        rem = str(row['Remark']).upper()
                        if any(k in rem for k in ["RAIN", "WIND", "WEATHER", "CLOSED", "SURVEY", "BERTH", "SHIFT", "SWELL"]):
                            excluded = True
                            break
            
            if excluded: total_deduct += step
            else: used_sec += step
            curr += timedelta(seconds=step)

        final_expiry = curr

        # --- 5. RESULTS ---
        st.markdown("---")
        res1, res2 = st.columns(2)
        if ops_completed > final_expiry:
            diff_days = (ops_completed - final_expiry).total_seconds() / 86400
            res1.error(f"STATUS: ON DEMURRAGE\n\nTotal Due: ${diff_days * demu_rate:,.2f}")
        else:
            diff_days = (final_expiry - ops_completed).total_seconds() / 86400
            res1.success(f"STATUS: IN DESPATCH\n\nTotal Earned: ${diff_days * desp_rate:,.2f}")

        res2.write("**Audit Summary:**")
        res2.write(f"• Laytime Start: {laytime_start.strftime('%Y-%m-%d %H:%M')}")
        res2.write(f"• Final Expiry: {final_expiry.strftime('%Y-%m-%d %H:%M')}")
        res2.write(f"• Total Deducted: {timedelta(seconds=total_deduct)}")
    else:
        st.warning("Please enter Quantity and Rate in the sidebar to calculate.")

if __name__ == "__main__":
    tdc_universal_engine()
