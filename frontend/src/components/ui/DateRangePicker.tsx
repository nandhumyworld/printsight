import { useEffect, useRef, useState } from "react";
import {
  addMonths, eachDayOfInterval, endOfDay, endOfMonth, endOfWeek, format,
  isAfter, isBefore, isSameDay, isSameMonth, startOfDay, startOfMonth,
  startOfWeek, subDays, subMonths,
} from "date-fns";
import { CalendarDays, ChevronLeft, ChevronRight } from "lucide-react";

export type DateRange = { start: Date; end: Date };

interface Props {
  value: DateRange;
  onChange: (r: DateRange) => void;
  /** Show a spinner in the trigger while dependent queries are in flight. */
  isLoading?: boolean;
}

const PRESETS: [string, number][] = [
  ["7d", 7], ["30d", 30], ["90d", 90], ["1y", 365],
];

const WEEKDAYS = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"];

export function DateRangePicker({ value, onChange, isLoading = false }: Props) {
  const [open, setOpen] = useState(false);
  const [month, setMonth] = useState(() => startOfMonth(value.end));
  // Set on the first click; the range is only committed on the second.
  const [pendingStart, setPendingStart] = useState<Date | null>(null);
  const [hovered, setHovered] = useState<Date | null>(null);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function onDocClick(e: MouseEvent) {
      if (!rootRef.current?.contains(e.target as Node)) {
        setOpen(false);
        setPendingStart(null);
      }
    }
    function onEsc(e: KeyboardEvent) {
      if (e.key === "Escape") { setOpen(false); setPendingStart(null); }
    }
    document.addEventListener("mousedown", onDocClick);
    document.addEventListener("keydown", onEsc);
    return () => {
      document.removeEventListener("mousedown", onDocClick);
      document.removeEventListener("keydown", onEsc);
    };
  }, [open]);

  function commit(start: Date, end: Date) {
    onChange({ start: startOfDay(start), end: endOfDay(end) });
    setOpen(false);
    setPendingStart(null);
    setHovered(null);
  }

  function applyPreset(days: number) {
    commit(subDays(new Date(), days), new Date());
  }

  function onDayClick(day: Date) {
    if (!pendingStart) {
      setPendingStart(day);
      return;
    }
    // Second click completes the range; picking backwards swaps rather than erroring.
    if (isBefore(day, pendingStart)) commit(day, pendingStart);
    else commit(pendingStart, day);
  }

  // The range to paint: committed value, or the live preview while picking.
  const previewEnd = pendingStart ? hovered : null;
  const paintStart = pendingStart
    ? (previewEnd && isBefore(previewEnd, pendingStart) ? previewEnd : pendingStart)
    : value.start;
  const paintEnd = pendingStart
    ? (previewEnd && isBefore(previewEnd, pendingStart) ? pendingStart : previewEnd ?? pendingStart)
    : value.end;

  const days = eachDayOfInterval({
    start: startOfWeek(startOfMonth(month), { weekStartsOn: 1 }),
    end: endOfWeek(endOfMonth(month), { weekStartsOn: 1 }),
  });

  const today = new Date();

  return (
    <div ref={rootRef} className="relative flex items-center gap-2">
      <div className="hidden sm:flex gap-1 rounded-md border bg-card p-1">
        {PRESETS.map(([label, d]) => (
          <button
            key={label}
            onClick={() => applyPreset(d)}
            className="rounded px-2 py-1 text-xs text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
          >
            {label}
          </button>
        ))}
      </div>

      <button
        onClick={() => { setOpen(o => !o); setPendingStart(null); setMonth(startOfMonth(value.end)); }}
        aria-label="Select date range"
        className="flex items-center gap-2 rounded-md border bg-card px-3 py-1.5 text-sm hover:bg-muted transition-colors"
      >
        {isLoading
          ? <span className="h-4 w-4 shrink-0 animate-spin rounded-full border-2 border-muted-foreground/30 border-t-primary" />
          : <CalendarDays className="h-4 w-4 shrink-0 text-muted-foreground" />}
        <span>{format(value.start, "d MMM yyyy")} — {format(value.end, "d MMM yyyy")}</span>
      </button>

      {open && (
        <div className="absolute top-11 right-0 z-30 w-[19rem] rounded-lg border bg-card p-3 shadow-xl">
          <div className="mb-2 flex items-center justify-between">
            <button
              onClick={() => setMonth(m => subMonths(m, 1))}
              aria-label="Previous month"
              className="rounded p-1 hover:bg-muted transition-colors"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <span className="text-sm font-semibold">{format(month, "MMMM yyyy")}</span>
            <button
              onClick={() => setMonth(m => addMonths(m, 1))}
              aria-label="Next month"
              disabled={isSameMonth(month, today)}
              className="rounded p-1 hover:bg-muted disabled:opacity-30 disabled:hover:bg-transparent transition-colors"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>

          <div className="mb-1 grid grid-cols-7 gap-0.5">
            {WEEKDAYS.map(d => (
              <div key={d} className="py-1 text-center text-[0.65rem] font-medium text-muted-foreground">{d}</div>
            ))}
          </div>

          <div className="grid grid-cols-7 gap-0.5" onMouseLeave={() => setHovered(null)}>
            {days.map(day => {
              const outside = !isSameMonth(day, month);
              const future = isAfter(startOfDay(day), startOfDay(today));
              const isStart = isSameDay(day, paintStart);
              const isEnd = isSameDay(day, paintEnd);
              const inRange = isAfter(day, paintStart) && isBefore(day, paintEnd);

              return (
                <button
                  key={day.toISOString()}
                  disabled={future}
                  onClick={() => onDayClick(day)}
                  onMouseEnter={() => setHovered(day)}
                  className={[
                    "h-8 rounded text-xs transition-colors",
                    future ? "cursor-not-allowed opacity-25" : "hover:bg-muted",
                    outside && !future ? "text-muted-foreground/50" : "",
                    inRange ? "bg-primary/15 text-foreground" : "",
                    isStart || isEnd ? "bg-primary text-primary-foreground font-semibold hover:bg-primary" : "",
                  ].join(" ")}
                >
                  {format(day, "d")}
                </button>
              );
            })}
          </div>

          <p className="mt-2 text-center text-[0.7rem] text-muted-foreground">
            {pendingStart ? "Now pick the end date" : "Pick a start date"}
          </p>
        </div>
      )}
    </div>
  );
}
