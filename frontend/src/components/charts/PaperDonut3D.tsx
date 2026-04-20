import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from "recharts";
import { PAPER_COLORS } from "@/lib/tonerPalette";

interface Row { paper_type: string; cost: number; pages: number }
interface Props { data: Row[] }

export function PaperDonut3D({ data }: Props) {
  const total = data.reduce((s, d) => s + d.cost, 0);

  return (
    <ResponsiveContainer width="100%" height={320}>
      <PieChart>
        <defs>
          {data.map((_, i) => {
            const c = PAPER_COLORS[i % PAPER_COLORS.length];
            return (
              <radialGradient key={i} id={`pie-${i}`} cx="50%" cy="50%" r="65%">
                <stop offset="0%" stopColor={c} stopOpacity={1} />
                <stop offset="100%" stopColor={c} stopOpacity={0.55} />
              </radialGradient>
            );
          })}
          <filter id="donut-shadow" x="-20%" y="-20%" width="140%" height="140%">
            <feDropShadow dx="0" dy="4" stdDeviation="6" floodOpacity="0.35" />
          </filter>
        </defs>
        <Pie
          data={data}
          dataKey="cost"
          nameKey="paper_type"
          innerRadius={70}
          outerRadius={120}
          paddingAngle={3}
          stroke="#fff"
          strokeWidth={2}
          filter="url(#donut-shadow)"
          label={({ paper_type, cost }) =>
            total > 0 ? `${paper_type}: ${((cost / total) * 100).toFixed(0)}%` : paper_type
          }
        >
          {data.map((_, i) => <Cell key={i} fill={`url(#pie-${i})`} />)}
        </Pie>
        <Tooltip formatter={(v: number) => `₹${v.toFixed(2)}`} />
        <Legend verticalAlign="bottom" />
      </PieChart>
    </ResponsiveContainer>
  );
}
