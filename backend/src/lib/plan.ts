import { addDays, parseISO, formatISO } from "date-fns";
import type { Plan, Task, PlanDiff, Intent } from "../types.js";
import fs from "node:fs/promises";
import path from "node:path";
import { defaultPlan } from "./default-plan.js";

const planPath = () => path.resolve(process.cwd(), "../shared/sample_plan.json");

function shiftDates(task: Task, delta: number): Task {
  const start = formatISO(addDays(parseISO(task.start), delta), { representation: "date" });
  const end   = formatISO(addDays(parseISO(task.end),   delta), { representation: "date" });
  return { ...task, start, end };
}

export async function ensurePlanOnDisk(): Promise<Plan> {
  const p = planPath();
  try {
    const raw = await fs.readFile(p, "utf8");
    return JSON.parse(raw);
  } catch {
    // If the shared file isn't there, seed with the Scooter Wheels dataset.
    await fs.mkdir(path.dirname(p), { recursive: true });
    await fs.writeFile(p, JSON.stringify(defaultPlan, null, 2), "utf8");
    return defaultPlan as Plan;
  }
}

export async function loadPlan(): Promise<Plan> {
  return ensurePlanOnDisk();
}

export async function savePlan(plan: Plan): Promise<void> {
  const p = planPath();
  await fs.writeFile(p, JSON.stringify(plan, null, 2), "utf8");
}

export function applyIntent(plan: Plan, intent: Intent): PlanDiff {
  const changes: PlanDiff["changes"] = [];
  const tasks = [...plan.tasks];

  const findByName = (name: string) =>
    tasks.find(t => t.name.toLowerCase() === name.toLowerCase());

  switch (intent.action) {
    case "shift_task_dates": {
      const t = findByName(intent.target);
      if (!t) throw new Error(`Task not found: ${intent.target}`);
      const delta = intent.mode === "forward" ? intent.delta_days : -intent.delta_days;
      const after = shiftDates(t, delta);
      changes.push({ type: "update", taskId: t.id, before: t, after });
      break;
    }
    case "extend_task": {
      const t = findByName(intent.target);
      if (!t) throw new Error(`Task not found: ${intent.target}`);
      const after: Task = { ...t, end: formatISO(addDays(parseISO(t.end), intent.delta_days), { representation: "date" }) };
      changes.push({ type: "update", taskId: t.id, before: t, after });
      break;
    }
    case "create_task": {
      const id = `t_${Math.random().toString(36).slice(2, 9)}`;
      const task: Task = {
        id,
        name: intent.name,
        start: intent.start,
        end: intent.end,
        dependsOn: intent.dependsOn,
        assignee: intent.assignee
      };
      changes.push({ type: "create", task });
      break;
    }
    case "move_milestone": {
      const t = findByName(intent.target);
      if (!t) throw new Error(`Milestone not found: ${intent.target}`);
      const durationDays =
        (parseISO(t.end).getTime() - parseISO(t.start).getTime()) / (1000 * 60 * 60 * 24);
      const after: Task = {
        ...t,
        start: intent.to_date,
        end: formatISO(addDays(parseISO(intent.to_date), Math.max(0, durationDays)), { representation: "date" })
      };
      changes.push({ type: "update", taskId: t.id, before: t, after });
      break;
    }
    case "shift_phase": {
      const lowered = intent.target.toLowerCase();
      const phaseTasks = tasks.filter(t => t.name.toLowerCase().includes(lowered));
      if (!phaseTasks.length) throw new Error(`No tasks matched phase: ${intent.target}`);
      for (const t of phaseTasks) {
        const after = shiftDates(t, intent.delta_days);
        changes.push({ type: "update", taskId: t.id, before: t, after });
      }
      break;
    }
  }

  const nextTasks = tasks.map(t => {
    const upd = changes.find(c => c.type === "update" && c.taskId === t.id) as any;
    return upd ? upd.after : t;
  });
  for (const c of changes) if (c.type === "create") nextTasks.push(c.task);

  return { changes };
}
