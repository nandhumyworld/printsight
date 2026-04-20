import { colorForToner } from "@/lib/tonerPalette";

interface Job {
  job_id: string;
  job_name?: string | null;
  paper_type?: string | null;
  printed_pages: number;
  paper_cost: number;
  toner_cost: number;
  total_cost: number;
  breakdown: Record<string, number>;
  source: string | null;
  is_waste: boolean;
  recorded_at: string | null;
}

interface Props { job: Job | null; onClose: () => void }

export function JobDetailDrawer({ job, onClose }: Props) {
  if (!job) return null;

  const breakdownEntries = Object.entries(job.breakdown || {}).filter(([, v]) => v > 0);
  const maxVal = breakdownEntries.reduce((m, [, v]) => Math.max(m, v), 0);

  return (
    <div className="fixed inset-0 z-30 flex justify-end" onClick={onClose}>
      <div
        className="h-full w-full max-w-md overflow-y-auto bg-card p-6 shadow-xl border-l"
        onClick={e => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h3 className="text-lg font-bold">{job.job_name || job.job_id}</h3>
            {job.recorded_at && (
              <p className="text-xs text-muted-foreground">{new Date(job.recorded_at).toLocaleString()}</p>
            )}
          </div>
          <button
            onClick={onClose}
            className="text-2xl text-muted-foreground hover:text-foreground leading-none"
          >
            ×
          </button>
        </div>

        {job.is_waste && (
          <div className="mb-4 rounded-md bg-amber-50 px-3 py-2 text-xs text-amber-700 border border-amber-200">
            Waste / failed job
          </div>
        )}

        <div className="mb-4 grid grid-cols-3 gap-3 text-sm">
          <div className="rounded-lg border bg-muted/30 p-3 text-center">
            <div className="text-lg font-bold">₹{job.paper_cost.toFixed(2)}</div>
            <div className="text-xs text-muted-foreground">Paper</div>
          </div>
          <div className="rounded-lg border bg-muted/30 p-3 text-center">
            <div className="text-lg font-bold">₹{job.toner_cost.toFixed(2)}</div>
            <div className="text-xs text-muted-foreground">Toner</div>
          </div>
          <div className="rounded-lg border bg-primary/10 p-3 text-center">
            <div className="text-lg font-bold text-primary">₹{job.total_cost.toFixed(2)}</div>
            <div className="text-xs text-muted-foreground">Total</div>
          </div>
        </div>

        {job.paper_type && (
          <div className="mb-3 text-xs text-muted-foreground">
            Paper type: <span className="text-foreground">{job.paper_type}</span>
            {job.printed_pages > 0 && ` · ${job.printed_pages} pages`}
          </div>
        )}

        {breakdownEntries.length > 0 && (
          <div className="mt-4">
            <div className="mb-2 text-sm font-semibold">Per-color toner cost</div>
            <div className="space-y-2">
              {breakdownEntries.map(([k, v]) => (
                <div key={k} className="flex items-center gap-2">
                  <span
                    className="inline-block h-3 w-3 shrink-0 rounded-full border border-border"
                    style={{ background: colorForToner(k) }}
                  />
                  <span className="w-12 text-xs uppercase text-muted-foreground">{k}</span>
                  <div className="flex-1 h-2 rounded-full bg-muted overflow-hidden">
                    <div
                      className="h-2 rounded-full"
                      style={{
                        background: colorForToner(k),
                        width: maxVal > 0 ? `${(v / maxVal) * 100}%` : "0%",
                      }}
                    />
                  </div>
                  <span className="w-20 text-right text-xs tabular-nums">₹{v.toFixed(4)}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {job.source && (
          <div className="mt-4 text-xs text-muted-foreground">
            Coverage source: <span className="text-foreground">{job.source}</span>
          </div>
        )}
      </div>
    </div>
  );
}
