"""
Puppeteer/Playwright Browser Automation Service

Headless browser service for web scraping and automation.
Provides REST API for browser control.
"""
import asyncio
import base64
import json
import logging
import os
from typing import Optional

from playwright.async_api import async_playwright, Browser, Page
import uvicorn

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

PORT = int(os.environ.get('PORT', 8080))
AUTH_TOKEN = os.environ.get('AUTH_TOKEN', '')

# Global browser instance
browser: Optional[Browser] = None
page: Optional[Page] = None


async def get_browser() -> Browser:
    """Get or create browser instance."""
    global browser
    if browser is None:
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
        )
    return browser


async def get_page() -> Page:
    """Get or create page instance."""
    global page
    if page is None or page.is_closed():
        b = await get_browser()
        context = await b.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        page = await context.new_page()
    return page


async def handle_action(action: str, params: dict) -> dict:
    """Handle browser action."""
    try:
        p = await get_page()
        
        if action == "navigate":
            url = params.get("url")
            await p.goto(url, wait_until="domcontentloaded", timeout=30000)
            return {"success": True, "url": p.url, "title": await p.title()}
        
        elif action == "screenshot":
            full_page = params.get("full_page", False)
            screenshot = await p.screenshot(full_page=full_page)
            return {"success": True, "screenshot": base64.b64encode(screenshot).decode()}
        
        elif action == "click":
            selector = params.get("selector")
            await p.click(selector, timeout=10000)
            return {"success": True, "clicked": selector}
        
        elif action == "type":
            selector = params.get("selector")
            text = params.get("text")
            await p.fill(selector, text)
            return {"success": True, "typed": text, "into": selector}
        
        elif action == "get_text":
            selector = params.get("selector")
            if selector:
                element = await p.query_selector(selector)
                if element:
                    text = await element.text_content()
                    return {"success": True, "text": text}
                return {"success": False, "error": "Element not found"}
            else:
                text = await p.content()
                return {"success": True, "html": text[:50000]}  # Limit size
        
        elif action == "eval":
            script = params.get("script")
            result = await p.evaluate(script)
            return {"success": True, "result": result}
        
        elif action == "wait":
            selector = params.get("selector")
            timeout = params.get("timeout", 10000)
            await p.wait_for_selector(selector, timeout=timeout)
            return {"success": True, "found": selector}
        
        elif action == "scroll":
            direction = params.get("direction", "down")
            amount = params.get("amount", 500)
            if direction == "down":
                await p.evaluate(f"window.scrollBy(0, {amount})")
            elif direction == "up":
                await p.evaluate(f"window.scrollBy(0, -{amount})")
            return {"success": True, "scrolled": direction}
        
        elif action == "select":
            selector = params.get("selector")
            value = params.get("value")
            await p.select_option(selector, value)
            return {"success": True, "selected": value}
        
        elif action == "pdf":
            pdf = await p.pdf()
            return {"success": True, "pdf": base64.b64encode(pdf).decode()}
        
        elif action == "cookies":
            cookies = await p.context.cookies()
            return {"success": True, "cookies": cookies}
        
        elif action == "close":
            global page
            if page:
                await page.close()
                page = None
            return {"success": True, "closed": True}
        
        else:
            return {"success": False, "error": f"Unknown action: {action}"}
    
    except Exception as e:
        logger.exception(f"Error in {action}")
        return {"success": False, "error": str(e)}


async def send_response(send, status: int, body: bytes, content_type: bytes = b"application/json"):
    """Send HTTP response."""
    headers = [
        [b"content-type", content_type],
        [b"access-control-allow-origin", b"*"],
        [b"access-control-allow-methods", b"GET, POST, OPTIONS"],
        [b"access-control-allow-headers", b"*"],
    ]
    await send({"type": "http.response.start", "status": status, "headers": headers})
    await send({"type": "http.response.body", "body": body})


def check_auth(scope) -> bool:
    """Check authentication."""
    if not AUTH_TOKEN:
        return True
    headers = dict(scope.get("headers", []))
    auth = headers.get(b"authorization", b"").decode()
    return auth == f"Bearer {AUTH_TOKEN}"


async def app(scope, receive, send):
    """Main ASGI application."""
    if scope["type"] != "http":
        return
    
    path = scope["path"]
    method = scope["method"]
    
    # CORS preflight
    if method == "OPTIONS":
        await send_response(send, 204, b"")
        return
    
    # Health check
    if path == "/health":
        await send_response(send, 200, json.dumps({"status": "healthy", "version": "1.0"}).encode())
        return
    
    # Action endpoint
    if path == "/action" and method == "POST":
        if not check_auth(scope):
            await send_response(send, 401, b'{"error":"Unauthorized"}')
            return
        
        body = b""
        while True:
            message = await receive()
            body += message.get("body", b"")
            if not message.get("more_body"):
                break
        
        try:
            data = json.loads(body.decode())
            action = data.get("action", "")
            params = {k: v for k, v in data.items() if k != "action"}
            result = await handle_action(action, params)
            await send_response(send, 200, json.dumps(result).encode())
        except Exception as e:
            await send_response(send, 500, json.dumps({"error": str(e)}).encode())
        return
    
    # Info
    if path == "/":
        await send_response(send, 200, json.dumps({
            "name": "juggernaut-puppeteer",
            "version": "1.0",
            "actions": ["navigate", "screenshot", "click", "type", "get_text", "eval", "wait", "scroll", "select", "pdf", "cookies", "close"]
        }).encode())
        return
    
    await send_response(send, 404, b'{"error":"Not found"}')


if __name__ == "__main__":
    logger.info(f"Starting Puppeteer service on port {PORT}")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
