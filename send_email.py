import argparse
import os
import smtplib
import ssl
from email.message import EmailMessage

from dotenv import load_dotenv


SMTP_SERVER = "smtp.centredelama.com"
SMTP_PORT = 587  # TLS (STARTTLS)
TEST_EMAIL = "nilpalaub@gmail.com"
DEFAULT_TEMPLATE_PATH = os.path.join(
    os.path.dirname(__file__), "email_template.html"
)


def load_credentials() -> tuple[str, str]:
    """
    Load SMTP credentials from environment variables.

    Expected variables (can be set in a .env file):
      - SMTP_USER
      - SMTP_PASSWORD
    """
    load_dotenv()

    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASSWORD")

    if not user or not password:
        raise RuntimeError(
            "Missing SMTP_USER or SMTP_PASSWORD. "
            "Set them in a .env file or the environment."
        )

    return user, password


def build_message(subject: str, sender: str, recipient: str, html_body: str) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient
    msg.set_content("This email requires an HTML-capable client.")
    msg.add_alternative(html_body, subtype="html")
    return msg


def send_email(recipient: str, subject: str, html_body: str) -> None:
    user, password = load_credentials()
    msg = build_message(subject=subject, sender=user, recipient=recipient, html_body=html_body)

    context = ssl.create_default_context()

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.ehlo()
        server.starttls(context=context)
        server.ehlo()
        server.login(user, password)
        server.send_message(msg)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Send an email via SMTP with TLS and an HTML body."
    )

    parser.add_argument(
        "--to",
        dest="to_email",
        help="Recipient email address (ignored when --test-email is used).",
    )
    parser.add_argument(
        "--subject",
        default="I Curso de Neuropatías por Atrapamiento – 6 plazas disponibles",
        help="Email subject. Default: %(default)s",
    )
    parser.add_argument(
        "--html",
        dest="html_body",
        help="Custom HTML body. If omitted, a default 'nice' HTML template is used.",
    )
    parser.add_argument(
        "--test-email",
        action="store_true",
        help=f"Send to test email address: {TEST_EMAIL}",
    )

    return parser.parse_args()


def default_html_body() -> str:
    with open(DEFAULT_TEMPLATE_PATH, "r", encoding="utf-8") as f:
        return f.read()


def main() -> None:
    args = parse_args()

    if args.test_email:
        recipient = TEST_EMAIL
    else:
        if not args.to_email:
            raise SystemExit(
                "Error: --to is required when --test-email is not used."
            )
        recipient = args.to_email

    subject = args.subject
    html_body = args.html_body if args.html_body else default_html_body()

    send_email(recipient=recipient, subject=subject, html_body=html_body)
    print(f"Email sent to {recipient}")


if __name__ == "__main__":
    main()

