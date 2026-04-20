import { colorForToner } from "@/lib/tonerPalette";

interface Props {
  color: string;
  pages_since_replacement: number;
  pct_yield_consumed: number;
  spend_to_date: number;
  est_remaining_pages: number;
}

export function TonerConsumptionCard(p: Props) {
  const c = colorForToner(p.color);
  const warn = p.pct_yield_consumed > 80;
  return (
    <div className="rounded-xl border bg-card p-4 shadow-sm">
      <div className="mb-2 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span
            className="inline-block h-4 w-4 rounded-full border border-border"
            style={{ background: c }}
          />
          <span className="font-medium uppercase text-sm">{p.color}</span>
        </div>
        {warn && (
          <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs text-amber-700 font-medium">
            Low
          </span>
        )}
      </div>
      <div className="mb-3 h-2 w-full rounded-full bg-muted overflow-hidden">
        <div
          className="h-2 rounded-full transition-all"
          style={{ width: `${Math.min(100, p.pct_yield_consumed)}%`, background: c }}
        />
      </div>
      <div className="grid grid-cols-2 gap-2 text-xs text-muted-foreground">
        <div>
          <div className="text-foreground font-semibold">{p.pages_since_replacement.toLocaleString()}</div>
          pages used
        </div>
        <div>
          <div className="text-foreground font-semibold">{p.est_remaining_pages.toLocaleString()}</div>
          est. remaining
        </div>
        <div>
          <div className="text-foreground font-semibold">₹{p.spend_to_date.toFixed(2)}</div>
          spent
        </div>
        <div>
          <div className="text-foreground font-semibold">{p.pct_yield_consumed.toFixed(1)}%</div>
          of rated yield
        </div>
      </div>
    </div>
  );
}
