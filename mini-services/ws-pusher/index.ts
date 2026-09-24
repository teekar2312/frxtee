/**
 * ZeniTrade AI — WebSocket pusher service (port 3003)
 *
 * Pushes real-time ticks, positions, and alerts to the dashboard via socket.io.
 * The Python backend (port 8000) polls MT5 and POSTs updates here; this service
 * fans them out to all connected dashboard clients instantly (<50ms).
 *
 * Frontend connects via: io("/?XTransformPort=3003")
 */
import { createServer } from "http";
import { Server } from "socket.io";

const PORT = 3003;
const httpServer = createServer();
const io = new Server(httpServer, {
  cors: { origin: "*" },
  path: "/",
});

// auth token (must match ZENITRADE_API_TOKEN)
const API_TOKEN = process.env.ZENITRADE_API_TOKEN || "";

io.on("connection", (socket) => {
  console.log(`[ws] client connected: ${socket.id}`);

  // join rooms by symbol for targeted tick updates
  socket.on("subscribe", (symbols: string[]) => {
    for (const s of symbols) socket.join(`tick:${s}`);
    console.log(`[ws] ${socket.id} subscribed to: ${symbols.join(",")}`);
  });

  socket.on("disconnect", () => {
    console.log(`[ws] client disconnected: ${socket.id}`);
  });
});

// REST endpoint for Python backend to push updates
import express from "express";
const app = express();
app.use(express.json({ limit: "1mb" }));

// simple token auth
app.use((req, res, next) => {
  if (API_TOKEN && req.headers["x-api-token"] !== API_TOKEN) {
    return res.status(401).json({ error: "unauthorized" });
  }
  next();
});

app.post("/push/ticks", (req, res) => {
  const { ticks } = req.body;
  if (Array.isArray(ticks)) {
    for (const t of ticks) {
      io.to(`tick:${t.symbol}`).emit("tick", t);
    }
    io.emit("ticks", ticks); // broadcast all for ticker tape
  }
  res.json({ ok: true });
});

app.post("/push/positions", (req, res) => {
  const { positions } = req.body;
  io.emit("positions", positions || []);
  res.json({ ok: true });
});

app.post("/push/alert", (req, res) => {
  const { alert } = req.body;
  io.emit("alert", alert);
  res.json({ ok: true });
});

app.post("/push/order", (req, res) => {
  const { order } = req.body;
  io.emit("order", order);
  res.json({ ok: true });
});

app.get("/health", (_req, res) => {
  res.json({ ok: true, clients: io.engine.clientsCount });
});

const EXPRESS_PORT = 3004;
app.listen(EXPRESS_PORT, () => {
  console.log(`[ws] REST endpoint on :${EXPRESS_PORT}`);
});

httpServer.listen(PORT, () => {
  console.log(`[ws] socket.io on :${PORT}`);
});
