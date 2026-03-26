import { Router } from "express";
import bcrypt from "bcryptjs";
import jwt from "jsonwebtoken";
import { pool } from "../db";
import { authMiddleware, AuthRequest } from "../middleware/auth";

const router = Router();

router.post("/register", async (req, res) => {
  try {
    const { nome, email, password, setor } = req.body;

    if (!nome || !email || !password) {
      return res.status(400).json({ message: "Nome, email e senha são obrigatórios" });
    }

    const emailNormalizado = String(email).trim().toLowerCase();

    const existingUser = await pool.query(
      "SELECT id FROM usuarios WHERE email = $1 LIMIT 1",
      [emailNormalizado]
    );

    if (existingUser.rows.length > 0) {
      return res.status(409).json({ message: "Já existe usuário com esse email" });
    }

    const senha_hash = await bcrypt.hash(password, 10);

    const result = await pool.query(
      `INSERT INTO usuarios (nome, email, senha_hash, setor)
       VALUES ($1, $2, $3, $4)
       RETURNING id, nome, email, setor, nivel_acesso`,
      [nome, emailNormalizado, senha_hash, setor || "GERAL"]
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
      process.env.JWT_SECRET as string,
      { expiresIn: "7d" }
    );

    return res.status(201).json({ token, user });
  } catch (error) {
    console.error("Erro no register:", error);
    return res.status(500).json({ message: "Erro interno ao registrar usuário" });
  }
});

router.post("/login", async (req, res) => {
  try {
    const { email, password } = req.body;

    if (!email || !password) {
      return res.status(400).json({ message: "Email e senha são obrigatórios" });
    }

    const emailNormalizado = String(email).trim().toLowerCase();

    const result = await pool.query(
      `SELECT id, nome, email, senha_hash, setor, nivel_acesso, ativo
       FROM usuarios
       WHERE email = $1
       LIMIT 1`,
      [emailNormalizado]
    );

    if (result.rows.length === 0) {
      return res.status(401).json({ message: "Email ou senha inválidos" });
    }

    const user = result.rows[0];

    if (!user.ativo) {
      return res.status(403).json({ message: "Usuário inativo" });
    }

    const senhaValida = await bcrypt.compare(password, user.senha_hash);

    if (!senhaValida) {
      return res.status(401).json({ message: "Email ou senha inválidos" });
    }

    const token = jwt.sign(
      {
        id: user.id,
        email: user.email,
        nome: user.nome,
        setor: user.setor,
        nivel_acesso: user.nivel_acesso,
      },
      process.env.JWT_SECRET as string,
      { expiresIn: "7d" }
    );

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
    return res.status(500).json({ message: "Erro interno ao autenticar" });
  }
});

router.get("/me", authMiddleware, async (req: AuthRequest, res) => {
  try {
    const userId = req.user?.id;

    const result = await pool.query(
      `SELECT id, nome, email, setor, nivel_acesso, ativo
       FROM usuarios
       WHERE id = $1
       LIMIT 1`,
      [userId]
    );

    if (result.rows.length === 0) {
      return res.status(404).json({ message: "Usuário não encontrado" });
    }

    const user = result.rows[0];

    if (!user.ativo) {
      return res.status(403).json({ message: "Usuário inativo" });
    }

    return res.json({ user });
  } catch (error) {
    console.error("Erro no /me:", error);
    return res.status(500).json({ message: "Erro interno ao buscar usuário" });
  }
});

export default router;