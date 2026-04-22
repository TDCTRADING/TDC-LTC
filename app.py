import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time
import base64

st.set_page_config(page_title="TDC Trade Ops AI", layout="wide")

# --- SESSION STATE ---
if 'nor_val' not in st.session_state:
    st.session_state.nor_val = datetime(2026, 3, 8, 7, 0)
if 'commenced_val' not in st.session_state:
    st.session_state.commenced_val = datetime(2026, 3, 10, 21, 30)
if 'completed_val' not in st.session_state:
    st.session_state.completed_val = datetime(2026, 3, 13, 3, 40)

def tdc_final_engine():
    st.title("🚢 TDC International: Master Laytime Platform")
    
    # --- 1. SIDEBAR: SHIP & VOYAGE DETAILS ---
    with st.sidebar:
        st.header("🚢 Voyage Identity")
        vessel_name = st.text_input("Vessel Name", value="MV DORA")
        bl_date = st.date_input("B/L Date", value=datetime(2026, 3, 1))
        
        st.header("💰 Financials")
        qty = st.number_input("B/L Quantity (MT)", value=7827.0)
        rate = st.number_input("Load/Disch Rate (MT/Day)", value=3200.0)
        demu_rate = st.number_input("Demurrage Rate ($/Day)", value=6000.0)
        desp_rate = demu_rate / 2
        st.info(f"**Despatch Rate:** ${desp_rate:,.2f}")
        
        st.header("⚖️ Contract Rules")
        laycan_start = st.date_input("Laycan Start Date", value=datetime(2026, 3, 9))
        calendar_basis = st.selectbox("Calendar Basis", [
            "SHINC", "SSHEX (Unless Used)", "SHEX (Unless Used)",
            "SSHEX (Even if Used)", "SHEX (Even if Used)"
        ])
        nor_rule_type = st.selectbox("NOR Rule Type", [
            "12 Hour Turn Time", "24h Turn Time",
            "LAFAMA Rule", "6:00 PM / 8:00 AM Rule"
        ])

    # --- 2. MILESTONES & DEDUCTIONS ---
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("⏱️ Key Timestamps")
        nor_t = st.datetime_input("NOR Tendered", value=st.session_state.nor_val)
        ops_s = st.datetime_input("Loading Commenced", value=st.session_state.commenced_val)
        ops_e = st.datetime_input("Loading Completed", value=st.session_state.completed_val)

    with col2:
        st.subheader("⛈️ Deductions Table")
        sof_events = st.data_editor(
            pd.DataFrame([
                {"Remark": "Draft Survey", "Start": datetime(2026, 3, 10, 18, 0), "End": datetime(2026, 3, 10, 20, 0)},
                {"Remark": "Berthing", "Start": datetime(2026, 3, 10, 20, 0), "End": datetime(2026, 3, 10, 21, 30)},
            ]), num_rows="dynamic", use_container_width=True
        )

    # --- 3. CALCULATION ENGINE ---
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

        total_allowed_sec = (qty / rate) * 86400
        curr = l_start
        used_sec = 0
        while used_sec < total_allowed_sec:
            excluded = False
            day = curr.weekday()
            if "SSHEX" in calendar_basis and day >= 5:
                if "Unless Used" not in calendar_basis or not (ops_s <= curr <= ops_e): excluded = True
            elif "SHEX" in calendar_basis and day == 6:
                if "Unless Used" not in calendar_basis or not (ops_s <= curr <= ops_e): excluded = True
            if not excluded:
                for _, row in sof_events.iterrows():
                    if pd.to_datetime(row['Start']) <= curr < pd.to_datetime(row['End']):
                        if any(k in str(row['Remark']).upper() for k in ["CLEANING", "SURVEY", "BERTH", "WEATHER", "RAIN", "WIND", "SHIFT"]):
                            excluded = True
                            break
            if not excluded: used_sec += 60
            curr += timedelta(seconds=60)

        # --- 4. RESULTS DISPLAY ---
        st.markdown("---")
        diff_sec = (curr - ops_e).total_seconds()
        days_diff = abs(diff_sec) / 86400
        
        res_col, pdf_col = st.columns([2, 1])
        
        if diff_sec < 0:
            total_money = days_diff * demu_rate
            res_col.error(f"🚨 {vessel_name}: ON DEMURRAGE\n\n**Total Due: ${total_money:,.2f}**")
            status_text = "DEMURRAGE"
        else:
            total_money = days_diff * desp_rate
            res_col.success(f"💰 {vessel_name}: IN DESPATCH\n\n**Total Credit: ${total_money:,.2f}**")
            status_text = "DESPATCH"

        # --- 5. PDF GENERATION LOGIC ---
        pdf_col.subheader("📤 Share Results")
        if pdf_col.button("Generate PDF Statement"):
            html_content = f"""
            <html>
            <body style="font-family: Arial; padding: 40px; color: #333;">
                <h1 style="color: #1a4a7a; border-bottom: 2px solid #1a4a7a;">LAYTIME STATEMENT</h1>
                <p><strong>Vessel:</strong> {vessel_name} | <strong>B/L Date:</strong> {bl_date}</p>
                <hr>
                <h3>Voyage Data</h3>
                <table style="width: 100%; border-collapse: collapse;">
                    <tr><td>Quantity: {qty} MT</td><td>Rate: {rate} MT/Day</td></tr>
                    <tr><td>Laytime Start: {l_start.strftime('%d-%b %H:%M')}</td><td>Expiry Wall: {curr.strftime('%d-%b %H:%M')}</td></tr>
                </table>
                <h2 style="margin-top: 30px; color: {'red' if diff_sec < 0 else 'green'};">RESULT: {status_text}</h2>
                <p style="font-size: 24px;">TOTAL VALUE: ${total_money:,.2f}</p>
                <p>Time Difference: {days_diff:.4f} days</p>
                <footer style="margin-top: 50px; font-size: 10px; color: gray;">Generated by TDC Trade Ops AI</footer>
            </body>
            </html>
            """
            st.info("PDF Content generated. In a real server environment, we would now convert this HTML to a PDF file for download.")
            st.download_button("Download Data as CSV", data=sof_events.to_csv(), file_name=f"{vessel_name}_laytime.csv")

if __name__ == "__main__":
    tdc_final_engine()
