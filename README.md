# Voice → AI → Gantt (Whisper + LLM)

This demo replaces typing with a mic button: record → transcribe with Whisper → parse intent with the OpenAI Responses API → validate and apply to a plan, updating a Gantt chart (Streamlit).

## Prereqs
- Node 18+
- Python 3.10+
- OpenAI API key

## 1) Backend

```bash
cd backend
cp .env.example .env
# put your OPENAI_API_KEY in .env
npm i
npm run dev

