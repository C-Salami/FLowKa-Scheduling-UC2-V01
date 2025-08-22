import io
import json
import time
import requests
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

st.set_page_config(page_title="Voice → Gantt", layout="wide")

BACKEND = st.secrets.get("backend_url", "http://localhost:8080")

st.title("🎙️ Voice → AI → Gantt")

with st.sidebar:
    st.header("Settings")
    backend_url = st.text_input("Backend URL", value=BACKEND)
    st.markdown("1) Start backend\n2) Click mic → speak a command\n3) Stop → Apply")

# Load plan from shared file (the backend persists it, but we mirror it)
def load_plan():
    with open("../shared/sample_plan.json", "r", encoding="utf-8") as f:
        return json.load(f)

def gantt(df):
    # plotly timeline expects start/end as datetimes
    df2 = df.copy()
    df2["Start"] = pd.to_datetime(df2["start"])
    df2["Finish"] = pd.to_datetime(df2["end"])
    fig = px.timeline(
        df2, x_start="Start", x_end="Finish",
        y="name", hover_name="name", title="Project Plan"
    )
    fig.update_yaxes(autorange="reversed")
    st.plotly_chart(fig, use_container_width=True)

plan = load_plan()
df = pd.DataFrame(plan["tasks"])
gantt(df)

st.subheader("Record a command")
audio = st.audio_input("Push-to-talk (hold to record, release to stop)", key="mic1")

col1, col2 = st.columns([1, 1])
with col1:
    if st.button("Send to AI", type="primary", disabled=audio is None):
        if audio is None:
            st.warning("Record something first.")
        else:
            # Streamlit gives a BytesIO
            audio_bytes = audio.read()
            files = {
                "audio": ("command.webm", audio_bytes, "audio/webm")
            }
            with st.status("Transcribing and parsing…", expanded=True) as status:
                try:
                    r = requests.post(f"{backend_url}/voice-intent", files=files, timeout=60)
                    r.raise_for_status()
                    data = r.json()

                    st.write("**Transcript:**", data.get("transcript"))
                    st.write("**Intent:**")
                    st.json(data.get("intent"))

                    st.write("**Diff:**")
                    st.json(data.get("diff"))

                    # Overwrite local plan display with updated plan
                    updated = data.get("updatedPlan")
                    if updated:
                        with open("../shared/sample_plan.json", "w", encoding="utf-8") as f:
                            json.dump(updated, f, indent=2)
                        st.success("Plan updated.")
                        df = pd.DataFrame(updated["tasks"])
                        gantt(df)
                    status.update(label="Done", state="complete")
                except requests.RequestException as e:
                    try:
                        err = r.json()
                    except Exception:
                        err = {"error": str(e)}
                    st.error(err)
                    status.update(label="Error", state="error")

with col2:
    if st.button("Reload plan"):
        plan = load_plan()
        df = pd.DataFrame(plan["tasks"])
        gantt(df)

st.caption("Tip: Try saying “move Design Review forward by two days” or “create task Beta QA from 2025-09-01 to 2025-09-03”.")

