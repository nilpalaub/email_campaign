import argparse
import csv
import os
import random
import smtplib
import ssl
import time
from email.message import EmailMessage
from typing import List

from dotenv import load_dotenv


SMTP_SERVER = "smtp.centredelama.com"
SMTP_PORT = 587  # TLS (STARTTLS)
PER_EMAIL_SLEEP_RANGE = (1.0, 3.0)  # seconds, used in --execute mode
BATCH_SIZE = 100  # extra pause every N successful sends
BATCH_PAUSE_SECONDS = 30  # seconds
PROGRAM_FILENAME = (
    "PROGRAMA: I Curso de Neuropatías por Atrapamiento de la extremidad superior.pdf"
)
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


def attach_program_pdf(msg: EmailMessage) -> None:
    """
    Attach the course program PDF to the email if the file exists
    alongside this script.
    """
    program_path = os.path.join(os.path.dirname(__file__), PROGRAM_FILENAME)
    if not os.path.exists(program_path):
        return

    with open(program_path, "rb") as f:
        data = f.read()

    msg.add_attachment(
        data,
        maintype="application",
        subtype="pdf",
        filename=PROGRAM_FILENAME,
    )


def load_recipients_from_csv(csv_path: str) -> List[str]:
    """
    Load recipient email addresses from a CSV file.

    Expects a header row and will first look for an 'Email 1' column,
    falling back to the first column whose name contains 'email'.
    """
    recipients: List[str] = []

    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise RuntimeError("CSV file has no header row.")

        fieldnames_lower = [name.lower() for name in reader.fieldnames]
        email_col = None

        # Prefer an exact 'Email 1' match (case-insensitive)
        for name in reader.fieldnames:
            if name.lower() == "email 1":
                email_col = name
                break

        # Otherwise, fall back to the first header containing 'email'
        if email_col is None:
            for name in reader.fieldnames:
                if "email" in name.lower():
                    email_col = name
                    break

        if email_col is None:
            raise RuntimeError(
                "Could not find an email column in the CSV. "
                "Expected a column named 'Email 1' or similar."
            )

        for row in reader:
            value = (row.get(email_col) or "").strip()
            if value:
                recipients.append(value)

    return recipients


def send_email(recipient: str, subject: str, html_body: str) -> None:
    user, password = load_credentials()
    msg = build_message(subject=subject, sender=user, recipient=recipient, html_body=html_body)
    attach_program_pdf(msg)

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
        "--execute",
        metavar="CSV",
        help="Send the campaign email to all contacts in this CSV file.",
    )
    parser.add_argument(
        "--dry-run",
        metavar="CSV",
        help="Read contacts from this CSV file and show what would be sent, without actually sending emails.",
    )
    parser.add_argument(
        "--test-email",
        metavar="EMAIL",
        help="Send a test email to this address (e.g. --test-email you@example.com).",
    )

    return parser.parse_args()


def default_html_body() -> str:
    with open(DEFAULT_TEMPLATE_PATH, "r", encoding="utf-8") as f:
        return f.read()


def main() -> None:
    args = parse_args()

    if args.execute and args.dry_run:
        raise SystemExit("Error: --execute and --dry-run cannot be used together.")

    subject = args.subject
    html_body = args.html_body if args.html_body else default_html_body()

    # Bulk modes using CSV
    if args.execute or args.dry_run:
        csv_path = args.execute or args.dry_run
        recipients = load_recipients_from_csv(csv_path)

        if not recipients:
            raise SystemExit(f"No valid email addresses found in CSV: {csv_path}")

        if args.dry_run:
            print(f"[DRY RUN] Would send email to {len(recipients)} contacts from '{csv_path}':")
            for email in recipients:
                print(f" - {email}")
            print("\nSubject:")
            print(f"  {subject}")
            print("\nHTML body is loaded from the template and will be used as-is.")
            return

        # Execute mode: actually send to all contacts
        print(f"[EXECUTE] Sending email to {len(recipients)} contacts from '{csv_path}'...")
        sent = 0
        for email in recipients:
            try:
                send_email(recipient=email, subject=subject, html_body=html_body)
                sent += 1
                print(f"Sent to: {email}")
                # Gentle throttling between sends to reduce spam/abuse flags
                time.sleep(random.uniform(*PER_EMAIL_SLEEP_RANGE))

                # Extra pause every batch of successfully sent emails
                if sent % BATCH_SIZE == 0 and sent < len(recipients):
                    print(f"Pausing {BATCH_PAUSE_SECONDS} seconds after {sent} emails...")
                    time.sleep(BATCH_PAUSE_SECONDS)
            except Exception as exc:  # noqa: BLE001
                print(f"Error sending to {email}: {exc}")

        print(f"Finished sending. Successfully sent to {sent} of {len(recipients)} contacts.")
        return

    # Single-recipient modes
    if args.test_email:
        recipient = args.test_email
    else:
        if not args.to_email:
            raise SystemExit(
                "Error: one of --to, --test-email, --execute, or --dry-run is required."
            )
        recipient = args.to_email

    send_email(recipient=recipient, subject=subject, html_body=html_body)
    print(f"Email sent to {recipient}")


if __name__ == "__main__":
    main()

