import { z } from "zod";

export const intentSchema = z.discriminatedUnion("action", [
  z.object({
    action: z.literal("shift_task_dates"),
    target: z.string(),
    delta_days: z.number().int(),
    mode: z.enum(["forward", "backward"])
  }),
  z.object({
    action: z.literal("extend_task"),
    target: z.string(),
    delta_days: z.number().int()
  }),
  z.object({
    action: z.literal("create_task"),
    name: z.string(),
    start: z.string(),
    end: z.string(),
    dependsOn: z.array(z.string()).optional(),
    assignee: z.string().optional()
  }),
  z.object({
    action: z.literal("move_milestone"),
    target: z.string(),
    to_date: z.string()
  }),
  z.object({
    action: z.literal("shift_phase"),
    target: z.string(),
    delta_days: z.number().int()
  })
]);

export type IntentSchema = typeof intentSchema;

