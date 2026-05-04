import { Router } from "express";
import bcrypt from "bcryptjs";
import jwt from "jsonwebtoken";
import crypto from "crypto";
import { pool } from "../db";
import { authMiddleware, AuthRequest } from "../middleware/auth";
import { sendPasswordResetEmail } from "../services/mailer";

// Garante que a tabela de tokens existe na primeira inicialização
pool.query(`
  CREATE TABLE IF NOT EXISTS password_reset_tokens (
    id         SERIAL PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES usuarios(id),
    token      VARCHAR(64) NOT NULL UNIQUE,
    expires_at TIMESTAMPTZ NOT NULL,
    used       BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
  )
`).catch((err) => console.error("[AUTH] Erro ao criar tabela password_reset_tokens:", err));

const router = Router();

function getJwtSecret(): string {
  const secret = process.env.JWT_SECRET;

  if (!secret) {
    throw new Error("JWT_SECRET não definido");
  }

  return secret;
}

router.post("/register", async (req, res) => {
  try {
    const { nome, email, password, setor } = req.body;

    if (!nome || !email || !password) {
      return res.status(400).json({
        message: "Nome, email e senha são obrigatórios",
      });
    }

    const emailNormalizado = String(email).trim().toLowerCase();

    const existingUser = await pool.query(
      "SELECT id FROM usuarios WHERE email = $1 LIMIT 1",
      [emailNormalizado]
    );

    if (existingUser.rows.length > 0) {
      return res.status(409).json({
        message: "Já existe usuário com esse email",
      });
    }

    const senha_hash = await bcrypt.hash(String(password), 10);

    const result = await pool.query(
      `INSERT INTO usuarios (nome, email, senha_hash, setor, nivel_acesso, ativo)
       VALUES ($1, $2, $3, $4, $5, $6)
       RETURNING id, nome, email, setor, nivel_acesso`,
      [String(nome).trim(), emailNormalizado, senha_hash, setor || "GERAL", "USER", true]
    );

    const user = result.rows[0];

    const token = jwt.sign(
      {
        id: user.id,
        email: user.email,
        nome: user.nome,
        setor: user.setor,
        nivel_acesso: user.nivel_acesso,
      },
      getJwtSecret(),
      { expiresIn: "7d" }
    );

    return res.status(201).json({ token, user });
  } catch (error) {
    console.error("Erro no register:", error);
    return res.status(500).json({
      message: "Erro interno ao registrar usuário",
      error: error instanceof Error ? error.message : String(error),
    });
  }
});

router.post("/login", async (req, res) => {
  try {
    console.log("[LOGIN] Requisição recebida");

    const { email, password } = req.body;

    if (!email || !password) {
      return res.status(400).json({
        message: "Email e senha são obrigatórios",
      });
    }

    const emailNormalizado = String(email).trim().toLowerCase();
    console.log("[LOGIN] Email normalizado:", emailNormalizado);
    console.log("[LOGIN] JWT carregado?", !!process.env.JWT_SECRET);

    const result = await pool.query(
      `SELECT id, nome, email, senha_hash, setor, nivel_acesso, ativo
       FROM usuarios
       WHERE email = $1
       LIMIT 1`,
      [emailNormalizado]
    );

    console.log("[LOGIN] Usuários encontrados:", result.rows.length);

    if (result.rows.length === 0) {
      return res.status(401).json({
        message: "Email ou senha inválidos",
      });
    }

    const user = result.rows[0];

    console.log("[LOGIN] Usuário encontrado:", user.email);
    console.log("[LOGIN] Usuário ativo:", user.ativo);
    console.log("[LOGIN] senha_hash existe?", !!user.senha_hash);

    if (!user.ativo) {
      return res.status(403).json({
        message: "Usuário inativo",
      });
    }

    if (!user.senha_hash) {
      throw new Error("senha_hash ausente para este usuário");
    }

    const senhaValida = await bcrypt.compare(String(password), user.senha_hash);
    console.log("[LOGIN] Senha válida?", senhaValida);

    if (!senhaValida) {
      return res.status(401).json({
        message: "Email ou senha inválidos",
      });
    }

    const token = jwt.sign(
      {
        id: user.id,
        email: user.email,
        nome: user.nome,
        setor: user.setor,
        nivel_acesso: user.nivel_acesso,
      },
      getJwtSecret(),
      { expiresIn: "7d" }
    );

    console.log("[LOGIN] Token gerado com sucesso");

    return res.json({
      token,
      user: {
        id: user.id,
        nome: user.nome,
        email: user.email,
        setor: user.setor,
        nivel_acesso: user.nivel_acesso,
      },
    });
  } catch (error) {
    console.error("Erro no login:", error);
    return res.status(500).json({
      message: "Erro interno ao autenticar",
      error: error instanceof Error ? error.message : String(error),
    });
  }
});

router.get("/me", authMiddleware, async (req: AuthRequest, res) => {
  try {
    const userId = req.user?.id;

    if (!userId) {
      return res.status(401).json({
        message: "Usuário não autenticado",
      });
    }

    const result = await pool.query(
      `SELECT id, nome, email, setor, nivel_acesso, ativo
       FROM usuarios
       WHERE id = $1
       LIMIT 1`,
      [userId]
    );

    if (result.rows.length === 0) {
      return res.status(404).json({
        message: "Usuário não encontrado",
      });
    }

    const user = result.rows[0];

    if (!user.ativo) {
      return res.status(403).json({
        message: "Usuário inativo",
      });
    }

    return res.json({ user });
  } catch (error) {
    console.error("Erro no /me:", error);
    return res.status(500).json({
      message: "Erro interno ao buscar usuário",
      error: error instanceof Error ? error.message : String(error),
    });
  }
});

router.post("/forgot-password", async (req, res) => {
  try {
    const { email } = req.body;

    if (!email) {
      return res.status(400).json({ message: "Email é obrigatório" });
    }

    const emailNormalizado = String(email).trim().toLowerCase();

    const result = await pool.query(
      "SELECT id, nome FROM usuarios WHERE email = $1 AND ativo = true LIMIT 1",
      [emailNormalizado]
    );

    // Resposta genérica para não revelar se o e-mail existe
    if (result.rows.length === 0) {
      return res.json({ message: "Se o e-mail estiver cadastrado, você receberá as instruções em breve." });
    }

    const user = result.rows[0];

    // Invalida tokens anteriores do mesmo usuário
    await pool.query(
      "UPDATE password_reset_tokens SET used = true WHERE user_id = $1 AND used = false",
      [user.id]
    );

    const token = crypto.randomBytes(32).toString("hex");
    const expiresAt = new Date(Date.now() + 60 * 60 * 1000); // 1 hora

    await pool.query(
      "INSERT INTO password_reset_tokens (user_id, token, expires_at) VALUES ($1, $2, $3)",
      [user.id, token, expiresAt]
    );

    await sendPasswordResetEmail(emailNormalizado, user.nome, token);

    return res.json({ message: "Se o e-mail estiver cadastrado, você receberá as instruções em breve." });
  } catch (error) {
    console.error("Erro no forgot-password:", error);
    return res.status(500).json({ message: "Erro interno ao processar solicitação" });
  }
});

router.post("/reset-password", async (req, res) => {
  try {
    const { token, password } = req.body;

    if (!token || !password) {
      return res.status(400).json({ message: "Token e nova senha são obrigatórios" });
    }

    if (String(password).length < 6) {
      return res.status(400).json({ message: "A senha deve ter pelo menos 6 caracteres" });
    }

    const result = await pool.query(
      `SELECT t.id, t.user_id, t.expires_at, t.used
       FROM password_reset_tokens t
       WHERE t.token = $1
       LIMIT 1`,
      [String(token).trim()]
    );

    if (result.rows.length === 0) {
      return res.status(400).json({ message: "Link inválido ou expirado" });
    }

    const tokenRow = result.rows[0];

    if (tokenRow.used) {
      return res.status(400).json({ message: "Este link já foi utilizado" });
    }

    if (new Date() > new Date(tokenRow.expires_at)) {
      return res.status(400).json({ message: "Link expirado. Solicite um novo." });
    }

    const senha_hash = await bcrypt.hash(String(password), 10);

    await pool.query("UPDATE usuarios SET senha_hash = $1 WHERE id = $2", [senha_hash, tokenRow.user_id]);
    await pool.query("UPDATE password_reset_tokens SET used = true WHERE id = $1", [tokenRow.id]);

    return res.json({ message: "Senha redefinida com sucesso" });
  } catch (error) {
    console.error("Erro no reset-password:", error);
    return res.status(500).json({ message: "Erro interno ao redefinir senha" });
  }
});

export default router;