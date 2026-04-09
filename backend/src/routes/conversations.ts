import { Router } from "express";
import { pool } from "../db";
import { authMiddleware, AuthRequest } from "../middleware/auth";

const router = Router();

router.use(authMiddleware);

// ── GET /conversations — lista conversas do usuário ───────────────────────────
router.get("/", async (req: AuthRequest, res) => {
  try {
    const userId = req.user!.id;

    const result = await pool.query(
      `SELECT
         c.id,
         c.titulo,
         c.pinned,
         c.criado_em,
         c.atualizado_em,
         (
           SELECT m.conteudo
           FROM mensagens m
           WHERE m.conversa_id = c.id
           ORDER BY m.criado_em DESC
           LIMIT 1
         ) AS ultima_mensagem
       FROM conversas c
       WHERE c.usuario_id = $1
       ORDER BY c.pinned DESC, c.atualizado_em DESC`,
      [userId]
    );

    return res.json({ conversations: result.rows });
  } catch (error) {
    console.error("Erro ao listar conversas:", error);
    return res.status(500).json({ message: "Erro ao listar conversas" });
  }
});

// ── POST /conversations — cria nova conversa ──────────────────────────────────
router.post("/", async (req: AuthRequest, res) => {
  try {
    const userId = req.user!.id;
    const { titulo } = req.body;

    const result = await pool.query(
      `INSERT INTO conversas (usuario_id, titulo)
       VALUES ($1, $2)
       RETURNING id, titulo, pinned, criado_em, atualizado_em`,
      [userId, titulo || "Nova conversa"]
    );

    return res.status(201).json({ conversation: result.rows[0] });
  } catch (error) {
    console.error("Erro ao criar conversa:", error);
    return res.status(500).json({ message: "Erro ao criar conversa" });
  }
});

// ── PATCH /conversations/:id/title — atualiza título ─────────────────────────
router.patch("/:id/title", async (req: AuthRequest, res) => {
  try {
    const userId = req.user!.id;
    const { id } = req.params;
    const { titulo } = req.body;

    if (!titulo) {
      return res.status(400).json({ message: "Título obrigatório" });
    }

    const result = await pool.query(
      `UPDATE conversas SET titulo = $1
       WHERE id = $2 AND usuario_id = $3
       RETURNING id, titulo, pinned, criado_em, atualizado_em`,
      [titulo, id, userId]
    );

    if (result.rows.length === 0) {
      return res.status(404).json({ message: "Conversa não encontrada" });
    }

    return res.json({ conversation: result.rows[0] });
  } catch (error) {
    console.error("Erro ao atualizar título:", error);
    return res.status(500).json({ message: "Erro ao atualizar título" });
  }
});

// ── PATCH /conversations/:id/pin — alterna fixado ────────────────────────────
router.patch("/:id/pin", async (req: AuthRequest, res) => {
  try {
    const userId = req.user!.id;
    const { id } = req.params;

    const result = await pool.query(
      `UPDATE conversas SET pinned = NOT pinned
       WHERE id = $1 AND usuario_id = $2
       RETURNING id, titulo, pinned, criado_em, atualizado_em`,
      [id, userId]
    );

    if (result.rows.length === 0) {
      return res.status(404).json({ message: "Conversa não encontrada" });
    }

    return res.json({ conversation: result.rows[0] });
  } catch (error) {
    console.error("Erro ao alternar pin:", error);
    return res.status(500).json({ message: "Erro ao alternar pin" });
  }
});

// ── DELETE /conversations/:id — remove conversa ───────────────────────────────
router.delete("/:id", async (req: AuthRequest, res) => {
  try {
    const userId = req.user!.id;
    const { id } = req.params;

    const result = await pool.query(
      `DELETE FROM conversas WHERE id = $1 AND usuario_id = $2 RETURNING id`,
      [id, userId]
    );

    if (result.rows.length === 0) {
      return res.status(404).json({ message: "Conversa não encontrada" });
    }

    return res.json({ ok: true });
  } catch (error) {
    console.error("Erro ao deletar conversa:", error);
    return res.status(500).json({ message: "Erro ao deletar conversa" });
  }
});

// ── GET /conversations/:id/messages — mensagens de uma conversa ───────────────
router.get("/:id/messages", async (req: AuthRequest, res) => {
  try {
    const userId = req.user!.id;
    const { id } = req.params;

    // Garante que a conversa pertence ao usuário
    const check = await pool.query(
      `SELECT id FROM conversas WHERE id = $1 AND usuario_id = $2`,
      [id, userId]
    );

    if (check.rows.length === 0) {
      return res.status(404).json({ message: "Conversa não encontrada" });
    }

    const result = await pool.query(
      `SELECT id, role, conteudo, criado_em
       FROM mensagens
       WHERE conversa_id = $1
       ORDER BY criado_em ASC`,
      [id]
    );

    return res.json({ messages: result.rows });
  } catch (error) {
    console.error("Erro ao buscar mensagens:", error);
    return res.status(500).json({ message: "Erro ao buscar mensagens" });
  }
});

// ── POST /conversations/:id/messages — grava mensagem ────────────────────────
router.post("/:id/messages", async (req: AuthRequest, res) => {
  try {
    const userId = req.user!.id;
    const { id } = req.params;
    const { role, conteudo } = req.body;

    if (!role || !conteudo) {
      return res.status(400).json({ message: "role e conteudo são obrigatórios" });
    }

    if (!["user", "assistant"].includes(role)) {
      return res.status(400).json({ message: "role deve ser 'user' ou 'assistant'" });
    }

    // Garante que a conversa pertence ao usuário
    const check = await pool.query(
      `SELECT id FROM conversas WHERE id = $1 AND usuario_id = $2`,
      [id, userId]
    );

    if (check.rows.length === 0) {
      return res.status(404).json({ message: "Conversa não encontrada" });
    }

    const result = await pool.query(
      `INSERT INTO mensagens (conversa_id, role, conteudo)
       VALUES ($1, $2, $3)
       RETURNING id, role, conteudo, criado_em`,
      [id, role, conteudo]
    );

    return res.status(201).json({ message: result.rows[0] });
  } catch (error) {
    console.error("Erro ao gravar mensagem:", error);
    return res.status(500).json({ message: "Erro ao gravar mensagem" });
  }
});

export default router;
