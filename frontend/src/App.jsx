import { useState, useEffect, useRef } from "react"
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts"
import "./index.css"
import SensorDetail from "./SensorDetail"
import MineMap from "./MineMap"

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
  if (!iso) return "—"
  const diff = Math.floor((Date.now() - new Date(iso)) / 1000)
  if (diff < 60) return diff + "s ago"
  if (diff < 3600) return Math.floor(diff / 60) + "m ago"
  return Math.floor(diff / 3600) + "h ago"
}
function fmtSeconds(s) {
  if (s === null || s === undefined) return "—"
  return s + "s"
}

export default function App() {
  const [sensors, setSensors] = useState([])
  const [alerts, setAlerts] = useState([])
  const [incidents, setIncidents] = useState([])
  const [history, setHistory] = useState({})
  const [wsStatus, setWsStatus] = useState("connecting")
  const [ventilating, setVentilating] = useState({})
  const [clickedInject, setClickedInject] = useState({})
  const [clickedVent, setClickedVent] = useState({})
  const [selectedSensor, setSelectedSensor] = useState(null)
  const wsRef = useRef(null)

  useEffect(function() {
    fetch(API_URL + "/alerts?limit=10")
      .then(function(r) { if (r.ok) return r.json() })
      .then(function(data) { if (data) setAlerts(data) })
      .catch(function() {})
  }, [])

  function refreshIncidents() {
    fetch(API_URL + "/incidents?limit=15")
      .then(function(r) { if (r.ok) return r.json() })
      .then(function(data) { if (data) setIncidents(data) })
      .catch(function() {})
  }

  useEffect(function() {
    refreshIncidents()
    const interval = setInterval(refreshIncidents, 4000)
    return function() { clearInterval(interval) }
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

  useEffect(function() {
    const interval = setInterval(function() {
      setVentilating(function(prev) {
        const next = {}
        Object.keys(prev).forEach(function(id) {
          const remaining = prev[id] - 1
          if (remaining > 0) next[id] = remaining
        })
        return next
      })
    }, 1000)
    return function() { clearInterval(interval) }
  }, [])

  function injectScenario(sensorId, value) {
    setClickedInject(function(prev) {
      const next = Object.assign({}, prev)
      next[sensorId] = true
      return next
    })
    setTimeout(function() {
      setClickedInject(function(prev) {
        const next = Object.assign({}, prev)
        delete next[sensorId]
        return next
      })
    }, 600)
    fetch(API_URL + "/sensors/" + sensorId + "/inject?value=" + value, { method: "POST" })
      .catch(function() {})
  }

  function activateVentilation(sensorId) {
    setClickedVent(function(prev) {
      const next = Object.assign({}, prev)
      next[sensorId] = true
      return next
    })
    fetch(API_URL + "/sensors/" + sensorId + "/ventilate", { method: "POST" })
      .then(function(r) { return r.json() })
      .then(function(data) {
        setVentilating(function(prev) {
          const next = Object.assign({}, prev)
          next[sensorId] = data.duration_seconds || 20
          return next
        })
      })
      .catch(function() {})
  }

  const criticalSensors = sensors.filter(function(s) { return s.status === "critical" })
  const hasEmergency = criticalSensors.length > 0

  return (
    <div>
      {hasEmergency && (
        <div className="emergency-banner">
          <div>
            <div className="emergency-text">⚠ EMERGENCY — {criticalSensors.length} sensor(s) at critical level</div>
            <div className="emergency-sub">
              {criticalSensors.map(function(s) { return s.sensor_code }).join(", ")} — immediate action required
            </div>
          </div>
        </div>
      )}

      <div className="topbar">
        <span className="topbar-title"><i className="topbar-icon">⛏</i>MineTrack — Matrix Operations</span>
        <div className="live-badge">
          <div className="live-dot" />
          <span>{wsStatus === "live" ? "LIVE · " + sensors.length + " NODES" : wsStatus.toUpperCase()}</span>
        </div>
      </div>

      <div className="main">

        <div className="stat-grid">
          {sensors.map(function(s) {
            const isVentilating = ventilating[s.sensor_id] > 0
            const needsAction = s.status === "warning" || s.status === "critical"
            const cardClass = "stat-card" + (s.status === "critical" ? " is-critical" : s.status === "warning" ? " is-warning" : " is-normal")
            const wasJustClicked = clickedVent[s.sensor_id]
            return (
              <div key={s.sensor_id} className={cardClass} onClick={function() { setSelectedSensor(s) }} style={{cursor: "pointer"}}>
                <div className="stat-label">{s.type} Telemetry · {s.zone}</div>
                <div className={"stat-value " + statusColor(s.status)}>
                  {s.value.toFixed(2)}<span className="stat-unit">{s.unit}</span>
                  <span className={badgeClass(s.status)}>{s.status}</span>
                </div>
                <div className="stat-meta">{s.sensor_code} · warn {s.warn_threshold} · crit {s.crit_threshold}</div>

                {isVentilating && (
                  <div className="vent-active-text">
                    <div className="vent-spinner" />
                    Ventilation active — {ventilating[s.sensor_id]}s remaining
                  </div>
                )}

                {!isVentilating && needsAction && (
                  <button
                    onClick={function(e) { e.stopPropagation(); activateVentilation(s.sensor_id) }}
                    className={"vent-btn" + (wasJustClicked ? " just-clicked" : "")}
                  >
                    {wasJustClicked ? "✓ Ventilation requested..." : "💨 Activate ventilation"}
                  </button>
                )}
              </div>
            )
          })}
        </div>

        <div className="panel" style={{marginBottom: "20px"}}>
          <div className="panel-title">Mine layout — live view</div>
          <MineMap sensors={sensors} />
        </div>

        <div className="panel" style={{marginBottom: "20px"}}>
          <div className="panel-title">Scenario injector — simulate an incident</div>
          <div style={{display: "flex", gap: "8px", flexWrap: "wrap"}}>
            {sensors.map(function(s) {
              const wasClicked = clickedInject[s.sensor_id]
              return (
                <button
                  key={s.sensor_id}
                  onClick={function() { injectScenario(s.sensor_id, s.crit_threshold * 1.4) }}
                  className={"inject-btn" + (wasClicked ? " just-clicked" : "")}
                >
                  {wasClicked ? "⚡ Injecting..." : "Trigger " + s.sensor_code + " critical"}
                </button>
              )
            })}
          </div>
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
              {alerts.slice(0, 6).map(function(a, i) {
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

        <div className="panel" style={{marginTop: "4px"}}>
          <div className="panel-title">Operator response log — incident history</div>
          {incidents.length === 0 && <div className="no-alerts">No incidents recorded yet — trigger a scenario to see one here</div>}
          {incidents.length > 0 && (
            <table className="incident-table">
              <thead>
                <tr>
                  <th>Sensor</th>
                  <th>Breach value</th>
                  <th>Peak value</th>
                  <th>Breach time</th>
                  <th>Response time</th>
                  <th>Recovery time</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {incidents.map(function(inc) {
                  const statusClass = inc.status === "resolved" ? "incident-resolved"
                    : inc.status === "ventilating" ? "incident-ventilating"
                    : "incident-open"
                  const responseClass = inc.response_seconds !== null && inc.response_seconds <= 10 ? "metric-good" : "metric-slow"
                  const recoveryClass = inc.recovery_seconds !== null && inc.recovery_seconds <= 20 ? "metric-good" : "metric-slow"
                  return (
                    <tr key={inc.id}>
                      <td>{inc.sensor_code}</td>
                      <td>{inc.breach_value.toFixed(2)} {inc.unit}</td>
                      <td>{inc.peak_value.toFixed(2)} {inc.unit}</td>
                      <td>{timeAgo(inc.breach_at)}</td>
                      <td className={inc.response_seconds !== null ? responseClass : ""}>{fmtSeconds(inc.response_seconds)}</td>
                      <td className={inc.recovery_seconds !== null ? recoveryClass : ""}>{fmtSeconds(inc.recovery_seconds)}</td>
                      <td><span className={"incident-status " + statusClass}>{inc.status}</span></td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          )}
        </div>

      </div>

      <SensorDetail sensor={selectedSensor} onClose={function() { setSelectedSensor(null) }} />
    </div>
  )
}
