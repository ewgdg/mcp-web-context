from contextlib import asynccontextmanager
import math
from pathlib import Path
import random
import traceback
from typing_extensions import Literal
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from typing import Any, Dict, cast, Tuple
import asyncio
import logging

from .utils import (
    get_relevant_images,
    extract_title,
    get_text_from_soup,
    get_markdown_from_soup,
    clean_soup,
)


class NoDriverScraper:
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    max_browsers = 3
    browser_load_threshold = 5
    browsers: set["NoDriverScraper.Browser"] = set()
    browsers_lock = asyncio.Lock()

    @staticmethod
    def get_domain(url: str) -> str:
        domain = urlparse(url=url).netloc
        parts = domain.split(".")
        if len(parts) > 2:
            domain = ".".join(parts[-2:])
        return domain

    @staticmethod
    def normalize_url(url):
        parsed = urlparse(url)
        if not parsed.scheme:
            return "https://" + url
        return url

    class Browser:
        def __init__(
            self,
            driver: "zendriver.Browser",
        ):
            self.driver = driver
            self.processing_count = 0
            self.has_blank_page = True
            self.allowed_requests_times = {}
            self.domain_semaphores: Dict[str, asyncio.Semaphore] = {}
            self.tab_mode = True
            self.max_scroll_percent = 500
            self.stopping = False

        async def get(self, url: str) -> "zendriver.Tab":
            self.processing_count += 1
            try:
                async with self.rate_limit_for_domain(url):
                    new_window = not self.has_blank_page
                    self.has_blank_page = False
                    if self.tab_mode:
                        return await self.driver.get(url, new_tab=new_window)
                    else:
                        return await self.driver.get(url, new_window=new_window)
            except Exception:
                self.processing_count -= 1
                raise

        async def scroll_page_to_bottom(self, page: "zendriver.Tab"):
            total_scroll_percent = 0
            
            while True:
                try:
                    # in tab mode, we need to bring the tab to front before scrolling to load the page content properly
                    if self.tab_mode:
                        await page.bring_to_front()
                    scroll_percent = random.randint(46, 97)
                    total_scroll_percent += scroll_percent
                    speed = random.randint(1600, 2800)
                    await asyncio.wait_for(
                        page.scroll_down(amount=scroll_percent, speed=speed), timeout=5
                    )
                    await self.wait_or_timeout(page, "idle", 2)
                    await page.sleep(random.uniform(0.23, 0.56))

                    if total_scroll_percent >= self.max_scroll_percent:
                        break

                    # Add timeout to page.evaluate to prevent hanging
                    at_bottom = await asyncio.wait_for(
                        page.evaluate(
                            "window.innerHeight + window.scrollY >= document.scrollingElement.scrollHeight"
                        ),
                        timeout=3,
                    )
                    if cast(bool, at_bottom):
                        break
                except asyncio.TimeoutError:
                    NoDriverScraper.logger.warning(
                        "Scrolling timed out, assuming at bottom"
                    )
                    break
                except Exception as e:
                    NoDriverScraper.logger.warning(f"Error during scrolling: {e}")
                    break

        async def wait_or_timeout(
            self,
            page: "zendriver.Tab",
            until: Literal["complete", "idle"] = "idle",
            timeout: float = 3,
        ):
            try:
                if until == "idle":
                    await asyncio.wait_for(page.wait(), timeout)
                else:
                    await page.wait_for_ready_state(until, timeout=math.ceil(timeout))
            except asyncio.TimeoutError:
                NoDriverScraper.logger.warning(
                    f"timeout waiting for {until} after {timeout} seconds"
                )

        async def close_page(self, page: "zendriver.Tab"):
            try:
                await asyncio.wait_for(page.close(), timeout=10.0)
            except asyncio.TimeoutError:
                NoDriverScraper.logger.error("Page close timed out after 10 seconds")
            except Exception as e:
                NoDriverScraper.logger.error(f"Failed to close page: {type(e).__name__}: {str(e)}")
                NoDriverScraper.logger.debug(f"Close page exception details: {repr(e)}")
            finally:
                self.processing_count -= 1

        @asynccontextmanager
        async def rate_limit_for_domain(self, url: str):
            semaphore = None
            try:
                domain = NoDriverScraper.get_domain(url)

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
                NoDriverScraper.logger.warning(
                    f"Rate limiting error for {url}: {str(e)}"
                )

        async def stop(self):
            if self.stopping:
                return
            self.stopping = True
            try:
                await asyncio.wait_for(self.driver.stop(), timeout=10.0)
            except asyncio.TimeoutError:
                NoDriverScraper.logger.error("Browser stop timed out after 10 seconds")
            except Exception as e:
                NoDriverScraper.logger.error(f"Failed to stop browser: {e}")

    @classmethod
    async def _cleanup_async(
        cls, page: "zendriver.Tab | None", browser: "NoDriverScraper.Browser | None"
    ):
        try:
            if page and browser:
                await browser.close_page(page)
            if browser:
                await cls.release_browser(browser)
        except Exception as e:
            cls.logger.error(f"Cleanup failed: {e}")

    @classmethod
    async def get_browser(cls, headless: bool = False) -> "NoDriverScraper.Browser":
        async def create_browser():
            try:
                global zendriver
                import zendriver
            except ImportError:
                raise ImportError(
                    "The zendriver package is required to use NoDriverScraper. "
                    "Please install it with: pip install zendriver"
                )

            config = zendriver.Config(
                headless=headless,
                browser_connection_timeout=0.5,
                # required to run in wayland vnc
                browser_args=[
                    # use wayland for rendering instead of default X11 backend
                    "--ozone-platform-hint=wayland",
                    # "--ignore-gpu-blocklist",
                ],
            )
            driver = await zendriver.start(config)
            browser = cls.Browser(driver)
            cls.browsers.add(browser)
            return browser

        async with cls.browsers_lock:
            if len(cls.browsers) == 0:
                # No browsers available, create new one
                return await create_browser()

            # Load balancing: Get browser with lowest number of tabs
            browser = min(cls.browsers, key=lambda b: b.processing_count)

            # If all browsers are heavily loaded and we can create more
            if (
                browser.processing_count >= cls.browser_load_threshold
                and len(cls.browsers) < cls.max_browsers
            ):
                return await create_browser()

            return browser

    @classmethod
    async def release_browser(cls, browser: Browser):
        async with cls.browsers_lock:
            if browser and browser.processing_count <= 0:
                try:
                    await browser.stop()
                except Exception as e:
                    NoDriverScraper.logger.error(f"Failed to release browser: {e}")
                finally:
                    cls.browsers.discard(browser)

    def __init__(self, url: str, session: Any | None = None):
        self.url = NoDriverScraper.normalize_url(url)
        self.session = session
        self.debug = True

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
            browser: NoDriverScraper.Browser | None = None
            page = None
            try:
                try:
                    browser = await self.get_browser()
                except ImportError as e:
                    self.logger.error(f"Failed to initialize browser: {str(e)}")
                    return str(e), [], ""

                page = await browser.get(self.url)
                if page is None:
                    self.logger.error(
                        f"Failed to open page for {self.url}: page is None"
                    )
                    return f"Failed to open page for {self.url}: page is None", [], ""
                await browser.wait_or_timeout(page, "complete", 2)
                # wait for potential redirection
                await page.sleep(random.uniform(0.3, 0.7))
                await browser.wait_or_timeout(page, "idle", 2)

                await browser.scroll_page_to_bottom(page)
                try:
                    html = await asyncio.wait_for(page.get_content(), timeout=10.0)
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
                            / f"screenshot-error-{NoDriverScraper.get_domain(self.url)}.jpeg"
                        )
                        try:
                            await asyncio.wait_for(
                                page.save_screenshot(screenshot_path), timeout=5.0
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
                asyncio.create_task(self._cleanup_async(page, browser))

        # This should never be reached due to the logic above, but added for completeness
        return "Maximum retry attempts exceeded", [], ""
