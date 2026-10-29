"""Send BrandVerity's account emails (verification, password reset).

Stdlib smtplib only — no new dependencies. Configuration comes from
environment variables, set on the host (Vercel env vars in production):

  SMTP_HOST   e.g. smtp.gmail.com
  SMTP_PORT   465 (SSL) or 587 (STARTTLS)
  SMTP_USER   the sending mailbox
  SMTP_PASS   the mailbox password / app password
  SMTP_FROM   shown sender (defaults to SMTP_USER)
  APP_URL     frontend base used in email links
              (defaults to https://brandverity.vercel.app)

If SMTP_USER/SMTP_PASS are missing, send_email returns False and the
caller tells the user the email could not be sent. Nothing pretends an
email went out when it did not, and no account is left in a state that
depends on an unsent email.
"""

import os
import smtplib
from email.message import EmailMessage


def app_url() -> str:
    return os.environ.get("APP_URL", "https://brandverity.vercel.app").rstrip("/")


def mail_configured() -> bool:
    return bool(os.environ.get("SMTP_USER") and os.environ.get("SMTP_PASS"))


def send_email(to_email: str, subject: str, body: str) -> bool:
    host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    try:
        port = int(os.environ.get("SMTP_PORT", "465"))
    except ValueError:
        port = 465
    user = os.environ.get("SMTP_USER", "")
    password = os.environ.get("SMTP_PASS", "")
    sender = os.environ.get("SMTP_FROM", user)
    if not user or not password:
        print("mailer: SMTP not configured (SMTP_USER/SMTP_PASS missing)")
        return False
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)
    try:
        if port == 465:
            with smtplib.SMTP_SSL(host, port, timeout=20) as smtp:
                smtp.login(user, password)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=20) as smtp:
                smtp.ehlo()
                smtp.starttls()
                smtp.ehlo()
                smtp.login(user, password)
                smtp.send_message(msg)
        return True
    except Exception as exc:  # noqa: BLE001 - email failure must not crash signup
        print(f"mailer: send failed: {exc}")
        return False


def send_verification_email(to_email: str, link: str) -> bool:
    return send_email(
        to_email,
        "Verify your BrandVerity account",
        f"Welcome to BrandVerity.\n\n"
        f"Click the link below to verify your email and activate your account:\n"
        f"{link}\n\n"
        f"The link expires in 24 hours. If you did not sign up, ignore this email.\n",
    )


def send_reset_email(to_email: str, link: str) -> bool:
    return send_email(
        to_email,
        "Reset your BrandVerity password",
        f"Someone asked to reset the password for this BrandVerity account.\n\n"
        f"Click the link below to choose a new password:\n"
        f"{link}\n\n"
        f"The link expires in 1 hour. If you did not ask for this, ignore this email.\n",
    )
