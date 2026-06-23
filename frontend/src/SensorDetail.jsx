import { useState, useEffect } from "react"
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts"

const API_URL = "http://127.0.0.1:8000"

export default function SensorDetail({ sensor, onClose }) {
  const [aggregate, setAggregate] = useState([])
  const [raw, setRaw] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(function() {
    if (!sensor) return
    setLoading(true)

    Promise.all([
      fetch(API_URL + "/sensors/" + sensor.sensor_id + "/readings/aggregate?bucket=5 minutes&hours=24")
        .then(function(r) { return r.json() }),
      fetch(API_URL + "/sensors/" + sensor.sensor_id + "/readings?limit=10")
        .then(function(r) { return r.json() })
    ]).then(function(results) {
      const agg = results[0]
      const rawData = results[1]
      setAggregate((agg.data || []).slice(0, 50).reverse().map(function(d) {
        return { t: new Date(d.bucket).toLocaleTimeString(), avg: d.avg, max: d.max, min: d.min }
      }))
      setRaw(rawData.readings || [])
      setLoading(false)
    }).catch(function() {
      setLoading(false)
    })
  }, [sensor])

  if (!sensor) return null

  return (
    <div style={{
      position: "fixed", top: 0, left: 0, right: 0, bottom: 0,
      background: "rgba(0,0,0,0.6)", display: "flex",
      alignItems: "center", justifyContent: "center", zIndex: 1000,
      padding: "20px"
    }} onClick={onClose}>
      <div
        style={{
          background: "#1a1d2e", border: "1px solid #2d3148", borderRadius: "12px",
          padding: "24px", maxWidth: "700px", width: "100%", maxHeight: "85vh",
          overflowY: "auto"
        }}
        onClick={function(e) { e.stopPropagation() }}
      >
        <div style={{display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px"}}>
          <div>
            <div style={{fontSize: "16px", fontWeight: 500, color: "#e2e8f0"}}>
              {sensor.sensor_code} — {sensor.type}
            </div>
            <div style={{fontSize: "12px", color: "#94a3b8", marginTop: "2px"}}>
              {sensor.zone} · warn {sensor.warn_threshold} · crit {sensor.crit_threshold}
            </div>
          </div>
          <button
            onClick={onClose}
            style={{
              background: "none", border: "none", color: "#94a3b8",
              fontSize: "20px", cursor: "pointer", padding: "4px 8px"
            }}
          >×</button>
        </div>

        {loading && <div style={{fontSize: "12px", color: "#64748b", padding: "20px 0"}}>Loading 24h history...</div>}

        {!loading && (
          <>
            <div style={{marginBottom: "16px"}}>
              <div style={{fontSize: "11px", color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.04em", marginBottom: "8px"}}>
                24-hour trend — 5 minute buckets (time_bucket aggregate query)
              </div>
              <ResponsiveContainer width="100%" height={160}>
                <LineChart data={aggregate}>
                  <XAxis dataKey="t" tick={{fontSize: 10, fill: "#64748b"}} />
                  <YAxis tick={{fontSize: 10, fill: "#64748b"}} domain={["auto", "auto"]} />
                  <Tooltip contentStyle={{background: "#1a1d2e", border: "1px solid #2d3148", fontSize: "11px"}} />
                  <Line type="monotone" dataKey="max" stroke="#f87171" strokeWidth={1} dot={false} name="max" />
                  <Line type="monotone" dataKey="avg" stroke="#4ade80" strokeWidth={1.5} dot={false} name="avg" />
                  <Line type="monotone" dataKey="min" stroke="#7dd3fc" strokeWidth={1} dot={false} name="min" />
                </LineChart>
              </ResponsiveContainer>
              {aggregate.length === 0 && (
                <div style={{fontSize: "11px", color: "#64748b", textAlign: "center", padding: "12px"}}>
                  Not enough historical data yet — keep the simulator running longer
                </div>
              )}
            </div>

            <div>
              <div style={{fontSize: "11px", color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.04em", marginBottom: "8px"}}>
                Recent raw readings
              </div>
              <table style={{width: "100%", fontSize: "12px"}}>
                <thead>
                  <tr>
                    <th style={{textAlign: "left", color: "#64748b", padding: "4px 0", fontWeight: 500}}>Time</th>
                    <th style={{textAlign: "right", color: "#64748b", padding: "4px 0", fontWeight: 500}}>Value</th>
                  </tr>
                </thead>
                <tbody>
                  {raw.slice(0, 8).map(function(r, i) {
                    return (
                      <tr key={i} style={{borderTop: "1px solid #2d3148"}}>
                        <td style={{padding: "5px 0", color: "#cbd5e1"}}>{new Date(r.time).toLocaleTimeString()}</td>
                        <td style={{padding: "5px 0", textAlign: "right", color: "#e2e8f0"}}>{r.value.toFixed(2)} {sensor.unit}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
