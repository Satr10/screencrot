import os
from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import Response
from playwright.async_api import async_playwright
from fastapi.security import APIKeyHeader

app = FastAPI()

# Kunci API yang diharapkan dari environment variable
API_KEY = os.environ.get("API_KEY")
API_KEY_NAME = "X-API-KEY"

api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

async def get_api_key(api_key_header: str = Depends(api_key_header)):
    if not API_KEY:
        raise HTTPException(status_code=500, detail="Kunci API server belum diatur.")
    if api_key_header != API_KEY:
        raise HTTPException(status_code=401, detail="Kunci API tidak valid atau tidak ada.")
    return api_key_header

@app.get("/screenshot")
async def take_screenshot(url: str, api_key: str = Depends(get_api_key)):
    """
    Mengambil tangkapan layar dari URL yang diberikan.
    Membutuhkan header X-API-KEY untuk autentikasi.
    """
    if not url.startswith("http"):
        url = "https://" + url

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--single-process'
            ]
        )
        page = await browser.new_page()
        try:
            await page.goto(url, wait_until="networkidle")
            screenshot_bytes = await page.screenshot(type="png", full_page=True)
        except Exception as e:
            await browser.close()
            raise HTTPException(status_code=500, detail=f"Gagal mengambil tangkapan layar: {str(e)}")
        finally:
            await browser.close()

    return Response(content=screenshot_bytes, media_type="image/png")

@app.get("/")
def read_root():
    return {"message": "API tangkapan layar siap digunakan. Gunakan endpoint /screenshot."}
