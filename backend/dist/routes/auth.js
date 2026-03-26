"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const express_1 = require("express");
const bcryptjs_1 = __importDefault(require("bcryptjs"));
const jsonwebtoken_1 = __importDefault(require("jsonwebtoken"));
const db_1 = require("../db");
const auth_1 = require("../middleware/auth");
const router = (0, express_1.Router)();
router.post("/register", async (req, res) => {
    try {
        const { nome, email, password, setor } = req.body;
        if (!nome || !email || !password) {
            return res.status(400).json({ message: "Nome, email e senha são obrigatórios" });
        }
        const emailNormalizado = String(email).trim().toLowerCase();
        const existingUser = await db_1.pool.query("SELECT id FROM usuarios WHERE email = $1 LIMIT 1", [emailNormalizado]);
        if (existingUser.rows.length > 0) {
            return res.status(409).json({ message: "Já existe usuário com esse email" });
        }
        const senha_hash = await bcryptjs_1.default.hash(password, 10);
        const result = await db_1.pool.query(`INSERT INTO usuarios (nome, email, senha_hash, setor)
       VALUES ($1, $2, $3, $4)
       RETURNING id, nome, email, setor, nivel_acesso`, [nome, emailNormalizado, senha_hash, setor || "GERAL"]);
        const user = result.rows[0];
        const token = jsonwebtoken_1.default.sign({
            id: user.id,
            email: user.email,
            nome: user.nome,
            setor: user.setor,
            nivel_acesso: user.nivel_acesso,
        }, process.env.JWT_SECRET, { expiresIn: "7d" });
        return res.status(201).json({ token, user });
    }
    catch (error) {
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
        const result = await db_1.pool.query(`SELECT id, nome, email, senha_hash, setor, nivel_acesso, ativo
       FROM usuarios
       WHERE email = $1
       LIMIT 1`, [emailNormalizado]);
        if (result.rows.length === 0) {
            return res.status(401).json({ message: "Email ou senha inválidos" });
        }
        const user = result.rows[0];
        if (!user.ativo) {
            return res.status(403).json({ message: "Usuário inativo" });
        }
        const senhaValida = await bcryptjs_1.default.compare(password, user.senha_hash);
        if (!senhaValida) {
            return res.status(401).json({ message: "Email ou senha inválidos" });
        }
        const token = jsonwebtoken_1.default.sign({
            id: user.id,
            email: user.email,
            nome: user.nome,
            setor: user.setor,
            nivel_acesso: user.nivel_acesso,
        }, process.env.JWT_SECRET, { expiresIn: "7d" });
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
    }
    catch (error) {
        console.error("Erro no login:", error);
        return res.status(500).json({ message: "Erro interno ao autenticar" });
    }
});
router.get("/me", auth_1.authMiddleware, async (req, res) => {
    try {
        const userId = req.user?.id;
        const result = await db_1.pool.query(`SELECT id, nome, email, setor, nivel_acesso, ativo
       FROM usuarios
       WHERE id = $1
       LIMIT 1`, [userId]);
        if (result.rows.length === 0) {
            return res.status(404).json({ message: "Usuário não encontrado" });
        }
        const user = result.rows[0];
        if (!user.ativo) {
            return res.status(403).json({ message: "Usuário inativo" });
        }
        return res.json({ user });
    }
    catch (error) {
        console.error("Erro no /me:", error);
        return res.status(500).json({ message: "Erro interno ao buscar usuário" });
    }
});
exports.default = router;
