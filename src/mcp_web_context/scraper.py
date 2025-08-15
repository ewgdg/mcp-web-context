from contextlib import asynccontextmanager
import math
from pathlib import Path
import random
import traceback
from typing_extensions import Literal
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from typing import Any, Dict, cast, Tuple, Optional, AsyncGenerator, Set
import asyncio
import logging
import json
from patchright.async_api import Browser, BrowserContext, Page

from .utils import (
    get_relevant_images,
    extract_title,
    get_text_from_soup,
    get_markdown_from_soup,
    clean_soup,
)


class Scraper:
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    max_browsers: int = 3
    browser_load_threshold: int = 5
    contexts: Set["Scraper.Context"] = set()
    contexts_lock: asyncio.Lock = asyncio.Lock()
    _shared_driver: Optional[Any] = None
    _shared_browser: Optional[Browser] = None

    @staticmethod
    def get_domain(url: str) -> str:
        domain = urlparse(url=url).netloc
        parts = domain.split(".")
        if len(parts) > 2:
            domain = ".".join(parts[-2:])
        return domain

    @staticmethod
    def normalize_url(url: str) -> str:
        parsed = urlparse(url)
        if not parsed.scheme:
            return "https://" + url
        return url

    class Context:
        def __init__(self, context: BrowserContext) -> None:
            self.context: BrowserContext = context
            self.processing_count: int = 0
            self.has_blank_page: bool = True
            self.allowed_requests_times: Dict[str, float] = {}
            self.domain_semaphores: Dict[str, asyncio.Semaphore] = {}
            self.tab_mode: bool = True
            self.max_scroll_percent: int = 500
            self.stopping: bool = False

        async def _ensure_browser(self) -> None:
            """Browser context is already initialized in constructor"""
            pass

        async def get(self, url: str) -> Page:
            self.processing_count += 1
            try:
                async with self.rate_limit_for_domain(url):
                    await self._ensure_browser()
                    page = await self.context.new_page()
                    await page.goto(url)
                    self.has_blank_page = False
                    return page
            except Exception:
                self.processing_count -= 1
                raise

        async def scroll_page_to_bottom(self, page: Page) -> None:
            total_scroll_percent = 0
            
            while True:
                try:
                    # Bring page to front before each scroll operation
                    await page.bring_to_front()

                    scroll_percent = random.randint(46, 97)
                    total_scroll_percent += scroll_percent

                    # Get viewport height for natural scrolling
                    viewport = page.viewport_size
                    if not viewport:
                        # Fallback to default viewport size
                        scroll_distance = int(800 * scroll_percent / 100)
                    else:
                        scroll_distance = int(viewport["height"] * scroll_percent / 100)

                    # Use native mouse wheel scrolling (less detectable)
                    await asyncio.wait_for(
                        page.mouse.wheel(0, scroll_distance),
                        timeout=5,
                    )

                    await asyncio.sleep(random.uniform(0.23, 0.56))
                    await self.wait_or_timeout(page, "load", 2)

                    if total_scroll_percent >= self.max_scroll_percent:
                        break

                    # Check if at bottom
                    at_bottom = await asyncio.wait_for(
                        page.evaluate(
                            "window.innerHeight + window.scrollY >= document.scrollingElement.scrollHeight"
                        ),
                        timeout=3,
                    )
                    if cast(bool, at_bottom):
                        break
                except asyncio.TimeoutError:
                    Scraper.logger.warning("Scrolling timed out, assuming at bottom")
                    break
                except Exception as e:
                    Scraper.logger.warning(f"Error during scrolling: {e}")
                    break

        async def wait_or_timeout(
            self,
            page: Page,
            until: Literal["domcontentloaded", "load", "networkidle"] = "load",
            timeout: float = 3,
        ) -> None:
            try:
                await asyncio.wait_for(
                    page.wait_for_load_state(until, timeout=timeout * 1000), timeout
                )
            except asyncio.TimeoutError:
                Scraper.logger.warning(
                    f"timeout waiting for {until} after {timeout} seconds"
                )

        async def close_page(self, page: Page) -> None:
            try:
                if page:
                    await asyncio.wait_for(page.close(), timeout=10.0)
            except asyncio.TimeoutError:
                Scraper.logger.error("Page close timed out after 10 seconds")
            except Exception as e:
                Scraper.logger.error(
                    f"Failed to close page: {type(e).__name__}: {str(e)}"
                )
                Scraper.logger.debug(f"Close page exception details: {repr(e)}")
            finally:
                self.processing_count -= 1

        @asynccontextmanager
        async def rate_limit_for_domain(self, url: str) -> AsyncGenerator[None, None]:
            semaphore: Optional[asyncio.Semaphore] = None
            try:
                domain = Scraper.get_domain(url)

                semaphore = self.domain_semaphores.get(domain)
                if not semaphore:
                    semaphore = asyncio.Semaphore(1)
                    self.domain_semaphores[domain] = semaphore

                was_locked = semaphore.locked()
                async with semaphore:
                    if was_locked:
                        await asyncio.sleep(random.uniform(0.6, 1.2))
                    yield

            except Exception as e:
                # Log error but don't block the request
                Scraper.logger.warning(f"Rate limiting error for {url}: {str(e)}")

        async def stop(self) -> None:
            if self.stopping:
                return
            self.stopping = True
            try:
                if self.context:
                    await self.context.close()
                # self.context = None
            except Exception as e:
                Scraper.logger.error(f"Failed to stop context: {e}")

    @classmethod
    async def _cleanup_async(
        cls, page: Optional[Page], context_wrapper: Optional["Scraper.Context"]
    ) -> None:
        try:
            if page and context_wrapper:
                await context_wrapper.close_page(page)
            if context_wrapper:
                await cls.release_context(context_wrapper)
        except Exception as e:
            cls.logger.error(f"Cleanup failed: {e}")

    @classmethod
    async def _ensure_shared_browser(cls, headless: bool = False) -> None:
        """Ensure we have a shared browser instance"""
        if cls._shared_driver is None:
            try:
                from patchright.async_api import async_playwright
            except ImportError:
                raise ImportError(
                    "The patchright package is required to use Scraper. "
                    "Please install it with: pip install patchright"
                )

            cls._shared_driver = await async_playwright().start()
            cls._shared_browser = await cls._shared_driver.chromium.launch(
                headless=headless,
                channel="chrome",  # Use real Chrome for better stealth
                args=["--ozone-platform-hint=wayland"]
            )

        # Ensure _shared_browser is not None after initialization
        assert cls._shared_browser is not None, "Browser initialization failed"

    @classmethod
    async def get_context(cls, headless: bool = False) -> "Scraper.Context":
        async def create_context() -> "Scraper.Context":
            await cls._ensure_shared_browser(headless)
            browser = cast(Browser, cls._shared_browser)  # Tell IDE this is not None
            context = await browser.new_context(
                no_viewport=True,  # Recommended for stealth
            )
            context_wrapper = cls.Context(context)
            cls.contexts.add(context_wrapper)
            return context_wrapper

        async with cls.contexts_lock:
            if len(cls.contexts) == 0:
                # No contexts available, create new one
                return await create_context()

            # Load balancing: Get context with lowest number of tabs
            context_wrapper = min(cls.contexts, key=lambda c: c.processing_count)

            # If all contexts are heavily loaded and we can create more
            if (
                context_wrapper.processing_count >= cls.browser_load_threshold
                and len(cls.contexts) < cls.max_browsers
            ):
                return await create_context()

            return context_wrapper

    @classmethod
    async def release_context(cls, context_wrapper: "Scraper.Context") -> None:
        async with cls.contexts_lock:
            if context_wrapper and context_wrapper.processing_count <= 0:
                try:
                    await context_wrapper.stop()
                except Exception as e:
                    Scraper.logger.error(f"Failed to release context: {e}")
                finally:
                    cls.contexts.discard(context_wrapper)

    def __init__(self, url: str, session: Optional[Any] = None) -> None:
        self.url = Scraper.normalize_url(url)
        self.session = session
        self.debug: bool = True

    async def scrape_async(
        self,
        max_retries: int = 1,
        output_format: Literal["text", "markdown", "html"] = "markdown",
    ) -> Tuple[str, list[dict[str, Any]], str]:
        if not self.url:
            return (
                "A URL was not specified, cancelling request to browse website.",
                [],
                "",
            )

        for attempt in range(max_retries + 1):
            context_wrapper: Optional["Scraper.Context"] = None
            page: Optional[Page] = None
            try:
                try:
                    context_wrapper = await self.get_context()
                except ImportError as e:
                    self.logger.error(f"Failed to initialize context: {str(e)}")
                    return str(e), [], ""

                page = await context_wrapper.get(self.url)
                if page is None:
                    self.logger.error(
                        f"Failed to open page for {self.url}: page is None"
                    )
                    return f"Failed to open page for {self.url}: page is None", [], ""
                await context_wrapper.wait_or_timeout(page, "load", 2)
                # wait for potential redirection
                await asyncio.sleep(random.uniform(0.3, 0.7))
                await context_wrapper.wait_or_timeout(page, "networkidle", 2)

                await context_wrapper.scroll_page_to_bottom(page)
                try:
                    html = await asyncio.wait_for(page.content(), timeout=10.0)
                except asyncio.TimeoutError:
                    self.logger.error(
                        f"Timeout getting content for {self.url} after 10 seconds"
                    )
                    return (
                        f"Timeout getting content for {self.url} after 10 seconds",
                        [],
                        "",
                    )
                soup = BeautifulSoup(html, "lxml")
                title = extract_title(soup)

                decompose_irrelevant_imgs = True
                if output_format == "html":
                    decompose_irrelevant_imgs = False
                image_urls = get_relevant_images(
                    soup,
                    self.url,
                    title,
                    decompose_irrelevant=decompose_irrelevant_imgs,
                )

                if output_format == "html":
                    content = str(soup)
                elif output_format == "markdown":
                    soup = clean_soup(soup)
                    content = get_markdown_from_soup(soup)
                else:  # text format (default)
                    soup = clean_soup(soup)
                    content = get_text_from_soup(soup)

                if len(content) < 400:
                    self.logger.warning(
                        f"Content is too short from {self.url}. Title: {title}, Content length: {len(content)},\n"
                        f"excerpt: {content}."
                    )
                    if self.debug:
                        screenshot_dir = Path("logs/screenshots")
                        screenshot_dir.mkdir(exist_ok=True)
                        screenshot_path = (
                            screenshot_dir
                            / f"screenshot-error-{Scraper.get_domain(self.url)}.png"
                        )
                        try:
                            await asyncio.wait_for(
                                page.screenshot(path=screenshot_path), timeout=5.0
                            )
                        except asyncio.TimeoutError:
                            self.logger.warning(
                                f"Screenshot timeout for {self.url}, continuing..."
                            )
                        except Exception as screenshot_error:
                            self.logger.warning(
                                f"Screenshot failed for {self.url}: {screenshot_error}"
                            )
                        self.logger.warning(
                            f"check screenshot at [{screenshot_path}] for more details."
                        )

                return content, image_urls, title
            except Exception as e:
                is_last_attempt = attempt == max_retries
                attempt_info = f" (attempt {attempt + 1}/{max_retries + 1})"

                if is_last_attempt:
                    self.logger.error(
                        f"An error occurred during scraping{attempt_info}: {str(e)}\n"
                        "Full stack trace:\n"
                        f"{traceback.format_exc()}"
                    )
                    return str(e), [], ""
                else:
                    self.logger.warning(
                        f"An error occurred during scraping{attempt_info}: {str(e)}. Retrying..."
                    )
                    await asyncio.sleep(random.uniform(1.0, 2.0))
            finally:
                # Fire-and-forget cleanup - don't wait for it
                asyncio.create_task(self._cleanup_async(page, context_wrapper))

        # This should never be reached due to the logic above, but added for completeness
        return "Maximum retry attempts exceeded", [], ""
