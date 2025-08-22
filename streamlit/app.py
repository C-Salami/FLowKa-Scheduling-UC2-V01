# streamlit_app.py
import io
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any

import pandas as pd
import plotly.express as px
import streamlit as st

# ---- OpenAI
# Uses the official OpenAI Python SDK (1.x).
# Docs: Audio Transcriptions (Whisper) and Responses API tool calling.
# Make sure you `pip install openai`.
from openai import OpenAI

# ---------- UI setup ----------
st.set_page_config(page_title="🎙️ Voice → Gantt (Scooter Wheels)", layout="wide")
st.title("🎙️ Voice → AI → Gantt (Scooter Wheels)")

with st.sidebar:
    st.header("Settings")
    st.markdown(
        "This one‑box app calls **OpenAI Whisper** for ASR and the **Responses API** "
        "for intent parsing — no separate backend."
    )
    # KEY: define your API key in .streamlit/secrets.toml as OPENAI_API_KEY="sk-..."
    api_key = st.secrets.get("OPENAI_API_KEY", "")
    if not api_key:
        st.warning("Set OPENAI_API_KEY in .streamlit/secrets.toml to enable transcription/LLM.")
    model_transcribe = st.selectbox("ASR model", ["whisper-1"], index=0)
    model_llm = st.selectbox("LLM model", ["gpt-4.1-mini", "gpt-4o-mini", "gpt-4.1"], index=0)

# ---------- OpenAI client ----------
@st.cache_resource(show_spinner=False)
def get_client(key: str):
    return OpenAI(api_key=key) if key else None

client = get_client(api_key)

# ---------- Scooter Wheels default plan ----------
DEFAULT_PLAN = {
    "tasks": [
        { "id": "w1_cut",   "name": "W1 Cutting",    "start": "2025-08-18", "end": "2025-08-18" },
        { "id": "w1_spoke", "name": "W1 Spoking",    "start": "2025-08-19", "end": "2025-08-20", "dependsOn": ["w1_cut"] },
        { "id": "w1_true",  "name": "W1 Truing",     "start": "2025-08-21", "end": "2025-08-21", "dependsOn": ["w1_spoke"] },
        { "id": "w1_qc",    "name": "W1 QC",         "start": "2025-08-22", "end": "2025-08-22", "dependsOn": ["w1_true"] },

        { "id": "w2_cut",   "name": "W2 Cutting",    "start": "2025-08-18", "end": "2025-08-18" },
        { "id": "w2_spoke", "name": "W2 Spoking",    "start": "2025-08-19", "end": "2025-08-20", "dependsOn": ["w2_cut"] },
        { "id": "w2_true",  "name": "W2 Truing",     "start": "2025-08-21", "end": "2025-08-21", "dependsOn": ["w2_spoke"] },
        { "id": "w2_qc",    "name": "W2 QC",         "start": "2025-08-22", "end": "2025-08-22", "dependsOn": ["w2_true"] },

        { "id": "assy_pair","name": "Wheel Pair Assembly", "start": "2025-08-25", "end": "2025-08-25", "dependsOn": ["w1_qc","w2_qc"] },
        { "id": "pack",     "name": "Packaging",           "start": "2025-08-26", "end": "2025-08-26", "dependsOn": ["assy_pair"] },
        { "id": "ship",     "name": "Ship to Customer",    "start": "2025-08-27", "end": "2025-08-27", "dependsOn": ["pack"] }
    ]
}

if "plan" not in st.session_state:
    st.session_state.plan = json.loads(json.dumps(DEFAULT_PLAN))  # deep copy

# ---------- Helpers for date math ----------
from datetime import date
def to_date(s: str) -> date:
    return datetime.fromisoformat(s).date()

def fmt_date(d: date) -> str:
    return d.isoformat()

def add_days_str(iso: str, n: int) -> str:
    return fmt_date(to_date(iso) + timedelta(days=n))

# ---------- Apply intent to plan ----------
def shift_task_dates(task: Dict[str, Any], delta_days: int) -> Dict[str, Any]:
    return {
        **task,
        "start": add_days_str(task["start"], delta_days),
        "end": add_days_str(task["end"], delta_days),
    }

def apply_intent(plan: Dict[str, Any], intent: Dict[str, Any]) -> Dict[str, Any]:
    """Returns a diff dict with changes; mutates plan in session for demo simplicity."""
    changes = []
    tasks = plan["tasks"]

    def find_by_name(name: str):
        lname = name.strip().lower()
        for t in tasks:
            if t["name"].lower() == lname:
                return t
        return None

    action = intent.get("action")
    if action == "shift_task_dates":
        target = find_by_name(intent["target"])
        if not target:
            raise ValueError(f"Task not found: {intent['target']}")
        delta = intent["delta_days"] if intent["mode"] == "forward" else -intent["delta_days"]
        before = json.loads(json.dumps(target))
        after = shift_task_dates(target, delta)
        # mutate
        target.update(after)
        changes.append({"type": "update", "taskId": target["id"], "before": before, "after": after})

    elif action == "extend_task":
        target = find_by_name(intent["target"])
        if not target:
            raise ValueError(f"Task not found: {intent['target']}")
        before = json.loads(json.dumps(target))
        target["end"] = add_days_str(target["end"], int(intent["delta_days"]))
        after = json.loads(json.dumps(target))
        changes.append({"type": "update", "taskId": target["id"], "before": before, "after": after})

    elif action == "create_task":
        new_task = {
            "id": f"t_{len(tasks)+1}",
            "name": intent["name"],
            "start": intent["start"],
            "end": intent["end"],
            "dependsOn": intent.get("dependsOn"),
            "assignee": intent.get("assignee"),
        }
        tasks.append(new_task)
        changes.append({"type": "create", "task": new_task})

    elif action == "move_milestone":
        target = find_by_name(intent["target"])
        if not target:
            raise ValueError(f"Milestone not found: {intent['target']}")
        # keep duration constant
        dur = to_date(target["end"]) - to_date(target["start"])
        before = json.loads(json.dumps(target))
        target["start"] = intent["to_date"]
        target["end"] = fmt_date(to_date(intent["to_date"]) + dur)
        after = json.loads(json.dumps(target))
        changes.append({"type": "update", "taskId": target["id"], "before": before, "after": after})

    elif action == "shift_phase":
        token = intent["target"].strip().lower()
        affected = [t for t in tasks if token in t["name"].lower()]
        if not affected:
            raise ValueError(f"No tasks matched phase: {intent['target']}")
        for t in affected:
            before = json.loads(json.dumps(t))
            after = shift_task_dates(t, int(intent["delta_days"]))
            t.update(after)
            changes.append({"type": "update", "taskId": t["id"], "before": before, "after": after})
    else:
        raise ValueError(f"Unsupported action: {action}")

    return {"changes": changes}

# ---------- Plot Gantt ----------
def draw_gantt(plan: Dict[str, Any]):
    df = pd.DataFrame(plan["tasks"])
    df2 = df.copy()
    df2["Start"] = pd.to_datetime(df2["start"])
    df2["Finish"] = pd.to_datetime(df2["end"])
    fig = px.timeline(df2, x_start="Start", x_end="Finish", y="name",
                      hover_name="name", title="Scooter Wheels Plan")
    fig.update_yaxes(autorange="reversed")
    st.plotly_chart(fig, use_container_width=True)

draw_gantt(st.session_state.plan)

# ---------- Voice capture ----------
st.subheader("Record a command")
audio = st.audio_input("Push-to-talk (hold to record, release to stop)")

# ---------- Tool (function) schema for LLM ----------
TOOL_SCHEMA = {
    "name": "apply_planning_action",
    "description": "Return a structured planning action based on the user's natural language command.",
    "parameters": {
        "type": "object",
        "properties": {
            "action": { "type": "string", "enum": ["shift_task_dates","extend_task","create_task","move_milestone","shift_phase"] },
            "target": { "type": "string" },
            "delta_days": { "type": "integer" },
            "mode": { "type": "string", "enum": ["forward","backward"] },
            "name": { "type": "string" },
            "start": { "type": "string" },
            "end": { "type": "string" },
            "dependsOn": { "type": "array", "items": { "type": "string" } },
            "assignee": { "type": "string" },
            "to_date": { "type": "string" }
        },
        "required": ["action"]
    }
}

SYSTEM_MSG = (
    "You are a strict planning intent parser. "
    "Given a transcript and a list of task names, return a single, valid tool call "
    "with fields conforming to the provided JSON schema. Do not use free-form text."
)

# ---------- Buttons ----------
col1, col2, col3 = st.columns([1,1,1])
send_clicked = col1.button("Send to AI", type="primary", disabled=audio is None or not client)
reset_clicked = col2.button("Reset plan to defaults")
show_tasks = col3.checkbox("Show task names", value=False)

if show_tasks:
    st.write(sorted([t["name"] for t in st.session_state.plan["tasks"]]))

if reset_clicked:
    st.session_state.plan = json.loads(json.dumps(DEFAULT_PLAN))
    draw_gantt(st.session_state.plan)
    st.success("Plan reset.")

# ---------- Core flow ----------
if send_clicked:
    if not client:
        st.error("OpenAI API key missing. Add OPENAI_API_KEY to .streamlit/secrets.toml.")
    elif audio is None:
        st.warning("Record something first.")
    else:
        with st.status("Transcribing and parsing…", expanded=True) as status:
            try:
                # 1) Transcribe with Whisper
                audio_bytes = audio.read()
                fname = "command.webm"
                st.write("Uploading audio for transcription…")
                transcript_resp = client.audio.transcriptions.create(
                    model=model_transcribe,
                    file=("command.webm", io.BytesIO(audio_bytes), "audio/webm"),
                )
                transcript = (transcript_resp.text or "").strip()
                st.write("**Transcript:**", transcript if transcript else "(empty)")

                # 2) LLM → structured intent via tool calling
                task_names = [t["name"] for t in st.session_state.plan["tasks"]]
                user_prompt = f'User said: "{transcript}"\nTask names: {json.dumps(task_names)}'

                st.write("Parsing intent…")
                resp = client.responses.create(
                    model=model_llm,
                    messages=[
                        {"role": "system", "content": SYSTEM_MSG},
                        {"role": "user", "content": user_prompt},
                    ],
                    tools=[{"type": "function", "function": TOOL_SCHEMA}],
                    tool_choice="auto",
                )

                # Responses API returns a list of content blocks. Find the tool call.
                tool_calls = [b for b in (resp.output or []) if b.type == "tool_call"]
                if not tool_calls:
                    raise RuntimeError("LLM did not return a tool call.")

                tool_args = tool_calls[0].function.arguments
                # tool_args is already a dict in Python SDK 1.x; if string, json.loads it
                if isinstance(tool_args, str):
                    parsed_intent = json.loads(tool_args)
                else:
                    parsed_intent = tool_args

                st.write("**Intent:**")
                st.json(parsed_intent)

                # 3) Apply intent to plan
                st.write("Applying changes…")
                diff = apply_intent(st.session_state.plan, parsed_intent)
                st.write("**Diff:**")
                st.json(diff)

                # 4) Redraw Gantt
                draw_gantt(st.session_state.plan)
                status.update(label="Done", state="complete")

            except Exception as e:
                st.error(f"{type(e).__name__}: {e}")
                status.update(label="Error", state="error")

st.caption(
    "Try: “move W1 Truing forward 1 day”, “extend W2 Spoking 2 days”, "
    "“shift phase Spoking backward 1 day”, “move milestone Ship to Customer to 2025-08-28”, "
    "“create task Final Polish from 2025-08-26 to 2025-08-27”."
)
