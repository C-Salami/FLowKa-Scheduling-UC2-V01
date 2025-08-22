import json
import requests
import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Voice → Gantt", layout="wide")

# ---- Config / Settings
DEFAULT_BACKEND = st.secrets.get("backend_url", "http://localhost:8080")

st.title("🎙️ Voice → AI → Gantt (Scooter Wheels)")
with st.sidebar:
    st.header("Settings")
    backend_url = st.text_input("Backend URL", value=DEFAULT_BACKEND)
    st.markdown("Backend must expose **/plan** and **/voice-intent**")

# ---- Data helpers
@st.cache_data(show_spinner=False)
def fetch_plan(backend: str):
    r = requests.get(f"{backend}/plan", timeout=30)
    r.raise_for_status()
    return r.json()

def gantt(plan):
    df = pd.DataFrame(plan["tasks"])
    df2 = df.copy()
    df2["Start"] = pd.to_datetime(df2["start"])
    df2["Finish"] = pd.to_datetime(df2["end"])
    fig = px.timeline(df2, x_start="Start", x_end="Finish", y="name",
                      hover_name="name", title="Scooter Wheels Plan")
    fig.update_yaxes(autorange="reversed")
    st.plotly_chart(fig, use_container_width=True)

# ---- Initial load
try:
    plan = fetch_plan(backend_url)
except Exception as e:
    st.error(f"Could not fetch plan from backend {backend_url}. {e}")
    st.stop()

gantt(plan)

# ---- Voice upload / call backend
st.subheader("Record a command")
audio = st.audio_input("Push-to-talk (hold to record, release to stop)")

cols = st.columns([1,1])
with cols[0]:
    do_send = st.button("Send to AI", type="primary", disabled=audio is None)
with cols[1]:
    do_reload = st.button("Reload plan")

if do_send:
    if audio is None:
        st.warning("Record something first.")
    else:
        files = {"audio": ("command.webm", audio.read(), "audio/webm")}
        with st.status("Transcribing and parsing…", expanded=True) as status:
            try:
                r = requests.post(f"{backend_url}/voice-intent", files=files, timeout=90)
                r.raise_for_status()
                data = r.json()

                st.write("**Transcript:**", data.get("transcript"))
                st.write("**Intent:**")
                st.json(data.get("intent"))
                st.write("**Diff:**")
                st.json(data.get("diff"))

                # Re-fetch authoritative plan from backend after apply
                plan = fetch_plan(backend_url)
                gantt(plan)
                status.update(label="Done", state="complete")
            except requests.RequestException as e:
                try:
                    st.error(r.json())
                except Exception:
                    st.error(str(e))
                status.update(label="Error", state="error")

if do_reload:
    plan = fetch_plan(backend_url)
    gantt(plan)

st.caption("Examples: “move W1 Truing forward 1 day”, “extend W2 Spoking 2 days”, “move milestone Ship to Customer to 2025-08-28”, “shift phase Spoking backward 1 day”.")
