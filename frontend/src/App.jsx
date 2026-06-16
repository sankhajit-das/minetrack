import { useState, useEffect, useRef } from "react"
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts"
import "./index.css"

const API_URL = "http://127.0.0.1:8000"
const WS_URL = "ws://127.0.0.1:8000/ws"

function statusColor(s) {
  if (s === "critical") return "status-critical"
  if (s === "warning") return "status-warning"
  return "status-normal"
}
function badgeClass(s) {
  if (s === "critical") return "badge badge-critical"
  if (s === "warning") return "badge badge-warning"
  return "badge badge-normal"
}
function zoneClass(s) {
  if (s === "critical") return "zone-card zone-critical"
  if (s === "warning") return "zone-card zone-warning"
  return "zone-card zone-normal"
}
function timeAgo(iso) {
  if (!iso) return "unknown"
  const diff = Math.floor((Date.now() - new Date(iso)) / 1000)
  if (diff < 60) return diff + "s ago"
  if (diff < 3600) return Math.floor(diff / 60) + "m ago"
  return Math.floor(diff / 3600) + "h ago"
}

export default function App() {
  const [sensors, setSensors] = useState([])
  const [alerts, setAlerts] = useState([])
  const [history, setHistory] = useState({})
  const [wsStatus, setWsStatus] = useState("connecting")
  const wsRef = useRef(null)

  useEffect(function() {
    fetch(API_URL + "/alerts?limit=10")
      .then(function(r) { if (r.ok) return r.json() })
      .then(function(data) { if (data) setAlerts(data) })
      .catch(function() {})
  }, [])

  useEffect(function() {
    function connect() {
      const ws = new WebSocket(WS_URL)
      wsRef.current = ws
      ws.onopen = function() { setWsStatus("live") }
      ws.onclose = function() {
        setWsStatus("reconnecting")
        setTimeout(connect, 3000)
      }
      ws.onerror = function() { ws.close() }
      ws.onmessage = function(e) {
        const msg = JSON.parse(e.data)
        if (msg.type === "readings") {
          setSensors(msg.data)
          setHistory(function(prev) {
            const next = Object.assign({}, prev)
            msg.data.forEach(function(s) {
              const arr = next[s.sensor_id] || []
              const point = { t: new Date(s.time).toLocaleTimeString(), v: s.value }
              next[s.sensor_id] = arr.concat([point]).slice(-60)
            })
            return next
          })
        }
        if (msg.type === "alert") {
          setAlerts(function(prev) {
            const newAlert = Object.assign({}, msg.data, { created_at: new Date().toISOString() })
            return [newAlert].concat(prev).slice(0, 20)
          })
        }
      }
    }
    connect()
    return function() { if (wsRef.current) wsRef.current.close() }
  }, [])

  return (
    <div>
      <div className="topbar">
        <span className="topbar-title">⛏ MineTrack Matrix Operations</span>
        <div className="live-badge">
          <div className="live-dot" />
          <span>{wsStatus === "live" ? "Live · " + sensors.length + " Nodes Active" : "Status: " + wsStatus}</span>
        </div>
      </div>
      <div className="main">
        <div className="stat-grid">
          {sensors.map(function(s) {
            return (
              <div key={s.sensor_id} className="stat-card">
                <div className="stat-label">{s.type} Telemetry · {s.zone}</div>
                <div className={"stat-value " + statusColor(s.status)}>
                  {s.value.toFixed(2)} <span style={{ fontSize: "13px", color: "#94a3b8" }}>{s.unit}</span>
                  <span className={badgeClass(s.status)}>{s.status}</span>
                </div>
                <div className="stat-meta">{s.sensor_code} · warn {s.warn_threshold} · crit {s.crit_threshold}</div>
              </div>
            )
          })}
        </div>
        <div className="grid2">
          <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
            {sensors.map(function(s) {
              return (
                <div key={s.sensor_id} className="panel">
                  <div className="panel-title">{s.sensor_code} — {s.type} Historical Vector</div>
                  <ResponsiveContainer width="100%" height={80}>
                    <LineChart data={history[s.sensor_id] || []}>
                      <XAxis dataKey="t" hide />
                      <YAxis hide domain={["auto", "auto"]} />
                      <Tooltip
                        contentStyle={{ background: "#1a1d2e", border: "1px solid #2d3148", fontSize: "11px" }}
                        formatter={function(v) { return [v.toFixed(2), s.unit] }}
                      />
                      <Line type="monotone" dataKey="v" dot={false} strokeWidth={1.5}
                        stroke={s.status === "critical" ? "#f87171" : s.status === "warning" ? "#fbbf24" : "#4ade80"}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              )
            })}
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
            <div className="panel">
              <div className="panel-title">Recent System Alerts</div>
              {alerts.length === 0 && <div className="no-alerts">No telemetry anomalies detected</div>}
              {alerts.slice(0, 8).map(function(a, i) {
                return (
                  <div key={i} className="alert-row">
                    <div className={"alert-dot alert-dot-" + (a.severity || "normal")} />
                    <div className="alert-msg">{a.message}</div>
                    <div className="alert-time">{timeAgo(a.created_at)}</div>
                  </div>
                )
              })}
            </div>
            <div className="panel">
              <div className="panel-title">Hardware Infrastructure Matrix</div>
              <div className="zone-grid">
                {sensors.map(function(s) {
                  return (
                    <div key={s.sensor_id} className={zoneClass(s.status)}>
                      <div className="zone-name">{s.sensor_code} · {s.zone}</div>
                      <div className="zone-detail">{s.value.toFixed(2)} {s.unit} · {s.status}</div>
                    </div>
                  )
                })}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
