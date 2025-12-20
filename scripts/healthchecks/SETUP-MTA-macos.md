# macOS MTA Setup for Healthcheck Email Notifications

To enable email notifications from healthcheck scripts on macOS, you need a working Mail Transfer Agent (MTA). The simplest option is to use `msmtp` for SMTP relay.

## Steps
1. Install msmtp:
   brew install msmtp

2. Create ~/.msmtprc with your SMTP credentials:

   account default
   host smtp.example.com
   port 587
   from your@email.com
   auth on
   user your@email.com
   password yourpassword
   tls on
   tls_trust_file /etc/ssl/cert.pem

3. Set permissions:
   chmod 600 ~/.msmtprc

4. Install mailutils:
   brew install mailutils

5. Configure mailutils to use msmtp:
   echo 'set sendmail="/usr/local/bin/msmtp"' > ~/.mailrc

6. Test email:
   echo "Test" | mail -s "Test Subject" your@email.com

## Notes
- Update healthcheck scripts to use `mail` for notifications.
- Ensure SMTP credentials are correct and your provider allows relay.
- For advanced setups, consider using Postfix or integrating with a cloud email API.
