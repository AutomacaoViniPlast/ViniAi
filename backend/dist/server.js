"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const express_1 = __importDefault(require("express"));
const cors_1 = __importDefault(require("cors"));
const dotenv_1 = __importDefault(require("dotenv"));
const auth_1 = __importDefault(require("./routes/auth"));
dotenv_1.default.config();
const app = (0, express_1.default)();
app.use((0, cors_1.default)({
    origin: "http://localhost:3001",
}));
app.use(express_1.default.json());
app.get("/health", (_req, res) => {
    res.json({ ok: true });
});
app.use("/auth", auth_1.default);
const PORT = Number(process.env.PORT || 4000);
app.listen(PORT, "0.0.0.0", () => {
    console.log(`API rodando na porta ${PORT}`);
});
