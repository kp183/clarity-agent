import os
import json
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
import google.generativeai as genai
import time
import re
from datetime import datetime
from google.api_core import exceptions # Important for error handling

# --- Data Parsing Functions ---

def parse_incident_logs():
    """Parses only the logs related to the original incident for Reactive Analysis."""
    all_log_entries = []
    log_directory = 'logs'
    incident_files = ['deployment_logs.json', 'config_changes.csv', 'db_performance.log', 'app_errors.log']

    for filename in incident_files:
        filepath = os.path.join(log_directory, filename)
        if not os.path.exists(filepath):
            st.warning(f"Log file not found: {filename}")
            continue

        try:
            if filename.endswith('.json'):
                with open(filepath, 'r') as f:
                    data = json.load(f)
                    for entry in data:
                        all_log_entries.append({'timestamp': entry['timestamp'], 'source': filename, 'message': f"Deployment {entry.get('status', 'N/A')} for {entry.get('app', 'N/A')} version {entry.get('version', 'N/A')}"})
            elif filename.endswith('.csv'):
                df_csv = pd.read_csv(filepath)
                for _, row in df_csv.iterrows():
                    all_log_entries.append({'timestamp': row['timestamp'], 'source': filename, 'message': f"Config change for {row['service']}: {row['parameter']} changed to {row['new_value']}"})
            else: # .log files
                with open(filepath, 'r') as f:
                    for line in f:
                        parts = line.strip().split(' ', 1)
                        if len(parts) == 2:
                            all_log_entries.append({'timestamp': parts[0], 'source': filename, 'message': parts[1]})
        except Exception as e:
            st.error(f"Error parsing {filename}: {e}")
    
    if not all_log_entries:
        return pd.DataFrame()

    log_df = pd.DataFrame(all_log_entries)
    log_df['timestamp'] = pd.to_datetime(log_df['timestamp'], errors='coerce')
    log_df.dropna(subset=['timestamp'], inplace=True)
    return log_df.sort_values(by='timestamp').reset_index(drop=True)

def parse_live_feed_logs():
    """Parses only the live feed for Proactive Monitoring."""
    filepath = os.path.join('logs', 'live_db_feed.log')
    if not os.path.exists(filepath):
        return pd.DataFrame()
    
    live_entries = []
    with open(filepath, 'r') as f:
        for line in f:
            parts = line.strip().split(' ', 1)
            if len(parts) == 2:
                live_entries.append({'timestamp': parts[0], 'source': 'live_db_feed.log', 'message': parts[1]})

    log_df = pd.DataFrame(live_entries)
    log_df['timestamp'] = pd.to_datetime(log_df['timestamp'], errors='coerce')
    return log_df


# --- AI and Anomaly Functions ---
@st.cache_data
def get_rca_from_gemini(log_dataframe):
    if log_dataframe.empty:
        return None
    log_data_string = log_dataframe.to_string()
    
    prompt = f"""
    You are an expert Site Reliability Engineer specializing in root cause analysis.
    Analyze the following consolidated log data to determine the root cause of the incident.

    **Log Data:**
    ---
    {log_data_string}
    ---

    **Task:**
    Provide a root cause analysis report in a clean JSON format. Do not include any text outside the JSON.
    The JSON must contain these exact keys: "summary", "root_cause", "evidence", "recommended_action", "confidence_score", and "executable_command".
    The "executable_command" should be a safe, single-line, simulated shell command that an IT technician could run to fix the problem. For example, if the problem is a bad deployment, the command could be "kubectl rollout undo deployment/auth-service". If no simple command is possible, return an empty string "".
    """
    try:
        model = genai.GenerativeModel('gemini-1.5-flash-latest') 
        response = model.generate_content(prompt)
        json_response_text = response.text.strip().replace('```json', '').replace('```', '')
        return json.loads(json_response_text)
    except exceptions.ResourceExhausted as e:
        st.error("API Rate Limit Reached. Please wait a minute and click 'Analyze' again.")
        return None
    except Exception as e:
        st.error(f"An error occurred during AI analysis: {e}")
        return None

def check_for_anomalies(df_logs):
    db_logs = df_logs[df_logs['source'] == 'live_db_feed.log'].copy()
    if db_logs.empty: return None
    db_logs.loc[:, 'latency'] = db_logs['message'].str.extract(r'(\d+)ms').astype(float)
    if not db_logs.empty:
        time_cutoff = db_logs['timestamp'].max() - pd.Timedelta(minutes=5)
        recent_latency_logs = db_logs[db_logs['timestamp'] >= time_cutoff]
        high_latency_events = recent_latency_logs[recent_latency_logs['latency'] > 300]
        if len(high_latency_events) >= 2:
            avg_latency = high_latency_events['latency'].mean()
            return f"Detected {len(high_latency_events)} high-latency DB events in the last 5 minutes, with an average latency of {avg_latency:.0f}ms."
    return None

@st.cache_data
def generate_proactive_alert(summary):
    prompt = f"""
    You are a proactive monitoring AI. Based on the following anomaly, write a concise, actionable alert for an IT technician in JSON format.
    **Anomaly:** {summary}
    **Task:** Generate a JSON object with keys "headline" and "recommendation".
    """
    try:
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        response = model.generate_content(prompt)
        json_response_text = response.text.strip().replace('```json', '').replace('```', '')
        return json.loads(json_response_text)
    except exceptions.ResourceExhausted:
        return {"headline": "API Rate Limit Reached", "recommendation": "Pausing monitoring checks for 60 seconds..."}
    except Exception as e:
        return {"headline": "Alert Generation Failed", "recommendation": str(e)}

# --- Main Application UI ---
st.set_page_config(page_title="Clarity Agent", layout="wide")
st.title("Clarity Agent: AI-Powered Root Cause Analysis 🕵️‍♂️")

# Configure API Key
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    st.error("🚨 GOOGLE_API_KEY not found! Please add it to your .env file.")
else:
    genai.configure(api_key=api_key)

# Initialize Session State
if 'log_df' not in st.session_state: st.session_state.log_df = None
if 'rca_report' not in st.session_state: st.session_state.rca_report = None
if 'messages' not in st.session_state: st.session_state.messages = []

tab1, tab2 = st.tabs(["**Reactive Analysis**", "**Proactive Monitoring**"])

# --- TAB 1: REACTIVE ANALYSIS ---
with tab1:
    st.header("Analyze a Past Incident")
    if st.button("Analyze Incident Logs"):
        # Reset state for a new run
        st.session_state.messages = []
        st.session_state.rca_report = None
        st.session_state.log_df = None
        
        with st.spinner("Reading and consolidating incident logs..."):
            st.session_state.log_df = parse_incident_logs() 
        
        if st.session_state.log_df.empty:
            st.error("No incident logs found or failed to parse. Please check the `logs` directory.")
        else:
            st.success("✅ Incident logs consolidated successfully!")
            with st.spinner("🤖 AI is analyzing the root cause..."):
                st.session_state.rca_report = get_rca_from_gemini(st.session_state.log_df)

    if st.session_state.log_df is not None and not st.session_state.log_df.empty:
        st.subheader("Consolidated Event Timeline")
        st.dataframe(st.session_state.log_df, width='stretch')
    
    if st.session_state.rca_report:
        report = st.session_state.rca_report
        st.success("✅ AI analysis complete!")
        
        col1, col2 = st.columns([3, 1]) 
        with col1:
            st.subheader("AI-Generated Root Cause Analysis Report")
            st.markdown(f"**Summary:** {report.get('summary', 'N/A')}")
            st.markdown(f"**Root Cause:** {report.get('root_cause', 'N/A')}")
            st.markdown("**Evidence:**")
            for ev in report.get('evidence', []):
                st.code(ev, language='log')
            st.warning(f"**Recommended Action:** {report.get('recommended_action', 'N/A')}")
        
        with col2:
            st.metric(label="Confidence Score", value=f"{report.get('confidence_score', 0) * 100:.0f}%")
            
            command = report.get("executable_command")
            if command:
                st.divider()
                st.subheader("🪄 Automated Remediation")
                st.info("The AI has suggested an automated fix for this issue.")
                if st.button("Execute Remediation", type="primary"):
                    st.divider()
                    st.subheader("Simulated Terminal")
                    terminal_placeholder = st.empty()
                    
                    full_command = f"$ {command}"
                    output = ""
                    for i in range(len(full_command) + 1):
                        output = full_command[:i] + "█"
                        terminal_placeholder.code(output, language="shell")
                        time.sleep(0.05)
                    
                    for i in range(3):
                        output = full_command + "\n" + "." * (i + 1)
                        terminal_placeholder.code(output, language="shell")
                        time.sleep(0.5)

                    success_message = f"✅ Success!\nDeployment 'auth-service' successfully rolled back."
                    output = full_command + "\n" + success_message
                    terminal_placeholder.code(output, language="shell")

        st.divider()
        st.subheader("Workflow Tools")
        if st.button("Push to Ticket"):
            evidence_str = "\n".join([f"- {ev}" for ev in report.get('evidence', [])])
            ticket_update_text = f"""### 🤖 AI-Generated Incident Analysis..."""
            st.subheader("Formatted Ticket Update")
            st.code(ticket_update_text, language="markdown")

        st.subheader("💬 Ask a Follow-up Question")
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
        if prompt := st.chat_input("e.g., Show me all logs from app_errors.log"):
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)
            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    # This is a simplified prompt for the chat
                    follow_up_prompt = f"Context:\n{st.session_state.log_df.to_string()}\n\nQuestion: {prompt}\n\nAnswer:"
                    model = genai.GenerativeModel('gemini-1.5-flash-latest')
                    response = model.generate_content(follow_up_prompt)
                    st.markdown(response.text)
                    st.session_state.messages.append({"role": "assistant", "content": response.text})

# --- TAB 2: PROACTIVE MONITORING ---
with tab2:
    st.header("Live Anomaly Detection")
    st.info("This simulates a live monitoring agent scanning new logs for patterns of trouble.")
    
    if st.toggle("Activate Monitor Mode"):
        st.success("Monitor is active. Scanning for anomalies...")
        alert_placeholder = st.empty()
        status_placeholder = st.empty()
        
        while True:
            live_logs = parse_live_feed_logs() 
            if not live_logs.empty:
                anomaly_summary = check_for_anomalies(live_logs)
                if anomaly_summary:
                    alert = generate_proactive_alert(anomaly_summary)
                    with alert_placeholder.container():
                        st.warning(f"🚨 **Proactive Alert:** {alert.get('headline', 'N/A')}")
                        st.info(f"**Recommendation:** {alert.get('recommendation', 'N/A')}")
                        # If we hit a rate limit, pause for a minute
                        if "Rate Limit" in alert.get('headline', ''):
                            time.sleep(60)
            
            now = datetime.now().strftime("%H:%M:%S")
            status_placeholder.info(f"Status: OK. Last checked for anomalies at {now}. Waiting for next scan...")
            
            # Slow down the loop to avoid hitting the rate limit
            time.sleep(15)