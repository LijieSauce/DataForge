"""Dataset image collector integrated from Bing and Pexels download scripts."""

from __future__ import annotations

import ipaddress
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

import requests
from tqdm import tqdm


class DatasetNetworkCollector:
    """纯粹的数据集网络图片收集器。

    该类只做一件事：从网络图片源下载图片到指定目录。
    构造函数只保存通用下载配置，具体来源需要的参数放到各自接口中传入。
    """

    PEXELS_API_KEY = "rZSZAnlS5au4o7qgCJvoXzoB0gBm83xLmzVXQ9ZjekzfvyLRfw2VdvOT"
    PEXELS_API_URL = "https://api.pexels.com/v1/search"

    DEFAULT_BING_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        )
    }

    IMAGE_EXTENSIONS = ("jpg", "jpeg", "png", "webp", "gif", "bmp")

    def __init__(self, output_dir: str | Path, thread_count: int = 5, timeout: int | float = 15):
        """初始化收集器。

        Args:
            output_dir: 图片输出目录，不存在时自动创建。
            thread_count: 批量下载时使用的线程数量，至少为 1。
            timeout: 网络请求超时时间，单位为秒。
        """
        if thread_count < 1:
            raise ValueError("thread_count 必须大于等于 1")
        if timeout <= 0:
            raise ValueError("timeout 必须大于 0")

        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.thread_count = thread_count
        self.timeout = timeout

        # 文件编号是整个收集器实例内全局递增的，Bing 和 Pexels 共用同一套编号。
        self._next_index = 1
        self._file_lock = threading.Lock()

    def BingDownload(self, search_url: str, headers: dict[str, str] | None = None) -> Path | None:
        """从一个 Bing 图片搜索页下载 1 张图片。

        Args:
            search_url: Bing 图片搜索页地址，例如 https://www.bing.com/images/search?q=xxx。
            headers: 下载图片时使用的请求头，不传则使用浏览器 UA 默认值。

        Returns:
            下载成功时返回图片路径，没有拿到可用图片时返回 None。
        """
        results = self.BingDownloadBatch(search_url=search_url, count=1, headers=headers)
        return results[0] if results else None

    def BingDownloadBatch(
        self,
        search_url: str,
        count: int,
        headers: dict[str, str] | None = None,
    ) -> list[Path]:
        """从一个 Bing 图片搜索页批量下载图片。

        Bing 侧不接收关键词参数，只接收完整 SEARCH_URL；该 URL 会被校验为合法的
        Bing 图片搜索链接，避免把 127.x、localhost 等无效地址当成下载入口。

        Args:
            search_url: Bing 图片搜索页完整地址。
            count: 需要下载的图片数量。
            headers: 下载原图时使用的请求头。

        Returns:
            成功保存的图片路径列表。
        """
        self._validate_count(count)
        self._validate_bing_search_url(search_url)
        self._assert_index_range_available(count)

        request_headers = dict(self.DEFAULT_BING_HEADERS)
        if headers:
            request_headers.update(headers)

        print(f"开始从 Bing 收集图片，目标数量：{count}")
        driver = self._create_headless_driver()

        try:
            candidate_count = max(count * 3, count + self.thread_count)
            thumbnails = self._load_bing_thumbnails(driver, search_url, candidate_count)
            image_urls = self._extract_bing_image_urls(driver, thumbnails, candidate_count)
        finally:
            driver.quit()
            print("Bing 无头浏览器已关闭")

        if not image_urls:
            print("未从 Bing 页面提取到可用图片链接")
            return []

        return self._download_urls_until_count(image_urls, count, request_headers, "Bing下载")

    def PexelsDownload(self, query: str) -> Path | None:
        """从 Pexels 使用单个关键词下载 1 张图片。

        Args:
            query: Pexels 搜索关键词，只允许传入一个字符串关键词。

        Returns:
            下载成功时返回图片路径，没有拿到可用图片时返回 None。
        """
        results = self.PexelsDownloadBatch(query=query, count=1)
        return results[0] if results else None

    def PexelsDownloadBatch(self, query: str, count: int) -> list[Path]:
        """从 Pexels 使用单个关键词批量下载图片。

        PEXELS_API_URL 固定写在类常量中；该接口只接收一个关键词，不接收关键词列表。

        Args:
            query: Pexels 搜索关键词。
            count: 需要下载的图片数量。

        Returns:
            成功保存的图片路径列表。
        """
        self._validate_query(query)
        self._validate_count(count)
        self._assert_index_range_available(count)

        headers = {"Authorization": self.PEXELS_API_KEY}
        saved_paths: list[Path] = []
        page = 1
        per_page = min(80, count)

        print(f"开始从 Pexels 收集图片，关键词：{query}，目标数量：{count}")
        with tqdm(total=count, desc="Pexels下载", unit="张") as progress:
            while len(saved_paths) < count:
                params = {
                    "query": query,
                    "per_page": min(per_page, count - len(saved_paths)),
                    "page": page,
                }

                response = requests.get(
                    self.PEXELS_API_URL,
                    headers=headers,
                    params=params,
                    timeout=self.timeout,
                )

                if response.status_code == 429:
                    print("Pexels API 触发限流，等待 10 秒后继续")
                    time.sleep(10)
                    continue

                if response.status_code != 200:
                    print(f"Pexels API 请求失败，HTTP 状态码：{response.status_code}")
                    break

                photos = response.json().get("photos", [])
                if not photos:
                    print("Pexels 没有返回更多图片")
                    break

                for photo in photos:
                    if len(saved_paths) >= count:
                        break

                    image_url = photo.get("src", {}).get("large")
                    if not self._is_valid_http_url(image_url):
                        print(f"跳过非法图片链接：{image_url}")
                        continue

                    saved_path = self._download_and_save_image(image_url, headers=None)
                    if saved_path:
                        saved_paths.append(saved_path)
                        progress.update(1)

                page += 1
                time.sleep(1)

        print(f"Pexels 下载完成，成功保存：{len(saved_paths)} 张")
        return saved_paths

    def _create_headless_driver(self):
        """创建无头 Chrome 浏览器，避免 Bing 下载时弹出浏览器窗口。"""
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service

        chrome_options = Options()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")

        cached_driver = self._find_cached_chromedriver()
        if cached_driver:
            return webdriver.Chrome(service=Service(str(cached_driver)), options=chrome_options)

        # Selenium 4 会通过 Selenium Manager 自动匹配 ChromeDriver，避免旧脚本依赖
        # webdriver_manager 在用户目录创建锁文件导致权限或残留锁问题。
        return webdriver.Chrome(options=chrome_options)

    def _find_cached_chromedriver(self) -> Path | None:
        """优先复用本机已缓存的 ChromeDriver，避免启动时再次下载驱动。"""
        candidates = list(Path.home().glob(".wdm/drivers/chromedriver/win64/*/chromedriver-win64/chromedriver.exe"))
        if not candidates:
            return None

        candidates.sort(key=lambda path: path.stat().st_mtime, reverse=True)
        return candidates[0]

    def _load_bing_thumbnails(self, driver, search_url: str, target_count: int):
        """打开 Bing SEARCH_URL，并滚动页面直到加载到足够数量的缩略图。"""
        from selenium.webdriver.common.by import By

        driver.get(search_url)
        time.sleep(2)

        last_height = driver.execute_script("return document.body.scrollHeight")
        loaded_count = 0

        with tqdm(total=target_count, desc="Bing加载", unit="张") as progress:
            while loaded_count < target_count:
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(1.5)

                try:
                    more_button = driver.find_element(By.CSS_SELECTOR, ".btn_seemore")
                    more_button.click()
                    time.sleep(2)
                except Exception:
                    pass

                thumbnails = driver.find_elements(By.CSS_SELECTOR, ".iusc")
                new_count = len(thumbnails)
                if new_count > loaded_count:
                    progress.update(min(new_count, target_count) - min(loaded_count, target_count))
                loaded_count = new_count

                new_height = driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height and loaded_count > 0:
                    break
                last_height = new_height

        return driver.find_elements(By.CSS_SELECTOR, ".iusc")

    def _extract_bing_image_urls(self, driver, thumbnails: Iterable, target_count: int) -> list[str]:
        """从 Bing 缩略图元素提取原图链接，并过滤明显非法的 URL。"""
        image_urls: list[str] = []
        max_count = min(len(thumbnails), target_count)

        with tqdm(total=max_count, desc="Bing提链", unit="张") as progress:
            for index, thumbnail in enumerate(list(thumbnails)[:target_count], start=1):
                image_url = self._extract_bing_image_url(driver, thumbnail)
                if self._is_valid_http_url(image_url):
                    image_urls.append(image_url)
                else:
                    print(f"跳过非法 Bing 图片链接：{image_url}")

                progress.update(1)
                time.sleep(0.3)

                if len(image_urls) >= target_count:
                    break

        print(f"Bing 链接提取完成，成功：{len(image_urls)}，目标：{target_count}")
        return image_urls

    def _extract_bing_image_url(self, driver, thumbnail) -> str | None:
        """按原脚本顺序提取 Bing 原图 URL：m 属性优先，点击缩略图作为备用。"""
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.support.ui import WebDriverWait

        try:
            m_json = thumbnail.get_attribute("m")
            if m_json:
                data = json.loads(m_json)
                image_url = data.get("murl") or data.get("turl") or data.get("purl")
                if self._is_valid_http_url(image_url):
                    return image_url
        except Exception as error:
            print(f"从 Bing m 属性提取失败：{error}")

        try:
            thumbnail.click()
            time.sleep(1.2)

            selectors = [
                "#mainImageWindow img",
                ".mainImage img",
                ".mimg",
                "img.nofocus",
                "#imgContainer img",
            ]

            for selector in selectors:
                try:
                    image = WebDriverWait(driver, 3).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    image_url = image.get_attribute("src")
                    if self._is_valid_http_url(image_url):
                        return image_url
                except Exception:
                    continue
        except Exception as error:
            print(f"点击 Bing 缩略图提取失败：{error}")

        try:
            image = thumbnail.find_element(By.TAG_NAME, "img")
            image_url = image.get_attribute("src")
            if self._is_valid_http_url(image_url):
                return image_url
        except Exception as error:
            print(f"从 Bing 缩略图标签提取失败：{error}")

        return None

    def _download_urls_with_threads(
        self,
        urls: list[str],
        headers: dict[str, str] | None,
        progress_desc: str,
    ) -> list[Path]:
        """使用线程池下载 URL 列表，进度条按完成数量更新。"""
        saved_paths: list[Path] = []

        with ThreadPoolExecutor(max_workers=self.thread_count) as executor:
            futures = [
                executor.submit(self._download_and_save_image, url, headers)
                for url in urls
            ]

            with tqdm(total=len(futures), desc=progress_desc, unit="张") as progress:
                for future in as_completed(futures):
                    saved_path = future.result()
                    if saved_path:
                        saved_paths.append(saved_path)
                    progress.update(1)

        saved_paths.sort()
        print(f"{progress_desc}完成，成功保存：{len(saved_paths)} 张")
        return saved_paths

    def _download_urls_until_count(
        self,
        urls: list[str],
        count: int,
        headers: dict[str, str] | None,
        progress_desc: str,
    ) -> list[Path]:
        """按候选 URL 顺序下载，直到成功数量达到目标数量。"""
        saved_paths: list[Path] = []

        with tqdm(total=count, desc=progress_desc, unit="张") as progress:
            for image_url in urls:
                if len(saved_paths) >= count:
                    break

                saved_path = self._download_and_save_image(image_url, headers)
                if saved_path:
                    saved_paths.append(saved_path)
                    progress.update(1)

        print(f"{progress_desc}完成，成功保存：{len(saved_paths)} 张")
        return saved_paths

    def _download_and_save_image(
        self,
        image_url: str,
        headers: dict[str, str] | None,
    ) -> Path | None:
        """下载前校验 URL，下载后校验响应确实是图片，再按全局编号保存。"""
        if not self._is_valid_http_url(image_url):
            print(f"非法图片链接，已跳过：{image_url}")
            return None

        try:
            response = requests.get(image_url, headers=headers, timeout=self.timeout)
        except requests.RequestException as error:
            print(f"图片请求失败，已跳过：{image_url}，原因：{error}")
            return None

        if response.status_code != 200:
            print(f"图片下载失败，HTTP 状态码：{response.status_code}，链接：{image_url}")
            return None

        content_type = response.headers.get("Content-Type", "").split(";")[0].lower()
        if not content_type.startswith("image/"):
            print(f"响应不是图片，已跳过：{image_url}，Content-Type：{content_type}")
            return None

        if not response.content:
            print(f"图片内容为空，已跳过：{image_url}")
            return None

        extension = self._extension_from_content_type(content_type)
        return self._save_image(response.content, extension)

    def _save_image(self, content: bytes, extension: str) -> Path:
        """按 0001、0002、0003 的全局编号保存图片，同名文件存在则抛异常。"""
        with self._file_lock:
            stem = f"{self._next_index:04d}"
            self.output_dir.mkdir(parents=True, exist_ok=True)
            self._assert_stem_available(stem)

            save_path = self.output_dir / f"{stem}.{extension}"
            with save_path.open("xb") as image_file:
                image_file.write(content)

            self._next_index += 1

        print(f"保存图片：{save_path}")
        return save_path

    def _assert_index_range_available(self, count: int) -> None:
        """下载前预检查即将使用的编号，避免下载到一半才发现重名。"""
        with self._file_lock:
            for index in range(self._next_index, self._next_index + count):
                self._assert_stem_available(f"{index:04d}")

    def _assert_stem_available(self, stem: str) -> None:
        """只按文件名主干判断重名；0001.jpg 和 0001.png 都算同名。"""
        for extension in self.IMAGE_EXTENSIONS:
            if (self.output_dir / f"{stem}.{extension}").exists():
                raise FileExistsError(f"输出目录已存在同名文件：{stem}.*")

    def _validate_bing_search_url(self, search_url: str) -> None:
        """校验 Bing SEARCH_URL，拒绝非 Bing 图片搜索页和本地/内网地址。"""
        if not self._is_valid_http_url(search_url):
            raise ValueError(f"非法 Bing SEARCH_URL：{search_url}")

        parsed_url = urlparse(search_url)
        host = parsed_url.hostname or ""
        if not host.endswith("bing.com"):
            raise ValueError(f"Bing SEARCH_URL 必须来自 bing.com：{search_url}")
        if "/images/search" not in parsed_url.path:
            raise ValueError(f"Bing SEARCH_URL 必须是图片搜索页：{search_url}")

    def _is_valid_http_url(self, url: str | None) -> bool:
        """校验 URL 是否是可用于网络下载的 http/https 链接。"""
        if not url or not isinstance(url, str):
            return False

        parsed_url = urlparse(url)
        if parsed_url.scheme not in {"http", "https"}:
            return False
        if not parsed_url.netloc or not parsed_url.hostname:
            return False

        host = parsed_url.hostname.strip().lower()
        if host == "localhost" or host.endswith(".localhost"):
            return False

        try:
            ip = ipaddress.ip_address(host)
        except ValueError:
            return True

        return not (
            ip.is_loopback
            or ip.is_private
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        )

    def _extension_from_content_type(self, content_type: str) -> str:
        """根据图片响应的 Content-Type 选择保存扩展名。"""
        if content_type in {"image/jpeg", "image/jpg"}:
            return "jpg"
        if content_type == "image/png":
            return "png"
        if content_type == "image/webp":
            return "webp"
        if content_type == "image/gif":
            return "gif"
        if content_type == "image/bmp":
            return "bmp"
        return "jpg"

    def _validate_count(self, count: int) -> None:
        """校验下载数量。"""
        if not isinstance(count, int) or count < 1:
            raise ValueError("count 必须是大于等于 1 的整数")

    def _validate_query(self, query: str) -> None:
        """校验 Pexels 单关键词参数，不接收列表或空字符串。"""
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query 必须是非空字符串")
