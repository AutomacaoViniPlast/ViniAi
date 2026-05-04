import nodemailer from "nodemailer";

function getTransporter() {
  const { SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS } = process.env;

  if (!SMTP_HOST || !SMTP_PORT || !SMTP_USER || !SMTP_PASS) {
    throw new Error("Configurações SMTP ausentes no .env (SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS)");
  }

  return nodemailer.createTransport({
    host: SMTP_HOST,
    port: Number(SMTP_PORT),
    secure: Number(SMTP_PORT) === 465,
    auth: { user: SMTP_USER, pass: SMTP_PASS },
  });
}

export async function sendPasswordResetEmail(
  toEmail: string,
  nomeUsuario: string,
  resetToken: string
): Promise<void> {
  const frontendUrl = process.env.FRONTEND_URL || "http://viniai.viniplast.local:3003";
  const resetLink = `${frontendUrl}/reset-password?token=${resetToken}`;
  const from = process.env.SMTP_FROM || process.env.SMTP_USER;

  const transporter = getTransporter();

  await transporter.sendMail({
    from: `"ViniAI" <${from}>`,
    to: toEmail,
    subject: "Redefinição de senha — ViniAI",
    html: `
      <div style="font-family:sans-serif;max-width:480px;margin:0 auto;padding:24px">
        <h2 style="margin-bottom:8px">Redefinição de senha</h2>
        <p>Olá, <strong>${nomeUsuario}</strong>.</p>
        <p>Recebemos uma solicitação para redefinir a senha da sua conta no ViniAI.</p>
        <p style="margin:24px 0">
          <a href="${resetLink}"
             style="background:#e53935;color:#fff;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:600">
            Redefinir senha
          </a>
        </p>
        <p style="color:#888;font-size:13px">Este link expira em <strong>1 hora</strong>.<br>
        Se você não solicitou a redefinição, ignore este e-mail.</p>
      </div>
    `,
  });
}
