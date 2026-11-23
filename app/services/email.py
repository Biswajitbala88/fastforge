import logging

logger = logging.getLogger("app.email")


def send_password_reset_email(email: str, reset_link: str) -> None:
    """Deliver a password reset link to the user.

    No email provider is configured yet, so the link is written to the server
    log. Replace this with a real sender (SMTP, SES, SendGrid, ...) before
    going to production.
    """
    logger.warning("Password reset requested for %s. Reset link: %s", email, reset_link)
