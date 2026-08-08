import React, { useState, useEffect, useCallback } from "react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { TrendingUp, Activity, Play, Circle, ChevronRight, ArrowUpRight, History } from "lucide-react";

const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000";
const GOLD = "#FFD700";
const GOLD_DARK = "#B8960A";

const fmtMoney = (n) =>
  n == null ? "—" : `$${n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const fmtPct = (n) => (n == null ? "—" : `${n >= 0 ? "+" : ""}${n.toFixed(2)}%`);

function StatCard({ label, value, tone = "neutral" }) {
  const toneClass =
    tone === "positive" ? "text-emerald-600" : tone === "negative" ? "text-red-600" : "text-neutral-900";
  return (
    <div className="bg-white border border-neutral-200 rounded-2xl px-5 py-4">
      <p className="text-[11px] uppercase tracking-wider text-neutral-400 mb-1.5 font-medium">{label}</p>
      <p className={`text-2xl font-mono font-medium ${toneClass}`}>{value}</p>
    </div>
  );
}

function Badge({ children, tone = "neutral" }) {
  const map = {
    neutral: "bg-neutral-100 text-neutral-600",
    running: "bg-[#FFF9DB] text-[#8A6D00]",
    done: "bg-emerald-50 text-emerald-700",
  };
  return <span className={`text-[11px] font-mono px-2.5 py-1 rounded-full ${map[tone]}`}>{children}</span>;
}

function NavRail({ tab, setTab }) {
  const items = [
    { id: "backtest", label: "Backtest", icon: Play },
    { id: "live", label: "Live", icon: Activity },
  ];
  return (
    <nav className="flex flex-col gap-1 w-48 shrink-0">
      {items.map(({ id, label, icon: Icon }) => {
        const active = tab === id;
        return (
          <button
            key={id}
            onClick={() => setTab(id)}
            className={`flex items-center justify-between px-3.5 py-2.5 rounded-xl text-sm transition-colors ${
              active ? "bg-neutral-900 text-white font-medium" : "text-neutral-500 hover:bg-neutral-100"
            }`}
          >
            <span className="flex items-center gap-2.5">
              <Icon size={15} strokeWidth={2} />
              {label}
            </span>
            {active && <ChevronRight size={14} />}
          </button>
        );
      })}
    </nav>
  );
}

function EventRow({ e }) {
  return (
    <div className="flex items-center justify-between text-xs font-mono px-3 py-2 rounded-lg bg-neutral-50 border border-neutral-100">
      <span
        className={
          e.type === "fill"
            ? "text-emerald-600 font-medium"
            : e.type === "order"
            ? "text-[#8A6D00] font-medium"
            : "text-neutral-400"
        }
      >
        {e.type}
      </span>
      <span className="text-neutral-700 flex items-center gap-1.5">
        <span>{e.symbol}</span>
        {e.side && (
          <span className={`font-medium ${e.side === "BUY" ? "text-emerald-600" : "text-red-600"}`}>
            {e.side}
          </span>
        )}
        <span>{e.price ?? e.fill_price ?? ""}</span>
      </span>
      <span className="text-neutral-400">{new Date(e.timestamp).toLocaleTimeString()}</span>
    </div>
  );
}

function BacktestTab() {
  const [form, setForm] = useState({ symbol: "AAPL", start: "2025-01-01", end: "2025-06-01" });
  const [runId, setRunId] = useState(null);
  const [status, setStatus] = useState("idle");
  const [result, setResult] = useState(null);
  const [curve, setCurve] = useState([]);
  const [error, setError] = useState(null);

  const trigger = async () => {
    setStatus("running");
    setError(null);
    setResult(null);
    setCurve([]);
    try {
      const res = await fetch(`${API_BASE}/backtest`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      if (!res.ok) throw new Error((await res.json()).detail || "Request failed");
      const data = await res.json();
      setRunId(data.run_id);
    } catch (e) {
      setStatus("error");
      setError(e.message);
    }
  };

  const poll = useCallback(async () => {
    if (!runId || status !== "running") return;
    try {
      const res = await fetch(`${API_BASE}/backtest/${runId}`);
      const data = await res.json();
      if (data.metrics) {
        setResult(data.metrics);
        setStatus("done");
        const curveRes = await fetch(`${API_BASE}/backtest/${runId}/equity-curve`);
        const curveData = await curveRes.json();
        setCurve(curveData.points || []);
      }
    } catch (e) {
      /* still running */
    }
  }, [runId, status]);

  useEffect(() => {
    if (status !== "running") return;
    const id = setInterval(poll, 1500);
    return () => clearInterval(id);
  }, [poll, status]);

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-medium text-neutral-900 mb-1">Run a backtest</h1>
        <p className="text-sm text-neutral-500">Replay historical data through the strategy and score the result.</p>
      </div>

      <div className="bg-white border border-neutral-200 rounded-2xl p-5">
        <div className="grid grid-cols-3 gap-4 mb-4">
          <div>
            <label className="text-[11px] uppercase tracking-wider text-neutral-400 font-medium block mb-1.5">
              Symbol
            </label>
            <input
              value={form.symbol}
              onChange={(e) => setForm({ ...form, symbol: e.target.value.toUpperCase() })}
              className="w-full font-mono text-sm border border-neutral-200 rounded-xl px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-[#FFD700] focus:border-transparent transition-shadow"
            />
          </div>
          <div>
            <label className="text-[11px] uppercase tracking-wider text-neutral-400 font-medium block mb-1.5">
              Start
            </label>
            <input
              type="date"
              value={form.start}
              onChange={(e) => setForm({ ...form, start: e.target.value })}
              className="w-full font-mono text-sm border border-neutral-200 rounded-xl px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-[#FFD700] focus:border-transparent transition-shadow"
            />
          </div>
          <div>
            <label className="text-[11px] uppercase tracking-wider text-neutral-400 font-medium block mb-1.5">
              End
            </label>
            <input
              type="date"
              value={form.end}
              onChange={(e) => setForm({ ...form, end: e.target.value })}
              className="w-full font-mono text-sm border border-neutral-200 rounded-xl px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-[#FFD700] focus:border-transparent transition-shadow"
            />
          </div>
        </div>
        <button
          onClick={trigger}
          disabled={status === "running"}
          className="flex items-center gap-2 text-sm font-medium px-4 py-2.5 rounded-xl transition-all disabled:opacity-40"
          style={{ background: GOLD, color: "#1A1A1A" }}
        >
          <Play size={14} fill="#1A1A1A" />
          {status === "running" ? "Running…" : "Run backtest"}
        </button>
        {error && <p className="text-sm text-red-600 mt-3">{error}</p>}
      </div>

      {runId && (
        <div className="bg-white border border-neutral-200 rounded-2xl p-5">
          <div className="flex items-center justify-between mb-4">
            <span className="font-mono text-sm text-neutral-500">Run #{runId}</span>
            <Badge tone={status === "running" ? "running" : status === "done" ? "done" : "neutral"}>
              {status === "running" ? "running" : status === "done" ? "complete" : status}
            </Badge>
          </div>

          {result && (
            <>
              <div className="grid grid-cols-4 gap-3 mb-6">
                <StatCard
                  label="Total return"
                  value={fmtPct(result.total_return_pct)}
                  tone={result.total_return_pct >= 0 ? "positive" : "negative"}
                />
                <StatCard label="Win rate" value={`${result.win_rate.toFixed(1)}%`} />
                <StatCard label="Max drawdown" value={`${result.max_drawdown_pct.toFixed(2)}%`} tone="negative" />
                <StatCard label="Total trades" value={result.total_trades} />
              </div>

              {curve.length > 0 && (
                <div style={{ height: 220 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={curve}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#F5F5F4" />
                      <XAxis
                        dataKey="trade_number"
                        tick={{ fontSize: 11, fontFamily: "monospace", fill: "#A3A3A3" }}
                        axisLine={{ stroke: "#E5E5E5" }}
                        tickLine={false}
                      />
                      <YAxis
                        tick={{ fontSize: 11, fontFamily: "monospace", fill: "#A3A3A3" }}
                        axisLine={false}
                        tickLine={false}
                        domain={([dataMin, dataMax]) => {
                          const padding = Math.max((dataMax - dataMin) * 0.5, 50);
                          return [Math.min(dataMin - padding, 9800), Math.max(dataMax + padding, 10200)];
                        }}
                      />
                      <Tooltip
                        formatter={(v) => fmtMoney(v)}
                        contentStyle={{
                          fontFamily: "monospace",
                          fontSize: 12,
                          borderRadius: 10,
                          border: "1px solid #E5E5E5",
                        }}
                      />
                      <Line
                        type="monotone"
                        dataKey="capital"
                        stroke="#1A1A1A"
                        strokeWidth={2}
                        dot={{ r: 3, fill: GOLD, stroke: "#1A1A1A", strokeWidth: 1.5 }}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              )}
            </>
          )}

          {!result && status === "running" && <p className="text-sm text-neutral-400 font-mono">Waiting for fills…</p>}
        </div>
      )}
    </div>
  );
}

function LiveTab() {
  const [connected, setConnected] = useState(false);
  const [events, setEvents] = useState([]);
  const [live, setLive] = useState(false);
  const [pastRuns, setPastRuns] = useState([]);
  const [viewingRunId, setViewingRunId] = useState(null);

  const loadPastRuns = useCallback(async () => {
    const res = await fetch(`${API_BASE}/live/runs`);
    if (res.ok) setPastRuns(await res.json());
  }, []);

  useEffect(() => {
    loadPastRuns();
  }, [loadPastRuns]);

  const startLive = async () => {
    const res = await fetch(`${API_BASE}/live/start`, { method: "POST" });
    if (res.ok) {
      setLive(true);
      setEvents([]);
      setViewingRunId(null);
    }
  };

  const stopLive = async () => {
    await fetch(`${API_BASE}/live/stop`, { method: "POST" });
    setLive(false);
    loadPastRuns();
  };

  const viewPastRun = async (runId) => {
    setViewingRunId(runId);
    const res = await fetch(`${API_BASE}/live/runs/${runId}/fills`);
    const fills = await res.json();
    setEvents(fills);
  };

  const backToLive = () => {
    setViewingRunId(null);
    setEvents([]);
  };

  useEffect(() => {
    const wsBase = API_BASE.replace("http", "ws");
    const ws = new WebSocket(`${wsBase}/ws/live`);
    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);
    ws.onmessage = (msg) => {
      if (viewingRunId !== null) return;
      const data = JSON.parse(msg.data);
      setEvents((prev) => [data, ...prev].slice(0, 30));
    };
    return () => ws.close();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-medium text-neutral-900 mb-1">Live paper trading</h1>
        <p className="text-sm text-neutral-500">The same strategy, reacting to a simulated live feed.</p>
      </div>

      <div className="flex gap-5">
        <div className="flex-1 bg-white border border-neutral-200 rounded-2xl p-5">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              {viewingRunId === null ? (
                <>
                  <Circle
                    size={8}
                    className={connected ? "text-emerald-500 fill-emerald-500" : "text-neutral-300 fill-neutral-300"}
                  />
                  <span className="text-sm font-mono text-neutral-500">
                    {connected ? "connected" : "not connected"}
                  </span>
                </>
              ) : (
                <span className="text-sm font-mono text-neutral-500">
                  Viewing run #{viewingRunId} (replay)
                </span>
              )}
            </div>
            {viewingRunId === null ? (
              <button
                onClick={live ? stopLive : startLive}
                className="flex items-center gap-2 text-sm font-medium px-4 py-2 rounded-xl"
                style={live ? { background: "#F5F5F4", color: "#525252" } : { background: GOLD, color: "#1A1A1A" }}
              >
                <Play size={13} fill={live ? "#525252" : "#1A1A1A"} />
                {live ? "Stop live" : "Start live"}
              </button>
            ) : (
              <button
                onClick={backToLive}
                className="text-sm font-medium px-4 py-2 rounded-xl bg-neutral-100 text-neutral-600"
              >
                Back to live
              </button>
            )}
          </div>

          {live && viewingRunId === null && (
            <p className="text-xs text-neutral-400 mb-4">
              Requires{" "}
              <code className="font-mono bg-neutral-100 px-1 py-0.5 rounded">simulate_live_feed.py</code> running
              separately.
            </p>
          )}

          <div className={`space-y-1.5 max-h-96 overflow-y-auto ${!live && viewingRunId === null && events.length > 0 ? "opacity-60" : ""}`}>
            {events.length === 0 && (
              <p className="text-sm text-neutral-400 text-center py-8">
                {viewingRunId !== null
                  ? "No fills recorded for this run"
                  : live
                  ? "Waiting for ticks…"
                  : "Start live mode to see events"}
              </p>
            )}
            {events.map((e, i) => (
              <EventRow key={i} e={e} />
            ))}
          </div>
        </div>

        <div className="w-56 shrink-0">
          <div className="flex items-center gap-1.5 mb-3 text-xs font-medium text-neutral-400 uppercase tracking-wider">
            <History size={13} />
            Past sessions
          </div>
          <div className="space-y-1.5">
            {pastRuns.length === 0 && (
              <p className="text-xs text-neutral-400">No past sessions yet</p>
            )}
            {pastRuns.map((r) => (
              <button
                key={r.run_id}
                onClick={() => viewPastRun(r.run_id)}
                className={`w-full text-left px-3 py-2 rounded-lg text-xs font-mono border transition-colors ${
                  viewingRunId === r.run_id
                    ? "bg-neutral-900 text-white border-neutral-900"
                    : "bg-white text-neutral-600 border-neutral-200 hover:border-neutral-300"
                }`}
              >
                <div className="flex items-center justify-between">
                  <span>#{r.run_id}</span>
                  <span className="opacity-60">{r.symbol}</span>
                </div>
                <div className="opacity-50 mt-0.5">
                  {new Date(r.created_at).toLocaleString(undefined, {
                    month: "short",
                    day: "numeric",
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </div>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

export default function App() {
  const [tab, setTab] = useState("backtest");

  return (
    <div className="min-h-screen bg-[#FBFBFB]">
      <header className="border-b border-neutral-200 bg-white">
        <div className="max-w-5xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-lg flex items-center justify-center" style={{ background: GOLD }}>
              <TrendingUp size={15} color="#1A1A1A" strokeWidth={2.5} />
            </div>
            <span className="font-medium text-neutral-900">flowtrade</span>
          </div>
          <a
            href="https://github.com/anukriti2306/flowtrade"
            className="flex items-center gap-1 text-xs font-mono text-neutral-400 hover:text-neutral-900 transition-colors"
          >
            source <ArrowUpRight size={12} />
          </a>
        </div>
      </header>

      <div className="max-w-5xl mx-auto px-6 py-8 flex gap-8">
        <NavRail tab={tab} setTab={setTab} />
        <div className="flex-1 min-w-0">{tab === "backtest" ? <BacktestTab /> : <LiveTab />}</div>
      </div>
    </div>
  );
}