import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";
import { colorForToner } from "@/lib/tonerPalette";

interface Props { data: { color: string; cost: number }[] }

export function TonerBreakdownBar({ data }: Props) {
  return (
    <ResponsiveContainer width="100%" height={Math.max(200, data.length * 40)}>
      <BarChart data={data} layout="vertical" margin={{ left: 32, right: 16 }}>
        <XAxis type="number" tickFormatter={v => `₹${v}`} tick={{ fontSize: 11 }} />
        <YAxis type="category" dataKey="color" width={60} tick={{ fontSize: 11 }} />
        <Tooltip formatter={(v: number) => `₹${v.toFixed(2)}`} />
        <Bar dataKey="cost" radius={[0, 4, 4, 0]}>
          {data.map((d, i) => <Cell key={i} fill={colorForToner(d.color)} />)}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
