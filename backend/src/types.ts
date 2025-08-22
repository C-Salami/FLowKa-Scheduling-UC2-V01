export type Task = {
  id: string;
  name: string;
  start: string; // ISO date
  end: string;   // ISO date
  dependsOn?: string[]; // task ids
  assignee?: string;
};

export type Plan = { tasks: Task[] };

export type Intent =
  | {
      action: "shift_task_dates";
      target: string;           // task name
      delta_days: number;       // positive/negative
      mode: "forward" | "backward";
    }
  | {
      action: "extend_task";
      target: string;
      delta_days: number;       // extend duration
    }
  | {
      action: "create_task";
      name: string;
      start: string; // ISO
      end: string;   // ISO
      dependsOn?: string[];
      assignee?: string;
    }
  | {
      action: "move_milestone";
      target: string;
      to_date: string;          // ISO
    }
  | {
      action: "shift_phase";
      target: string;           // phase label or group
      delta_days: number;
    };

export type PlanDiff = {
  changes: Array<
    | { type: "update"; taskId: string; before: Task; after: Task }
    | { type: "create"; task: Task }
  >;
};

