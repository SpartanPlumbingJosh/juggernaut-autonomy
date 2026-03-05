from datetime import datetime, timedelta
from typing import Dict, Optional
import logging
import smtplib
from email.mime.text import MIMEText
from core.database import query_db

class RevenueAlerts:
    def __init__(self):
        self.daily_threshold = 1000000  # $10,000 in cents
        self.weekly_threshold = 5000000  # $50,000 in cents
        self.email_config = {
            "smtp_server": "smtp.example.com",
            "smtp_port": 587,
            "sender": "alerts@revenue.com",
            "recipients": ["team@revenue.com"]
        }

    async def check_daily_threshold(self):
        """Check if daily revenue exceeds threshold."""
        try:
            today = datetime.utcnow().date()
            sql = f"""
            SELECT SUM(amount_cents) as total 
            FROM revenue_events 
            WHERE event_type = 'revenue' 
            AND recorded_at >= '{today.isoformat()}'
            """
            result = await query_db(sql)
            total = result.get("rows", [{}])[0].get("total", 0)
            
            if total > self.daily_threshold:
                await self.send_alert(
                    subject="Daily Revenue Threshold Exceeded",
                    message=f"Daily revenue reached {total/100:.2f} USD"
                )
        except Exception as e:
            logging.error(f"Failed to check daily threshold: {str(e)}")

    async def check_weekly_threshold(self):
        """Check if weekly revenue exceeds threshold."""
        try:
            week_start = datetime.utcnow() - timedelta(days=7)
            sql = f"""
            SELECT SUM(amount_cents) as total 
            FROM revenue_events 
            WHERE event_type = 'revenue' 
            AND recorded_at >= '{week_start.isoformat()}'
            """
            result = await query_db(sql)
            total = result.get("rows", [{}])[0].get("total", 0)
            
            if total > self.weekly_threshold:
                await self.send_alert(
                    subject="Weekly Revenue Threshold Exceeded",
                    message=f"Weekly revenue reached {total/100:.2f} USD"
                )
        except Exception as e:
            logging.error(f"Failed to check weekly threshold: {str(e)}")

    async def send_alert(self, subject: str, message: str):
        """Send email alert."""
        try:
            msg = MIMEText(message)
            msg['Subject'] = subject
            msg['From'] = self.email_config['sender']
            msg['To'] = ', '.join(self.email_config['recipients'])

            with smtplib.SMTP(
                self.email_config['smtp_server'], 
                self.email_config['smtp_port']
            ) as server:
                server.starttls()
                server.login(self.email_config['sender'], "password")
                server.sendmail(
                    self.email_config['sender'],
                    self.email_config['recipients'],
                    msg.as_string()
                )
        except Exception as e:
            logging.error(f"Failed to send alert: {str(e)}")
