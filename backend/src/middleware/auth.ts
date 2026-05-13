import { Request, Response, NextFunction } from "express";
import jwt from "jsonwebtoken";

export interface AuthRequest extends Request {
  user?: {
    id: number;
    email: string;
    nome: string;
    setor: string;
    nivel_acesso: string;
  };
}

export function authMiddleware(
  req: AuthRequest,
  res: Response,
  next: NextFunction
) {
  // Cookie httpOnly tem prioridade; Bearer como fallback para clientes legados
  const cookieToken = (req as any).cookies?.auth_token as string | undefined;
  const authHeader = req.headers.authorization;
  const bearerToken =
    authHeader?.startsWith("Bearer ") ? authHeader.slice(7) : undefined;

  const token = cookieToken || bearerToken;

  if (!token) {
    return res.status(401).json({ message: "Token não informado" });
  }

  const secret = process.env.JWT_SECRET;

  if (!secret) {
    return res.status(500).json({ message: "JWT_SECRET não configurado" });
  }

  try {
    const decoded = jwt.verify(token, secret) as AuthRequest["user"];
    req.user = decoded;
    return next();
  } catch (error) {
    console.error("Erro ao validar token:", error);
    return res.status(401).json({ message: "Token inválido ou expirado" });
  }
}
