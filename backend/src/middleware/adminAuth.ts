import { Response, NextFunction } from "express";
import { authMiddleware, AuthRequest } from "./auth";

export function adminMiddleware(req: AuthRequest, res: Response, next: NextFunction) {
  authMiddleware(req, res, () => {
    if (req.user?.nivel_acesso !== "ADMIN") {
      return res.status(403).json({ message: "Acesso restrito a administradores" });
    }
    next();
  });
}
