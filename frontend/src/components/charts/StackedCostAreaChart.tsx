import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend } from "recharts";
import { colorForToner } from "@/lib/tonerPalette";

interface Row { bucket: string; [key: string]: number | string }
interface Props { data: Row[] }

export function StackedCostAreaChart({ data }: Props) {
  const series = new Set<string>();
  data.forEach(r => Object.keys(r).forEach(k => { if (k !== "bucket") series.add(k); }));
  const keys = Array.from(series);

  return (
    <ResponsiveContainer width="100%" height={320}>
      <AreaChart data={data} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
        <defs>
          {keys.map(k => {
            const c = colorForToner(k);
            return (
              <linearGradient key={k} id={`grad-${k}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={c} stopOpacity={0.9} />
                <stop offset="100%" stopColor={c} stopOpacity={0.35} />
              </linearGradient>
            );
          })}
        </defs>
        <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
        <XAxis dataKey="bucket" tick={{ fontSize: 11 }} />
        <YAxis tick={{ fontSize: 11 }} tickFormatter={v => `₹${v}`} />
        <Tooltip formatter={(v: number) => `₹${v.toFixed(2)}`} />
        <Legend />
        {keys.map(k => (
          <Area
            key={k}
            type="monotone"
            dataKey={k}
            stackId="1"
            stroke={colorForToner(k)}
            fill={`url(#grad-${k})`}
            strokeWidth={1.5}
          />
        ))}
      </AreaChart>
    </ResponsiveContainer>
  );
}
