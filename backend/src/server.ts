import "dotenv/config";
import express from "express";
import cors from "cors";
import { voiceIntentRoute } from "./routes/voice-intent.js";
import { ensurePlanOnDisk } from "./lib/plan.js";

const app = express();
app.use(cors());
app.get("/health", (_req, res) => res.json({ ok: true }));

// New: expose current plan so Streamlit doesn’t need to read files.
app.get("/plan", async (_req, res) => {
  const plan = await ensurePlanOnDisk();
  res.json(plan);
});

app.post("/voice-intent", ...voiceIntentRoute);

const port = Number(process.env.PORT || 8080);
app.listen(port, () => console.log(`Voice intent server listening on :${port}`));
