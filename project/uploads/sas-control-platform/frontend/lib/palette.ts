// Palette of scenario node types. The `type` values match the backend
// validator's NODE_TYPES set exactly, so a graph built here validates server
// side without translation.
export interface PaletteItem {
  type: string;
  label: string;
  group: "flow" | "action" | "logic" | "meta";
  color: string;
  defaultConfig?: Record<string, unknown>;
}

export const PALETTE: PaletteItem[] = [
  { type: "start", label: "Start", group: "flow", color: "var(--color-online)" },
  { type: "end", label: "End", group: "flow", color: "var(--color-offline)" },
  { type: "wait", label: "Wait", group: "flow", color: "var(--color-active)", defaultConfig: { seconds: 3 } },
  {
    type: "set_output_state",
    label: "Set Output State",
    group: "action",
    color: "var(--color-output)",
    defaultConfig: { enabled: true },
  },
  {
    type: "configure_parameters",
    label: "Configure",
    group: "action",
    color: "var(--color-output)",
    defaultConfig: { params: { isc_a: 8, imp_a: 7.3, voc_v: 100, vmp_v: 82 } },
  },
  {
    type: "apply_profile",
    label: "Apply Profile",
    group: "action",
    color: "var(--color-output)",
    defaultConfig: { profile: "Standard Panel A" },
  },
  { type: "read_measurement", label: "Read Measurement", group: "action", color: "var(--color-scenario)" },
  { type: "record_measurement", label: "Record Measurement", group: "action", color: "var(--color-scenario)" },
  {
    type: "send_command",
    label: "Send Command",
    group: "action",
    color: "var(--color-warning)",
    defaultConfig: { template_id: "read_measurements", params: {} },
  },
  { type: "safe_shutdown", label: "Safe Shutdown", group: "action", color: "var(--color-alarm)" },
  {
    type: "condition",
    label: "Condition",
    group: "logic",
    color: "var(--color-warning)",
    defaultConfig: { field: "power_w", op: ">=", value: 10 },
  },
  {
    type: "threshold_check",
    label: "Threshold Check",
    group: "logic",
    color: "var(--color-warning)",
    defaultConfig: { field: "power_w", op: ">=", value: 10 },
  },
  { type: "branch", label: "Branch", group: "logic", color: "var(--color-warning)" },
  {
    type: "repeat",
    label: "Repeat (bounded)",
    group: "logic",
    color: "var(--color-scenario)",
    defaultConfig: { max_iterations: 5 },
  },
  {
    type: "notification",
    label: "Notification",
    group: "meta",
    color: "var(--color-active)",
    defaultConfig: { message: "checkpoint reached" },
  },
  { type: "comment", label: "Comment", group: "meta", color: "var(--color-ink-faint)" },
];

export const PALETTE_BY_TYPE = Object.fromEntries(PALETTE.map((p) => [p.type, p]));
