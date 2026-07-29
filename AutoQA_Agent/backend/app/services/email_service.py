"""
EmailService — sends AutoQA analysis reports as PDF email attachments.

Uses Python's built-in smtplib + email.mime stack (zero new dependencies).
Transport: Gmail SMTP over STARTTLS (smtp.gmail.com:587).

Setup required
--------------
1. Enable 2-Step Verification on your Google account:
   https://myaccount.google.com/security

2. Generate an App Password (16-character code Google creates for you):
   https://myaccount.google.com/apppasswords
   Choose App = "Mail", Device = "Other" → give it a name like "AutoQA"

3. Set in backend/.env:
   EMAIL_SENDER_ADDRESS=your-address@gmail.com
   EMAIL_SENDER_APP_PASSWORD=xxxx xxxx xxxx xxxx  (the 16-char App Password)

   ⚠ Regular Gmail passwords will NOT work — Google requires App Passwords for
   third-party SMTP access when 2-Step Verification is enabled.

Failure modes
-------------
- `EmailNotConfiguredError`  : raised when sender address/password are missing in .env
- `EmailAuthError`           : raised on SMTP AUTH failure (wrong App Password)
- `EmailSendError`           : raised on any other SMTP / network error
All errors carry a human-readable `.detail` attribute for forwarding to the API response.
"""
from __future__ import annotations

import logging
import smtplib
import ssl
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


from app.core.config import settings

logger = logging.getLogger(__name__)

_GMAIL_HOST = "smtp.gmail.com"
_GMAIL_PORT = 587          # STARTTLS


# ── Custom exceptions ────────────────────────────────────────────────────────


class EmailNotConfiguredError(Exception):
    """EMAIL_SENDER_ADDRESS or EMAIL_SENDER_APP_PASSWORD are not set in .env."""
    detail = (
        "Email is not configured on this server. "
        "Set EMAIL_SENDER_ADDRESS and EMAIL_SENDER_APP_PASSWORD in backend/.env. "
        "See the README for Gmail App Password setup instructions."
    )


class EmailAuthError(Exception):
    """SMTP authentication failed — wrong or expired App Password."""
    def __init__(self, smtp_detail: str = "") -> None:
        hint = (
            "Make sure you are using a Gmail App Password (not your regular Gmail password). "
            "Generate one at https://myaccount.google.com/apppasswords"
        )
        self.detail = (
            f"SMTP authentication failed — {smtp_detail}. {hint}"
            if smtp_detail
            else f"SMTP authentication failed. {hint}"
        )
        super().__init__(self.detail)


class EmailSendError(Exception):
    """Any other SMTP or network error during send."""
    def __init__(self, cause: str) -> None:
        self.detail = f"Email could not be sent: {cause}"
        super().__init__(self.detail)


# ── Public API ───────────────────────────────────────────────────────────────


def send_report_email(to_email: str, repo_name: str, pdf_bytes: bytes) -> bool:
    """
    Send ``pdf_bytes`` as a PDF attachment to ``to_email``.

    Parameters
    ----------
    to_email   : recipient email address (validated by the caller / Pydantic)
    repo_name  : repository name shown in subject + body (display only)
    pdf_bytes  : raw bytes of the generated PDF report

    Returns
    -------
    True on success.

    Raises
    ------
    EmailNotConfiguredError  – SMTP credentials missing from .env
    EmailAuthError           – wrong App Password
    EmailSendError           – any other transport / SMTP error
    """
    sender   = (settings.email_sender_address or "").strip()
    # Gmail App Passwords are 16 alphanumeric chars; Google displays them
    # with spaces for readability but smtplib must receive the bare token.
    password = (settings.email_sender_app_password or "").replace(" ", "").strip()

    if not sender or not password:
        logger.error("EmailService: EMAIL_SENDER_ADDRESS or EMAIL_SENDER_APP_PASSWORD not set")
        raise EmailNotConfiguredError()

    logger.debug("EmailService: using sender=%s, password_len=%d", sender, len(password))

    # ── Compose message ───────────────────────────────────────────────────────
    msg = MIMEMultipart()
    msg["From"]    = f"AutoQA Agent <{sender}>"
    msg["To"]      = to_email
    msg["Subject"] = f"AutoQA Report — {repo_name}"

    body = (
        f"Hi,\n\n"
        f"Attached is your AutoQA Agent analysis report for the repository:\n"
        f"  {repo_name}\n\n"
        f"The report includes tech stack detection, API inventory, dependency graph,\n"
        f"code insights, bug detection results, and AI-generated architectural notes.\n\n"
        f"— AutoQA Agent"
    )
    msg.attach(MIMEText(body, "plain"))

    # ── Attach PDF ────────────────────────────────────────────────────────────
    safe_name  = repo_name.replace("/", "_").replace(" ", "_")
    attachment = MIMEApplication(pdf_bytes, _subtype="pdf")
    attachment.add_header(
        "Content-Disposition",
        "attachment",
        filename=f"autoqa-{safe_name}.pdf",
    )
    msg.attach(attachment)

    # ── Send via Gmail SMTP ──────────────────────────────────────────────────
    # Try port 465 (SMTP_SSL, direct TLS) first — most commonly open through
    # firewalls/ISPs. Fall back to port 587 (STARTTLS) if 465 times out.
    last_exc: Exception | None = None

    for port, use_ssl in [(465, True), (587, False)]:
        logger.info("EmailService: trying %s:%d (%s)", _GMAIL_HOST, port, "SSL" if use_ssl else "STARTTLS")
        try:
            if use_ssl:
                ctx = ssl.create_default_context()
                smtp_cls = smtplib.SMTP_SSL(_GMAIL_HOST, port, timeout=10, context=ctx)
            else:
                smtp_cls = smtplib.SMTP(_GMAIL_HOST, port, timeout=10)

            with smtp_cls as smtp:
                if not use_ssl:
                    smtp.ehlo()
                    smtp.starttls()
                smtp.ehlo()
                try:
                    smtp.login(sender, password)
                except smtplib.SMTPAuthenticationError as exc:
                    raw = exc.smtp_error.decode(errors="replace") if isinstance(exc.smtp_error, bytes) else str(exc)
                    logger.error(
                        "EmailService: SMTP auth failed (port %d) sender=%s — code=%s detail=%s",
                        port, sender, exc.smtp_code, raw,
                    )
                    raise EmailAuthError(smtp_detail=raw.strip()) from exc

                smtp.sendmail(sender, to_email, msg.as_bytes())
                logger.info(
                    "EmailService: report sent to %s for repo '%s' via port %d",
                    to_email, repo_name, port,
                )
                return True

        except (EmailAuthError, EmailNotConfiguredError):
            raise   # auth errors are definitive — no point trying next port
        except smtplib.SMTPRecipientsRefused as exc:
            raise EmailSendError(f"Recipient address refused by server: {to_email}") from exc
        except OSError as exc:
            # TimeoutError, ConnectionRefusedError, socket errors — try next port
            logger.warning("EmailService: port %d failed (%s: %s) — trying next port", port, type(exc).__name__, exc)
            last_exc = exc
            continue
        except smtplib.SMTPException as exc:
            logger.warning("EmailService: port %d SMTP error (%s) — trying next port", port, exc)
            last_exc = exc
            continue

    # Both ports exhausted
    raise EmailSendError(
        f"Could not connect to Gmail SMTP on ports 465 or 587. "
        f"This is usually a network/firewall issue. Last error: {last_exc}"
    )
