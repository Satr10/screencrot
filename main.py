# main.py

import os
import asyncio
from typing import Literal, Optional

from fastapi import FastAPI, Depends, HTTPException, Security
from fastapi.responses import Response, JSONResponse
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field, HttpUrl
from playwright.async_api import async_playwright, Error

# --- API Key Setup ---
API_KEY = os.environ.get("API_KEY")
API_KEY_NAME = "X-API-KEY"
api_key_header_scheme = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

# No longer using a global browser instance or lifespan manager
app = FastAPI(
    title="Screenshot API 📸",
    description="A high-performance API to take screenshots of web pages using FastAPI and Playwright.",
)

# --- Dependency for API Key Validation ---
async def get_api_key(api_key_header: str = Security(api_key_header_scheme)):
    if not API_KEY:
        raise HTTPException(status_code=500, detail="API key not configured on the server.")
    if api_key_header != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API Key.")
    return api_key_header

# --- Pydantic Model for Input Validation ---
class ScreenshotParams(BaseModel):
    url: HttpUrl = Field(..., description="The full URL of the website to capture.")
    width: int = Field(1920, gt=0, le=3840, description="Viewport width in pixels.")
    height: int = Field(1080, gt=0, le=2160, description="Viewport height in pixels.")
    full_page: bool = Field(False, description="Capture the full scrollable page.")
    format: Literal['jpeg', 'png', 'webp'] = Field('jpeg', description="Output image format.")
    quality: Optional[int] = Field(80, ge=1, le=100, description="Image quality (1-100) for JPEG and WebP.")
    delay: int = Field(0, ge=0, le=10000, description="Delay in milliseconds after page load before screenshot.")

# --- API Endpoint (Now uses request-scoped browser) ---
@app.get(
    "/screenshot",
    summary="Take a Screenshot of a URL",
    description="Captures a screenshot of a given web page. **Requires API key.**",
    tags=["Screenshot"],
)
async def take_screenshot(
    params: ScreenshotParams = Depends(),
    api_key: str = Depends(get_api_key) # Dependency to protect the endpoint
):
    """
    Launches a new browser for each request, takes a screenshot, and then closes it.
    This is more stable for serverless environments.
    """
    async with async_playwright() as p:
        browser = None
        try:
            # Launch a new browser instance for this request
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-gpu"]
            )
            
            context = await browser.new_context(
                viewport={'width': params.width, 'height': params.height},
                device_scale_factor=2,
            )
            page = await context.new_page()
            await page.goto(str(params.url), wait_until="networkidle", timeout=30000)

            if params.delay > 0:
                await asyncio.sleep(params.delay / 1000)

            screenshot_args = {
                "type": params.format,
                "full_page": params.full_page,
            }
            if params.format in ['jpeg', 'webp']:
                screenshot_args["quality"] = params.quality

            screenshot_bytes = await page.screenshot(**screenshot_args)
            media_type = f"image/{params.format}"
            return Response(content=screenshot_bytes, media_type=media_type)

        except Error as e:
            error_message = f"Failed to process the page: {e}"
            return JSONResponse(status_code=500, content={"error": error_message})
        except Exception as e:
            return JSONResponse(status_code=500, content={"error": f"An unexpected error occurred: {str(e)}"})
        finally:
            # Ensure the browser is closed to free up resources
            if browser:
                await browser.close()

@app.get("/", include_in_schema=False)
async def root():
    return {"message": "Screenshot API is running. Visit /docs for documentation."}
