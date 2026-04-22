import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time
import io

st.set_page_config(page_title="TDC Professional Trade Desk", layout="wide")

def tdc_trade_platform():
    st.title("🚢 TDC International: Master SOF & Laytime Platform")
    
    # --- 1. SIDEBAR: CONTRACTUALS ---
    with st.sidebar:
        st.header("1. Financials")
        qty = st.number_input("Cargo Quantity (MT)", value=36700.0)
        rate = st.number_input("Load Rate (MT/Day)", value=5000.0)
        demu_rate = st.number_input("Demurrage Rate ($/Day)", value=16500.0)
        desp_rate = st.number_input("Despatch Rate ($/Day)", value=8250.0)
        
        st.header("2. Laycan & Working Rules")
        laycan_start = st.date_input("Laycan Start Date", value=datetime(2026, 2, 10))
        
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
    st.subheader("📂 Document Management (PDF, Word, Images, Excel)")
    uploaded_file = st.file_uploader("Upload Statement of Facts", type=["pdf", "docx", "jpg", "jpeg", "png", "xlsx"])
    
    if uploaded_file:
        st.success(f"✅ {uploaded_file.name} successfully attached to this calculation.")
        # If it's an image, let the user see it to read remarks
        if uploaded_file.type.startswith('image/'):
            st.image(uploaded_file, caption="SOF Preview", width=400)

    st.markdown("---")

    # --- 3. MILESTONES ---
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("⏱️ Key Timestamps")
        nor_tendered = st.datetime_input("NOR Tendered", value=datetime(2026, 2, 1, 0, 1))
        ops_commenced = st.datetime_input("Loading Commenced", value=datetime(2026, 2, 28, 6, 0))
        ops_completed = st.datetime_input("Loading Completed", value=datetime(2026, 3, 9, 4, 0))

    with col2:
        st.subheader("⛈️ Weather & Remarks")
        st.caption("Berthing, Shifting, and Surveys are auto-deducted if not on demurrage.")
        sof_events = st.data_editor(
            pd.DataFrame([
                {"Remark": "Port Closed (Weather)", "Start": datetime(2026, 2, 2, 12, 0), "End": datetime(2026, 2, 16, 23, 59)},
                {"Remark": "Rain Interruption", "Start": datetime(2026, 3, 5, 1, 0), "End": datetime(2026, 3, 7, 15, 0)},
            ]), num_rows="dynamic", use_container_width=True
        )

    # --- 4. CALCULATION LOGIC (The "Brain") ---
    
    # NOR Trigger Logic
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

    # Official Start Logic (Laycan & Commencement)
    lc_start_dt = datetime.combine(laycan_start, time(0, 0))
    official_trigger = min(turn_time_expiry, ops_commenced)
    
    if official_trigger < lc_start_dt:
        laytime_start = max(official_trigger, ops_commenced)
    else:
        laytime_start = official_trigger

    # Engine Execution
    allowed_sec = (qty / rate) * 86400
    curr = laytime_start
    used_sec = 0
    total_deduct = 0
    step = 600 # 10-minute resolution

    while used_sec < allowed_sec and curr < ops_completed:
        excluded = False
        day = curr.weekday() # 5=Sat, 6=Sun
        
        # 1. Calendar Basis (Including Unless Used)
        is_weekend = (calendar_basis in ["SSHEX", "SSHEX UNLESS USED"] and day >= 5) or \
                     (calendar_basis in ["SHEX", "SHEX UNLESS USED"] and day == 6)
        
        if is_weekend:
            if "UNLESS USED" in calendar_basis:
                # If loading is actually happening, it counts.
                # We assume loading is happening between ops_commenced and ops_completed
                # except during manual weather remarks entered in the table.
                is_working = (ops_commenced <= curr <= ops_completed)
                if not is_working:
                    excluded = True
            else:
                excluded = True
        
        # 2. Weather & Keywords (Berthing/Shifting/Surveys)
        if not excluded:
            for _, row in sof_events.iterrows():
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
        res1.error(f"STATUS: ON DEMURRAGE\n\nTotal Owed: ${diff_days * demu_rate:,.2f}")
    else:
        diff_days = (final_expiry - ops_completed).total_seconds() / 86400
        res1.success(f"STATUS: IN DESPATCH\n\nTotal Earned: ${diff_days * desp_rate:,.2f}")

    res2.write("**Audit Summary:**")
    res2.write(f"• Start Rule: {nor_rule_type}")
    res2.write(f"• Laytime Start: {laytime_start.strftime('%Y-%m-%d %H:%M')}")
    res2.write(f"• Final Expiry: {final_expiry.strftime('%Y-%m-%d %H:%M')}")
    res2.write(f"• Time Deducted: {timedelta(seconds=total_deduct)}")

if __name__ == "__main__":
    tdc_trade_platform()
