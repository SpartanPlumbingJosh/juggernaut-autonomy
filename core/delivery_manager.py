import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import Dict, Any, Callable

class DeliveryManager:
    def __init__(self):
        self.smtp_host = os.getenv('SMTP_HOST', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', 587))
        self.smtp_user = os.getenv('SMTP_USER')
        self.smtp_password = os.getenv('SMTP_PASSWORD')
        
    async def send_email(self, to: str, subject: str, content: str) -> bool:
        """Send email to customer"""
        try:
            msg = MIMEMultipart()
            msg['From'] = self.smtp_user
            msg['To'] = to
            msg['Subject'] = subject
            
            msg.attach(MIMEText(content, 'html'))
            
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)
            return True
        except Exception as e:
            print(f"Failed to send email: {str(e)}")
            return False

    async def process_delivery(self, execute_sql: Callable[[str], Dict[str, Any]], order_id: str) -> Dict[str, Any]:
        """Process order delivery"""
        try:
            # Get order details
            order = await execute_sql(f"SELECT * FROM orders WHERE id = '{order_id}'")
            if not order.get('rows'):
                return {"success": False, "error": "Order not found"}
            
            order_data = order['rows'][0]
            user_email = order_data['email']
            product_id = order_data['product_id']
            
            # Get product details
            product = await execute_sql(f"SELECT * FROM products WHERE id = '{product_id}'")
            if not product.get('rows'):
                return {"success": False, "error": "Product not found"}
            
            product_data = product['rows'][0]
            
            # Send delivery email
            email_content = f"""
                <h1>Your Order is Ready!</h1>
                <p>Thank you for purchasing {product_data['name']}.</p>
                <p>Here's your download link: <a href="{product_data['download_url']}">Download Now</a></p>
            """
            
            sent = await self.send_email(
                to=user_email,
                subject=f"Your {product_data['name']} is ready",
                content=email_content
            )
            
            if not sent:
                return {"success": False, "error": "Failed to send delivery email"}
            
            # Mark order as delivered
            await execute_sql(f"""
                UPDATE orders SET status = 'delivered', delivered_at = NOW()
                WHERE id = '{order_id}'
            """)
            
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
