import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time

# Page Setup
st.set_page_config(page_title="TDC Trade Ops AI", layout="wide")

def tdc_final_app():
    st.title("🚢 TDC International: Master Laytime Platform")
    st.markdown("---")

    # --- SIDEBAR: SETTINGS ---
    with st.sidebar:
        st.header("1. Financials")
        qty = st.number_input("Cargo Quantity (MT)", value=20000.0)
        rate = st.number_input("Load Rate (MT/Day)", value=5000.0)
        demu_rate = st.number_input("Demurrage Rate ($/Day)", value=16500.0)
        desp_rate = st.number_input("Despatch Rate ($/Day)", value=demu_rate / 2)
        
        st.header("2. Working Terms")
        calendar_basis = st.selectbox("Calendar Basis", ["SHINC", "SSHEX", "SHEX"])
        nor_rule = st.selectbox("NOR/Turn Time Rule", [
            "12 Hours Free", "24 Hours Free", "6 Hours Free", "Custom: 12:00 PM Rule"
        ])

    # --- FILE UPLOADER ---
    st.subheader("📂 Document Management")
    uploaded_file = st.file_uploader("Upload SOF (PDF, Word, Image, Excel)", 
                                     type=["pdf", "docx", "jpg", "jpeg", "png", "xlsx", "csv"])
    if uploaded_file:
        st.success(f"Successfully attached: {uploaded_file.name}")

    st.markdown("---")

    # --- MILESTONES & REMARKS ---
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("⏱️ Key Timestamps")
        nor_tendered = st.datetime_input("NOR Tendered", value=datetime(2026, 4, 20, 10, 0))
        ops_commenced = st.datetime_input("Loading Commenced", value=datetime(2026, 4, 20, 14, 0))
        ops_completed = st.datetime_input("Loading Completed", value=datetime(2026, 4, 25, 18, 0))

    with col2:
        st.subheader("⛈️ Weather & Remarks")
        st.caption("Add Rain or Breakdowns from your SOF below:")
        sof_events = st.data_editor(
            pd.DataFrame([
                {"Remark": "Rain", "Start": datetime(2026, 4, 22, 8, 0), "End": datetime(2026, 4, 22, 12, 0)},
            ]), num_rows="dynamic", use_container_width=True
        )

    # --- LOGIC ENGINE ---
    # 1. Turn Time / NOR Calculation
    if nor_rule == "12 Hours Free":
        official_start = nor_tendered + timedelta(hours=12)
    elif nor_rule == "24 Hours Free":
        official_start = nor_tendered + timedelta(hours=24)
    elif nor_rule == "6 Hours Free":
        official_start = nor_tendered + timedelta(hours=6)
    else: # 12:00 PM Rule
        if nor_tendered.time() >= time(12, 0):
            # Tenders after 12pm -> Starts 08:00 next day
            next_day = nor_tendered + timedelta(days=1)
            official_start = datetime.combine(next_day.date(), time(8, 0))
        else:
            # Tenders before 12pm -> Starts 14:00 same day
            official_start = datetime.combine(nor_tendered.date(), time(14, 0))
    
    # Laytime starts at official time UNLESS loading commenced sooner
    laytime_start = min(official_start, ops_commenced)
    allowed_days = qty / rate
    allowed_delta = timedelta(days=allowed_days)
    
    # 2. Find the "Wall" (Expiry)
    prelim_expiry = laytime_start + allowed_delta

    # 3. Calendar Deductions (SSHEX/SHEX)
    calendar_deductions = timedelta(0)
    if calendar_basis != "SHINC":
        curr = laytime_start
        while curr < ops_completed:
            if (calendar_basis == "SSHEX" and curr.weekday() >= 5) or (calendar_basis == "SHEX" and curr.weekday() == 6):
                calendar_deductions += timedelta(minutes=15)
            curr += timedelta(minutes=15)

    # 4. Weather Deductions (Once on Demurrage logic)
    weather_deductions = timedelta(0)
    audit_trail = []
    for _, row in sof_events.iterrows():
        try:
            s, e = pd.to_datetime(row['Start']), pd.to_datetime(row['End'])
            remark = str(row['Remark']).upper()
            if any(k in remark for k in ["RAIN", "WIND", "WEATHER", "FAILURE", "SWELL"]):
                if s < prelim_expiry:
                    deduct_end = min(e, prelim_expiry)
                    weather_deductions += (deduct_end - s)
                    audit_trail.append(f"Deducted: {remark}")
                else:
                    audit_trail.append(f"Rejected: {remark} (Vessel on Demurrage)")
        except: continue

    final_expiry = prelim_expiry + weather_deductions + calendar_deductions

    # --- RESULTS ---
    st.markdown("---")
    res_col1, res_col2 = st.columns(2)
    
    if ops_completed > final_expiry:
        diff = (ops_completed - final_expiry).total_seconds() / 86400
        res_col1.error(f"STATUS: ON DEMURRAGE\n\nTotal Owed: ${diff * demu_rate:,.2f}")
    else:
        diff = (final_expiry - ops_completed).total_seconds() / 86400
        res_col1.success(f"STATUS: IN DESPATCH\n\nTotal Earned: ${diff * desp_rate:,.2f}")

    res_col2.write("**Audit Summary:**")
    res_col2.write(f"• Laytime Start: {laytime_start.strftime('%Y-%m-%d %H:%M')}")
    res_col2.write(f"• Allowed Time: {allowed_days:.4f} days")
    res_col2.write(f"• Final Expiry: {final_expiry.strftime('%Y-%m-%d %H:%M')}")
    for log in audit_trail: res_col2.write(f"• {log}")

if __name__ == "__main__":
    tdc_final_app()
