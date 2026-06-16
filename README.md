# MineTrack — Real-Time Mine Operations Dashboard

A high-performance, real-time telemetry monitoring system designed for critical underground mine operations. Streams live sensor metrics (Methane, Carbon Monoxide, Sub-surface Temperature) from emulated IoT infrastructure to an operational web interface via WebSockets, persists high-velocity time-series datasets inside TimescaleDB, and coordinates instant alerting vectors via a Redis pub/sub backbone when safety thresholds are breached.

---

## Architecture

```text
Sensor Simulator  ──(HTTP POST)──>  FastAPI Backend  ──(Async write)──>  TimescaleDB Hypertable
                                           │
                                    (Redis Pub/Sub)
                                           │
                                           ▼
                                   WebSocket Server  ──(JSON Stream)──>  React Dashboard