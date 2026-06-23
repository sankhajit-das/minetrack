export default function MineMap({ sensors }) {
  function colorFor(status) {
    if (status === "critical") return "#f87171"
    if (status === "warning") return "#fbbf24"
    return "#4ade80"
  }

  function sensorIn(zoneName) {
    return sensors.filter(function(s) { return s.zone === zoneName })
  }

  const zoneLayout = [
    { name: "Main Entry", x: 40, y: 40, w: 180, h: 220 },
    { name: "Shaft A", x: 250, y: 40, w: 180, h: 220 },
    { name: "Heading C", x: 460, y: 40, w: 180, h: 220 },
  ]

  return (
    <svg width="100%" viewBox="0 0 680 300" style={{display: "block"}}>
      <rect x="10" y="10" width="660" height="280" rx="12" fill="none" stroke="#2d3148" strokeWidth="1" />
      <text x="20" y="30" fontSize="11" fill="#64748b">Mine layout — live sensor positions</text>

      {zoneLayout.map(function(zone, i) {
        const zoneSensors = sensorIn(zone.name)
        const hasCritical = zoneSensors.some(function(s) { return s.status === "critical" })
        const hasWarning = zoneSensors.some(function(s) { return s.status === "warning" })
        const borderColor = hasCritical ? "#991b1b" : hasWarning ? "#92400e" : "#2d3148"
        const fillColor = hasCritical ? "#1c0a0a" : hasWarning ? "#1c1200" : "#161829"

        return (
          <g key={zone.name}>
            <rect
              x={zone.x} y={zone.y} width={zone.w} height={zone.h}
              rx="10" fill={fillColor} stroke={borderColor} strokeWidth="1.5"
            />
            <text x={zone.x + 12} y={zone.y + 22} fontSize="13" fontWeight="500" fill="#e2e8f0">
              {zone.name}
            </text>

            {zoneSensors.map(function(s, idx) {
              const dotX = zone.x + 30 + (idx % 2) * 80
              const dotY = zone.y + 60 + Math.floor(idx / 2) * 70
              const color = colorFor(s.status)
              return (
                <g key={s.sensor_id}>
                  <circle cx={dotX} cy={dotY} r="14" fill={color} opacity="0.2">
                    {s.status === "critical" && (
                      <animate attributeName="r" values="14;20;14" dur="1.2s" repeatCount="indefinite" />
                    )}
                  </circle>
                  <circle cx={dotX} cy={dotY} r="7" fill={color} />
                  <text x={dotX} y={dotY + 28} fontSize="10" fill="#94a3b8" textAnchor="middle">
                    {s.sensor_code}
                  </text>
                  <text x={dotX} y={dotY + 40} fontSize="10" fontWeight="500" fill={color} textAnchor="middle">
                    {s.value.toFixed(1)}
                  </text>
                </g>
              )
            })}

            {zoneSensors.length === 0 && (
              <text x={zone.x + zone.w / 2} y={zone.y + zone.h / 2} fontSize="11" fill="#475569" textAnchor="middle">
                No sensors
              </text>
            )}
          </g>
        )
      })}

      <g>
        <circle cx="500" cy="270" r="5" fill="#4ade80" />
        <text x="510" y="274" fontSize="10" fill="#94a3b8">normal</text>
        <circle cx="565" cy="270" r="5" fill="#fbbf24" />
        <text x="575" y="274" fontSize="10" fill="#94a3b8">warning</text>
        <circle cx="630" cy="270" r="5" fill="#f87171" />
        <text x="640" y="274" fontSize="10" fill="#94a3b8">critical</text>
      </g>
    </svg>
  )
}
