
import type { Request, Response } from "express";
import multer from "multer";
import { openai } from "../lib/openai.js";
import { z } from "zod";
import { intentSchema } from "../lib/intent-schema.js";
import { applyIntent, loadPlan, savePlan } from "../lib/plan.js";
import type { PlanDiff, Intent } from "../types.js";

const upload = multer({ storage: multer.memoryStorage(), limits: { fileSize: 20 * 1024 * 1024 } });

const toolSchema = {
  name: "apply_planning_action",
  description: "Return a structured planning action based on the user's natural language command.",
  parameters: {
    type: "object",
    properties: {
      action: { type: "string", enum: ["shift_task_dates","extend_task","create_task","move_milestone","shift_phase"] },
      target: { type: "string", description: "Task or phase name", nullable: true },
      delta_days: { type: "integer", nullable: true },
      mode: { type: "string", enum: ["forward","backward"], nullable: true },
      name: { type: "string", nullable: true },
      start: { type: "string", nullable: true },
      end: { type: "string", nullable: true },
      dependsOn: { type: "array", items: { type: "string" }, nullable: true },
      assignee: { type: "string", nullable: true },
      to_date: { type: "string", nullable: true }
    },
    required: ["action"]
  }
} as const;

export const voiceIntentRoute = [
  upload.single("audio"),
  async (req: Request, res: Response) => {
    try {
      const audio = req.file;
      if (!audio) return res.status(400).json({ error: "No audio uploaded" });

      // 1) Transcribe (Whisper or GPT-4o Transcribe if env toggled)
      const use4o = String(process.env.USE_GPT4O_TRANSCRIBE).toLowerCase() === "true";
      const transcription = await openai.audio.transcriptions.create({
        file: new File([audio.buffer], audio.originalname || "command.webm", { type: audio.mimetype }),
        // If you prefer GPT‑4o Transcribe, set model to "gpt-4o-transcribe".
        model: use4o ? "gpt-4o-transcribe" : "whisper-1"
      });

      const transcript = transcription.text?.trim() || "";

      // 2) Get current plan context (lightweight)
      const plan = await loadPlan();
      const taskNames = plan.tasks.map(t => t.name);

      // 3) LLM → structured intent via tool/function calling (Responses API)
      const system = [
        "You are a strict planning intent parser.",
        "Output ONLY by calling the tool with a valid action and fields per the schema.",
        "If the user mentions a task not in taskNames, still produce best guess."
      ].join(" ");

      const userPrompt = [
        `User said: "${transcript}"`,
        `Task names: ${JSON.stringify(taskNames)}`
      ].join("\n");

      const resp = await openai.responses.create({
        model: "gpt-4.1-mini",
        messages: [
          { role: "system", content: system },
          { role: "user", content: userPrompt }
        ],
        tools: [{ type: "function", function: toolSchema }],
        tool_choice: "auto",
      });

      // Extract tool call arguments
      const toolCalls = resp.output?.filter((x: any) => x.type === "tool_call") ?? [];
      if (!toolCalls.length) throw new Error("No tool call returned by LLM");

      const toolArgs = toolCalls[0].function.arguments as unknown;
      const parsed = intentSchema.safeParse(toolArgs);
      if (!parsed.success) {
        return res.status(400).json({ error: "Intent validation failed", details: parsed.error.format(), transcript });
      }
      const intent = parsed.data as Intent;

      // 4) Compute & apply diff
      let diff: PlanDiff;
      try {
        diff = applyIntent(plan, intent);
      } catch (e: any) {
        return res.status(422).json({ transcript, intent, error: e.message });
      }

      await savePlan(plan);

      return res.json({
        transcript,
        intent,
        diff,
        updatedPlan: plan
      });
    } catch (err: any) {
      console.error(err);
      return res.status(500).json({ error: err.message ?? "Server error" });
    }
  }
];
