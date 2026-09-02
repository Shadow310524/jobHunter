"""Minimal Playwright experiment demonstrating browser lifecycle and text extraction."""

import asyncio
from pathlib import Path

from playwright.async_api import async_playwright


async def extract_sample_job_title(fixture_path: Path, headless: bool = False) -> str:
    """Launch Chromium, load local HTML fixture, and extract the job title.

    Args:
        fixture_path: Absolute or relative Path to the local HTML fixture.
        headless: Whether to run Chromium without a visible window.

    Returns:
        The extracted job title string.
    """
    file_uri = fixture_path.resolve().as_uri()

    async with async_playwright() as p:
        # 1. Launch Browser
        browser = await p.chromium.launch(headless=headless)
        try:
            # 2. Create BrowserContext (isolated session)
            context = await browser.new_context()
            try:
                # 3. Open Page (single tab)
                page = await context.new_page()

                # 4. Navigate to local HTML fixture
                await page.goto(file_uri)

                # 5. Use Locator to target the job title element
                title_locator = page.locator(".job-title")

                # 6. Extract the inner text (with auto-waiting)
                job_title: str = await title_locator.inner_text()

                return job_title.strip()
            finally:
                await context.close()
        finally:
            await browser.close()


async def main() -> None:
    """Entry point for manual headed smoke testing."""
    fixture_path = (
        Path(__file__).resolve().parent.parent.parent / "tests" / "fixtures" / "sample_job.html"
    )
    print(f"Loading local fixture: {fixture_path}")
    print("Launching Chromium in HEADED mode...")

    extracted_title = await extract_sample_job_title(fixture_path, headless=False)

    print("\n--- Extracted Result ---")
    print(f"Job Title: {extracted_title}")
    print("------------------------")


if __name__ == "__main__":
    asyncio.run(main())
