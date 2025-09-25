import os
from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.responses import Response, RedirectResponse
from playwright.async_api import async_playwright, Playwright, Browser
from fastapi.security import APIKeyHeader
from typing import Optional, Literal

app = FastAPI(
    title="Screenshot API",
    description="API to take screenshots of web pages.",
)

# API Key Setup
API_KEY = os.environ.get("API_KEY")
API_KEY_NAME = "X-API-KEY"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

async def get_api_key(api_key_header: str = Depends(api_key_header)):
    if not API_KEY:
        raise HTTPException(status_code=500, detail="Server API key is not set.")
    if api_key_header != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key.")
    return api_key_header

# Browser Management
class BrowserManager:
    def __init__(self):
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None

    async def start_browser(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--single-process'
            ]
        )

    async def stop_browser(self):
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

browser_manager = BrowserManager()

@app.on_event("startup")
async def startup_event():
    await browser_manager.start_browser()

@app.on_event("shutdown")
async def shutdown_event():
    await browser_manager.stop_browser()

async def get_browser() -> Browser:
    if browser_manager.browser is None:
        raise HTTPException(status_code=503, detail="Browser is not available.")
    return browser_manager.browser

@app.get("/screenshot")
async def take_screenshot(
    url: str,
    api_key: str = Depends(get_api_key),
    browser: Browser = Depends(get_browser),
    width: int = Query(1280, description="Screenshot width"),
    height: int = Query(720, description="Screenshot height for the initial viewport"),
    full_page: bool = Query(True, description="Capture the full scrollable page"), # <-- PERUBAHAN DI SINI
    user_agent: Literal['desktop', 'mobile'] = Query('desktop', description="User agent type"),
    quality: int = Query(80, ge=0, le=100, description="Screenshot quality (for JPEG)"),
    wait_until: Literal['load', 'domcontentloaded', 'networkidle', 'commit'] = Query('networkidle', description="Wait until event")
):
    """
    Takes a screenshot of a given URL with customizable options.
    Requires X-API-KEY header for authentication.
    """
    if not url.startswith("http"):
        url = "https://" + url

    user_agent_string = None
    if user_agent == 'mobile':
        user_agent_string = "Mozilla/5.0 (iPhone; CPU iPhone OS 13_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.1.1 Mobile/15E148 Safari/604.1"

    context = await browser.new_context(
        viewport={'width': width, 'height': height},
        user_agent=user_agent_string
    )
    page = await context.new_page()

    try:
        await page.goto(url, wait_until=wait_until)
        # Menggunakan parameter full_page dari query
        screenshot_bytes = await page.screenshot(
            type="jpeg", 
            quality=quality, 
            full_page=full_page # <-- PERUBAHAN DI SINI
        )
    except Exception as e:
        await context.close()
        raise HTTPException(status_code=500, detail=f"Failed to take screenshot: {str(e)}")
    
    await context.close()

    return Response(content=screenshot_bytes, media_type="image/jpeg")

@app.get("/")
def read_root():
    return RedirectResponse(url="/docs")
