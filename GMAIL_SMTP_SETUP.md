# Gmail SMTP Setup Guide

## 1) Enable 2-Step Verification

In Google Account security settings, enable 2FA.

## 2) Create App Password

1. Go to Google Account -> Security -> App Passwords
2. Generate app password for "Mail"
3. Copy 16-character password

## 3) Update `.env`

```text
EMAIL_ENABLED=true
EMAIL_SMTP_HOST=smtp.gmail.com
EMAIL_SMTP_PORT=587
EMAIL_USERNAME=your_email@gmail.com
EMAIL_APP_PASSWORD=your_16_char_app_password
EMAIL_FROM=your_email@gmail.com
EMAIL_TO=destination_email@gmail.com
```

## 4) Test

Start the bot and wait for first signal. The bot sends email with all strategy fields.

## Notes

- Use app password, not your normal Gmail password
- Ensure sender and username are valid Gmail accounts
