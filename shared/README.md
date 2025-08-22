
# Shared data
- `sample_plan.json` is the working plan the backend mutates.
- Streamlit and the backend both read/write this for demo simplicity.
- In production, use a database or service to store plans and apply diffs transactionally.
