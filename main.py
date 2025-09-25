# main.py
#
# To run this application:
# 1. Set the API_KEY environment variable:
#    export API_KEY='your_super_secret_key'
#
# 2. Install dependencies:
#    pip install -r requirements.txt
#
# 3. Install Playwright's browser binaries (only needs to be done once):
#    playwright install chromium
#
# 4. Start the server:
#    uvicorn main:app --host 0.0.0.0 --port 8000

import os
import asyncio
from typing import Literal, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, Query, Security
from fastapi.responses import Response, JSONResponse
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field, HttpUrl
from playwright.async_api import async_playwright, Browser, Error

# --- API Key Setup ---
API_KEY = os.environ.get("API_KEY")
API_KEY_NAME = "X-API-KEY"
api_key_header_scheme = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

# --- Global State for Browser Management ---
playwright_state = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    # On startup, launch the browser and store it in the state.
    print("🚀 Starting browser...")
    p = await async_playwright().start()
    
    # --- THIS IS THE MODIFIED LINE ---
    # Add '--no-sandbox' and '--disable-gpu' arguments for compatibility with serverless/container environments.
    browser = await p.chromium.launch(
        headless=True,
        args=[
                '--single-process',
                '--no-sandbox',
                '--disable-setuid-sandbox',
            ]
    )
    # ---------------------------------
    
    playwright_state["browser"] = browser
    playwright_state["playwright"] = p
    print("✅ Browser started successfully.")
    yield
    # On shutdown, close the browser and stop Playwright.
    print("🌙 Closing browser...")
    await playwright_state["browser"].close()
    await playwright_state["playwright"].stop()
    print("✅ Browser closed successfully.")

app = FastAPI(
    title="Screenshot API 📸",
    description="A high-performance API to take screenshots of web pages using FastAPI and Playwright.",
    lifespan=lifespan,
)

# --- Dependency for API Key Validation ---
async def get_api_key(api_key_header: str = Security(api_key_header_scheme)):
    """Dependency to validate the API key from the X-API-KEY header."""
    if not API_KEY:
        raise HTTPException(
            status_code=500, 
            detail="API key not configured on the server."
        )
    if api_key_header != API_KEY:
        raise HTTPException(
            status_code=401, 
            detail="Invalid or missing API Key."
        )
    return api_key_header

# --- Pydantic Model for Input Validation ---
class ScreenshotParams(BaseModel):
    """Pydantic model for validating query parameters."""
    url: HttpUrl = Field(..., description="The full URL of the website to capture.")
    width: int = Field(1920, gt=0, le=3840, description="Viewport width in pixels.")
    height: int = Field(1080, gt=0, le=2160, description="Viewport height in pixels.")
    full_page: bool = Field(False, description="Capture the full scrollable page.")
    format: Literal['jpeg', 'png', 'webp'] = Field('jpeg', description="Output image format.")
    quality: Optional[int] = Field(80, ge=1, le=100, description="Image quality (1-100) for JPEG and WebP.")
    delay: int = Field(0, ge=0, le=10000, description="Delay in milliseconds after page load before screenshot.")

# --- Dependency to Get Browser Instance ---
async def get_browser() -> Browser:
    """Dependency to provide the browser instance to the route."""
    if "browser" not in playwright_state or not playwright_state["browser"].is_connected():
         raise HTTPException(
            status_code=503,
            detail="Browser is not available or has disconnected."
        )
    return playwright_state["browser"]

# --- API Endpoint (Now Protected) ---
@app.get(
    "/screenshot",
    summary="Take a Screenshot of a URL",
    description="Captures a screenshot of a given web page with customizable options. **Requires API key.**",
    tags=["Screenshot"],
    responses={
        200: {
            "description": "Successful screenshot.",
            "content": {"image/jpeg": {}, "image/png": {}, "image/webp": {}},
        },
        401: {"description": "Invalid or missing API Key."},
        400: {"description": "Invalid input parameters."},
        500: {"description": "Internal server error (e.g., page timeout, navigation error)."},
        503: {"description": "Browser service is not available."},
    },
)
async def take_screenshot(
    params: ScreenshotParams = Depends(),
    browser: Browser = Depends(get_browser),
    api_key: str = Depends(get_api_key) # This dependency protects the endpoint
):
    """
    Takes a screenshot of a given URL.
    
    Authentication is required via the X-API-KEY header.
    """
    context = None
    try:
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
        if context:
            await context.close()

@app.get("/", include_in_schema=False)
async def root():
    return {"message": "Screenshot API is running. Visit /docs for documentation."}
