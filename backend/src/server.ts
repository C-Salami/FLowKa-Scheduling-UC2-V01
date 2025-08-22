import "dotenv/config";
import express from "express";
import cors from "cors";
import { voiceIntentRoute } from "./routes/voice-intent.js";

const app = express();
app.use(cors());
app.get("/health", (_req, res) => res.json({ ok: true }));

app.post("/voice-intent", ...voiceIntentRoute);

const port = Number(process.env.PORT || 8080);
app.listen(port, () => console.log(`Voice intent server listening on :${port}`));

