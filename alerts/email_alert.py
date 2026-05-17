from __future__ import annotations

import aiosmtplib
from email.message import EmailMessage


class EmailAlert:
    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        username: str,
        app_password: str,
        sender: str,
        receiver: str,
    ) -> None:
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.username = username
        self.app_password = app_password
        self.sender = sender
        self.receiver = receiver

    async def send(self, subject: str, message: str) -> None:
        if not self.username or not self.app_password or not self.sender or not self.receiver:
            return

        email_message = EmailMessage()
        email_message["From"] = self.sender
        email_message["To"] = self.receiver
        email_message["Subject"] = subject
        email_message.set_content(message)

        await aiosmtplib.send(
            email_message,
            hostname=self.smtp_host,
            port=self.smtp_port,
            username=self.username,
            password=self.app_password,
            start_tls=True,
            timeout=20,
        )
