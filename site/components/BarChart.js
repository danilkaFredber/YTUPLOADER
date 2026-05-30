"use client";
// Простой SVG-график без внешних зависимостей.
export default function BarChart({ data = [] }) {
  if (!data.length) return <div className="muted">Нет данных для графика.</div>;
  const max = Math.max(...data.map((d) => d.value), 1);
  const w = 100 / data.length;
  const svgStyle = { width: "100%", height: "170px", display: "block" };
  const labelRow = { display: "flex", marginTop: "6px" };
  const labelCell = { flex: 1, textAlign: "center", fontSize: "11px" };
  return (
    <div>
      <svg viewBox="0 0 100 60" preserveAspectRatio="none" style={svgStyle}>
        {data.map((d, i) => {
          const h = (d.value / max) * 50;
          const bh = Math.max(h, 0.5);
          return (
            <rect key={i} x={i * w + w * 0.18} y={56 - bh} width={w * 0.64}
              height={bh} rx="1.2" fill="#4f46e5" />
          );
        })}
      </svg>
      <div style={labelRow}>
        {data.map((d, i) => (
          <div key={i} className="muted" style={labelCell}>{d.label}</div>
        ))}
      </div>
    </div>
  );
}
