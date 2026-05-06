import { Router } from "express";
import bcrypt from "bcryptjs";
import { pool } from "../db";
import { adminMiddleware } from "../middleware/adminAuth";

const router = Router();

router.use(adminMiddleware);

// GET /admin/users — lista todos os usuários
router.get("/users", async (_req, res) => {
  try {
    const result = await pool.query(
      `SELECT id, nome, email, setor, nivel_acesso, ativo, force_password_change
       FROM usuarios
       ORDER BY ativo DESC, nome ASC`
    );
    return res.json(result.rows);
  } catch (error) {
    console.error("Erro ao listar usuários:", error);
    return res.status(500).json({ message: "Erro interno ao listar usuários" });
  }
});

// POST /admin/users — cria novo usuário
router.post("/users", async (req, res) => {
  try {
    const { nome, email, password, setor, nivel_acesso, force_password_change } = req.body;

    if (!nome || !email || !password) {
      return res.status(400).json({ message: "Nome, email e senha são obrigatórios" });
    }

    const emailNormalizado = String(email).trim().toLowerCase();

    const existing = await pool.query(
      "SELECT id FROM usuarios WHERE email = $1 LIMIT 1",
      [emailNormalizado]
    );

    if (existing.rows.length > 0) {
      return res.status(409).json({ message: "Já existe usuário com esse email" });
    }

    const senha_hash = await bcrypt.hash(String(password), 10);
    const forcarTroca = Boolean(force_password_change);

    const result = await pool.query(
      `INSERT INTO usuarios (nome, email, senha_hash, setor, nivel_acesso, ativo, force_password_change)
       VALUES ($1, $2, $3, $4, $5, true, $6)
       RETURNING id, nome, email, setor, nivel_acesso, ativo, force_password_change`,
      [
        String(nome).trim(),
        emailNormalizado,
        senha_hash,
        setor || "GERAL",
        nivel_acesso || "USER",
        forcarTroca,
      ]
    );

    return res.status(201).json(result.rows[0]);
  } catch (error) {
    console.error("Erro ao criar usuário:", error);
    return res.status(500).json({ message: "Erro interno ao criar usuário" });
  }
});

// PATCH /admin/users/:id — atualiza dados do usuário
router.patch("/users/:id", async (req, res) => {
  try {
    const { id } = req.params;
    const { nome, setor, nivel_acesso, ativo, password, force_password_change } = req.body;

    const fields: string[] = [];
    const values: unknown[] = [];
    let idx = 1;

    if (nome !== undefined) { fields.push(`nome = $${idx++}`); values.push(String(nome).trim()); }
    if (setor !== undefined) { fields.push(`setor = $${idx++}`); values.push(String(setor)); }
    if (nivel_acesso !== undefined) { fields.push(`nivel_acesso = $${idx++}`); values.push(String(nivel_acesso)); }
    if (ativo !== undefined) { fields.push(`ativo = $${idx++}`); values.push(Boolean(ativo)); }
    if (force_password_change !== undefined) { fields.push(`force_password_change = $${idx++}`); values.push(Boolean(force_password_change)); }
    if (password !== undefined && String(password).length >= 8) {
      const senha_hash = await bcrypt.hash(String(password), 10);
      fields.push(`senha_hash = $${idx++}`);
      values.push(senha_hash);
    }

    if (fields.length === 0) {
      return res.status(400).json({ message: "Nenhum campo para atualizar" });
    }

    values.push(Number(id));
    const result = await pool.query(
      `UPDATE usuarios SET ${fields.join(", ")} WHERE id = $${idx}
       RETURNING id, nome, email, setor, nivel_acesso, ativo, force_password_change`,
      values
    );

    if (result.rows.length === 0) {
      return res.status(404).json({ message: "Usuário não encontrado" });
    }

    return res.json(result.rows[0]);
  } catch (error) {
    console.error("Erro ao atualizar usuário:", error);
    return res.status(500).json({ message: "Erro interno ao atualizar usuário" });
  }
});

export default router;
