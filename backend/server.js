require("dotenv").config();

const express        = require("express");
const cors           = require("cors");
const multer         = require("multer");
const path           = require("path");
const fs             = require("fs");
const workflowRoutes = require("./routes/workflowRoutes");

const app  = express();
const PORT = process.env.PORT || 3001;

app.use(cors());
app.use(express.json());

// ── File Upload Setup ──────────────────────────────────────────────
const uploadDir = path.join(__dirname, "data", "uploads");
if (!fs.existsSync(uploadDir)) {
  fs.mkdirSync(uploadDir, { recursive: true });
}

const storage = multer.diskStorage({
  destination: (req, file, cb) => cb(null, uploadDir),
  filename:    (req, file, cb) => {
    const safe = file.originalname.replace(/[^a-zA-Z0-9._-]/g, "_");
    cb(null, `${Date.now()}-${safe}`);
  }
});

const upload = multer({
  storage,
  limits:    { fileSize: 10 * 1024 * 1024 }, // 10MB
  fileFilter: (req, file, cb) => {
    if (file.mimetype === "text/csv" || file.originalname.endsWith(".csv")) {
      cb(null, true);
    } else {
      cb(new Error("Only CSV files are allowed"));
    }
  }
});

// ── Upload Endpoint ────────────────────────────────────────────────
app.post("/api/upload", upload.single("file"), (req, res) => {
  if (!req.file) {
    return res.status(400).json({ success: false, error: "No file uploaded" });
  }

  console.log("[Upload] File received:", req.file.originalname);
  console.log("[Upload] Saved to:", req.file.path);

  return res.json({
    success:      true,
    filename:     req.file.originalname,
    savedAs:      req.file.filename,
    path:         req.file.path,
    size:         req.file.size,
    uploadedAt:   new Date().toISOString()
  });
});

// ── List Uploaded Files ────────────────────────────────────────────
app.get("/api/files", (req, res) => {
  const files = fs.readdirSync(uploadDir).map(f => ({
    name: f,
    path: path.join(uploadDir, f),
    size: fs.statSync(path.join(uploadDir, f)).size
  }));
  res.json({ success: true, files });
});

// ── Health Check ───────────────────────────────────────────────────
app.get("/health", (req, res) => {
  res.json({ status: "ok", timestamp: new Date().toISOString() });
});

// ── Workflow Routes ────────────────────────────────────────────────
app.use("/api/workflow", workflowRoutes);

// ── 404 ────────────────────────────────────────────────────────────
app.use((req, res) => {
  res.status(404).json({ error: `Route not found: ${req.method} ${req.path}` });
});

// ── Error Handler ──────────────────────────────────────────────────
app.use((err, req, res, next) => {
  console.error("[Server Error]", err.message);
  res.status(500).json({ error: err.message });
});

app.listen(PORT, () => {
  console.log(`Backend running on http://localhost:${PORT}`);
  console.log(`Upload endpoint: POST http://localhost:${PORT}/api/upload`);
});
