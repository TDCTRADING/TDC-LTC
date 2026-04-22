import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time

st.set_page_config(page_title="TDC Dynamic Trade Engine", layout="wide")

def tdc_floating_wall_engine():
    st.title("🚢 TDC International: Dynamic Laytime Engine")
    st.info("The clock stops for weather/port closures and pushes the 'Demurrage Wall' forward.")

    # --- 1. SIDEBAR: CONTRACT SETTINGS ---
    with st.sidebar:
        st.header("Contract Terms")
        qty = st.number_input("Cargo Quantity (MT)", value=20000.0)
        rate = st.number_input("Load Rate (MT/Day)", value=5000.0)
        demu_rate = st.number_input("Demurrage Rate ($/Day)", value=16500.0)
        desp_rate = st.number_input("Despatch Rate ($/Day)", value=demu_rate / 2)
        
        calendar_basis = st.selectbox("Calendar Basis", ["SHINC", "SSHEX", "SHEX"])
        nor_rule = st.selectbox("NOR/Turn Time Rule", [
            "12 Hours Free", "24 Hours Free", "6 Hours Free", "Custom: 12:00 PM Rule"
        ])

    # --- 2. FILE UPLOADER ---
    uploaded_file = st.file_uploader("Upload SOF (PDF/Word/Image)", type=["pdf", "docx", "jpg", "png", "xlsx"])

    # --- 3. TIMESTAMPS & REMARKS ---
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("⏱️ Key Milestones")
        nor_tendered = st.datetime_input("NOR Tendered", value=datetime(2026, 4, 20, 10, 0))
        ops_commenced = st.datetime_input("Loading Commenced", value=datetime(2026, 4, 20, 14, 0))
        ops_completed = st.datetime_input("Loading Completed", value=datetime(2026, 4, 27, 10, 0))

    with col2:
        st.subheader("⛈️ Port Remarks (Deductions)")
        st.caption("Include Rain, Port Closed, Wind, Shifting, etc.")
        sof_events = st.data_editor(
            pd.DataFrame([
                {"Remark": "Rain", "Start": datetime(2026, 4, 21, 8, 0), "End": datetime(2026, 4, 21, 12, 0)},
            ]), num_rows="dynamic", use_container_width=True
        )

    # --- 4. THE DYNAMIC LOGIC ---
    # A. Calculate Laytime Start
    if nor_rule == "Custom: 12:00 PM Rule":
        if nor_tendered.time() >= time(12, 0):
            next_day = nor_tendered + timedelta(days=1)
            official_start = datetime.combine(next_day.date(), time(8, 0))
        else:
            official_start = datetime.combine(nor_tendered.date(), time(14, 0))
    else:
        hours = int(nor_rule.split(' ')[0])
        official_start = nor_tendered + timedelta(hours=hours)
    
    laytime_start = min(official_start, ops_commenced)
    allowed_seconds = (qty / rate) * 86400
    
    # B. The Floating Wall Calculation
    # We Sort events to process them in chronological order
    events = sof_events.copy()
    events['Start'] = pd.to_datetime(events['Start'])
    events['End'] = pd.to_datetime(events['End'])
    events = events.sort_values('Start')

    current_time = laytime_start
    seconds_used = 0
    total_deducted_seconds = 0
    audit_log = []

    # Iterate through time to account for weekend exclusions and weather
    while seconds_used < allowed_seconds and current_time < ops_completed:
        step = 300 # 5-minute increments for high precision
        is_excluded = False
        
        # Check Weekend Exclusions
        if calendar_basis == "SSHEX" and current_time.weekday() >= 5: is_excluded = True
        if calendar_basis == "SHEX" and current_time.weekday() == 6: is_excluded = True
        
        # Check Weather/Remark Deductions
        for _, row in events.iterrows():
            if row['Start'] <= current_time < row['End']:
                rem = str(row['Remark']).upper()
                # Broad keywords to catch everything you mentioned
                if any(k in rem for k in ["RAIN", "WIND", "WEATHER", "CLOSED", "SHIFT", "SAIL", "BERTH", "FAILURE", "STOP"]):
                    is_excluded = True
                    break
        
        if not is_excluded:
            seconds_used += step
        else:
            total_deducted_seconds += step
            
        current_time += timedelta(seconds=step)

    # final_expiry is when the allowed_seconds are finally exhausted
    final_expiry = current_time

    # --- 5. RESULTS ---
    st.markdown("---")
    res_col1, res_col2 = st.columns(2)
    
    if ops_completed > final_expiry:
        diff = (ops_completed - final_expiry).total_seconds() / 86400
        res_col1.error(f"STATUS: ON DEMURRAGE\n\nTotal Due: ${diff * demu_rate:,.2f}")
    else:
        diff = (final_expiry - ops_completed).total_seconds() / 86400
        res_col1.success(f"STATUS: IN DESPATCH\n\nTotal Earned: ${diff * desp_rate:,.2f}")

    res_col2.write("**TDC Audit Summary:**")
    res_col2.write(f"• Laytime Start: {laytime_start.strftime('%Y-%m-%d %H:%M')}")
    res_col2.write(f"• Final Expiry (The Wall): {final_expiry.strftime('%Y-%m-%d %H:%M')}")
    res_col2.write(f"• Total Time Deducted: {timedelta(seconds=total_deducted_seconds)}")

if __name__ == "__main__":
    tdc_floating_wall_engine()
