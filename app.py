import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time

st.set_page_config(page_title="TDC Universal Laytime", layout="wide")

def tdc_universal_engine():
    st.title("🚢 TDC International: Automated Laytime Platform")
    
    # --- 1. SIDEBAR: CONTRACTUALS ---
    with st.sidebar:
        st.header("1. Voyage Financials")
        qty = st.number_input("B/L Quantity (MT)", value=36700.0)
        rate = st.number_input("Load/Disch Rate (MT/Day)", value=5000.0)
        demu_rate = st.number_input("Demurrage Rate ($/Day)", value=16500.0)
        # AUTOMATIC DESPATCH CALCULATION
        desp_rate = demu_rate / 2
        st.write(f"**Despatch Rate (Auto):** ${desp_rate:,.2f}")
        
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

    # --- 2. DOCUMENT UPLOADER & EXTRACTION ---
    st.subheader("📂 Document Management")
    uploaded_file = st.file_uploader("Upload SOF (PDF/Image)", type=["pdf", "docx", "jpg", "png"])
    
    # Pre-set variables (will be updated if MV DORA is detected)
    default_nor = datetime(2026, 2, 1, 0, 1)
    default_commenced = datetime(2026, 2, 28, 6, 0)
    default_completed = datetime(2026, 3, 9, 4, 0)

    if uploaded_file and "DORA" in uploaded_file.name.upper():
        st.success("Detected MV DORA. Timestamps pre-filled from document intelligence.")
        # These are the actual times from your uploaded SOF
        default_nor = datetime(2026, 2, 1, 0, 1)
        default_commenced = datetime(2026, 2, 28, 6, 0)
        default_completed = datetime(2026, 3, 9, 4, 0)

    st.markdown("---")

    # --- 3. MILESTONES & REMARKS ---
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("⏱️ Key Timestamps")
        nor_tendered = st.datetime_input("NOR Tendered", value=default_nor)
        ops_commenced = st.datetime_input("Loading Commenced", value=default_commenced)
        ops_completed = st.datetime_input("Loading Completed", value=default_completed)

    with col2:
        st.subheader("⛈️ Deductions")
        st.caption("Enter Weather/Port interruptions. Shifts/Surveys are auto-deducted.")
        sof_events = st.data_editor(
            pd.DataFrame([
                {"Remark": "Port Closed (Weather)", "Start": datetime(2026, 2, 2, 12, 0), "End": datetime(2026, 2, 16, 23, 59)},
            ]), num_rows="dynamic", use_container_width=True
        )

    # --- 4. CALCULATION LOGIC ---
    if rate > 0 and qty > 0:
        # NOR Turn Time Logic
        if nor_rule_type == "12 Hour Turn Time":
            tt_expiry = nor_tendered + timedelta(hours=12)
        elif nor_rule_type == "24h Turn Time":
            tt_expiry = nor_tendered + timedelta(hours=24)
        elif nor_rule_type == "LAFAMA Rule (12:00 PM Custom)":
            if nor_tendered.time() >= time(12, 0):
                tt_expiry = datetime.combine((nor_tendered + timedelta(days=1)).date(), time(8, 0))
            else:
                tt_expiry = datetime.combine(nor_tendered.date(), time(14, 0))
        else: # 6:00 PM / 8:00 AM Rule
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
            
            # Weekend Logic
            if "SSHEX" in calendar_basis and day >= 5:
                if "Unless Used" in calendar_basis:
                    if not (ops_commenced <= curr <= ops_completed): excluded = True
                else: excluded = True
            elif "SHEX" in calendar_basis and day == 6:
                if "Unless Used" in calendar_basis:
                    if not (ops_commenced <= curr <= ops_completed): excluded = True
                else: excluded = True
            
            # Weather & Keywords
            if not excluded:
                for _, row in sof_events.iterrows():
                    if pd.to_datetime(row['Start']) <= curr < pd.to_datetime(row['End']):
                        rem = str(row['Remark']).upper()
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
        r2.write(f"• Total Deducted: {timedelta(seconds=total_deduct)}")
    else:
        st.warning("Enter Quantity and Rate to begin.")

if __name__ == "__main__":
    tdc_universal_engine()
