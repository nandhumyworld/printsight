import { useState } from "react";

export type DateRange = { start: Date; end: Date };

interface Props {
  value: DateRange;
  onChange: (r: DateRange) => void;
}

const PRESETS: [string, number][] = [
  ["Today", 1], ["7d", 7], ["30d", 30], ["90d", 90], ["1y", 365],
];

function toInput(d: Date): string {
  return d.toISOString().slice(0, 10);
}

export function DateRangePicker({ value, onChange }: Props) {
  const [open, setOpen] = useState(false);

  function applyPreset(days: number) {
    const end = new Date();
    const start = new Date();
    start.setDate(end.getDate() - days);
    onChange({ start, end });
    setOpen(false);
  }

  return (
    <div className="relative flex items-center gap-2">
      <div className="flex gap-1 rounded-md border bg-card p-1">
        {PRESETS.map(([label, d]) => (
          <button
            key={label}
            onClick={() => applyPreset(d)}
            className="rounded px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
          >
            {label}
          </button>
        ))}
      </div>
      <button
        onClick={() => setOpen(o => !o)}
        className="rounded-md border bg-card px-3 py-1.5 text-sm hover:bg-muted transition-colors"
      >
        {toInput(value.start)} — {toInput(value.end)}
      </button>
      {open && (
        <div className="absolute top-10 right-0 z-20 flex gap-2 rounded-md border bg-card p-3 shadow-lg">
          <div className="flex flex-col gap-1">
            <label className="text-xs text-muted-foreground">From</label>
            <input
              type="date"
              value={toInput(value.start)}
              onChange={e => onChange({ ...value, start: new Date(e.target.value) })}
              className="rounded border px-2 py-1 text-sm"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs text-muted-foreground">To</label>
            <input
              type="date"
              value={toInput(value.end)}
              onChange={e => onChange({ ...value, end: new Date(e.target.value) })}
              className="rounded border px-2 py-1 text-sm"
            />
          </div>
          <div className="flex items-end">
            <button
              onClick={() => setOpen(false)}
              className="rounded bg-primary px-3 py-1.5 text-sm text-primary-foreground"
            >
              Apply
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
