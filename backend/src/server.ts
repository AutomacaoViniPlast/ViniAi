import express from "express";
import cors from "cors";
import dotenv from "dotenv";
import authRoutes from "./routes/auth";
import conversationRoutes from "./routes/conversations";
import { pool } from "./db";

dotenv.config();

const requiredEnv = [
  "DB_HOST",
  "DB_PORT",
  "DB_NAME",
  "DB_USER",
  "DB_PASSWORD",
  "JWT_SECRET",
  "PORT",
];

const missingEnv = requiredEnv.filter((key) => !process.env[key]);

if (missingEnv.length > 0) {
  console.error("Variáveis de ambiente ausentes:", missingEnv.join(", "));
  process.exit(1);
}

const app = express();

app.use(
  cors({
    origin: [
      "http://localhost:3001",
      "http://192.168.1.84:3001",
      "http://192.168.1.84:3003",
      "http://viniai.viniplast.local:3003",
    ],
    credentials: true,
  })
);

app.use(express.json());

app.get("/health", async (_req, res) => {
  try {
    const result = await pool.query(
      "SELECT current_database() AS database, current_user AS user, NOW() AS now"
    );

    return res.json({
      ok: true,
      api: true,
      db: true,
      jwt: !!process.env.JWT_SECRET,
      info: result.rows[0],
    });
  } catch (error) {
    console.error("Erro no /health:", error);
    return res.status(500).json({
      ok: false,
      api: true,
      db: false,
      jwt: !!process.env.JWT_SECRET,
      error: error instanceof Error ? error.message : String(error),
    });
  }
});

app.use("/auth", authRoutes);
app.use("/conversations", conversationRoutes);

const PORT = Number(process.env.PORT || 4000);

app.listen(PORT, "0.0.0.0", () => {
  console.log(`API rodando na porta ${PORT}`);
  console.log("DB_HOST:", process.env.DB_HOST);
  console.log("DB_PORT:", process.env.DB_PORT);
  console.log("DB_NAME:", process.env.DB_NAME);
  console.log("DB_USER:", process.env.DB_USER);
  console.log("JWT_SECRET carregado?", !!process.env.JWT_SECRET);
});