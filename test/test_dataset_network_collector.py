"""DatasetNetworkCollector 的真实联网测试。

这个测试文件不是纯单元测试，而是面向“图片网络收集器”的接口验收测试。
原因是收集器的核心价值并不只是函数能被调用，而是它必须真的能完成以下事情：
1. 打开 Bing 图片搜索页，提取真实图片链接，并把真实图片保存到磁盘。
2. 调用 Pexels API，按单个关键词下载真实图片，并把真实图片保存到磁盘。
3. 按工具类要求使用 0001、0002、0003 这种全局递增文件名。
4. 在发现同编号文件已经存在时抛出异常，避免覆盖已有数据。

测试输出固定保存在 E:\\meter\\test\\out 下，并且测试结束后不会删除。
这样做是为了让开发者可以直接打开目录检查真实下载下来的图片质量，而不是只能看到
“测试通过”四个字。测试开始前会无条件删除旧的 out 目录，避免上一次运行留下来的
旧图片、旧锁文件或旧编号影响本次判断。
"""

from __future__ import annotations

import shutil
import sys
import unittest
from pathlib import Path

# 允许直接执行本文件：
#   python test/test_dataset_network_collector.py
# 也允许通过 unittest discovery 执行：
#   python -m unittest discover -s test -p test_dataset_network_collector.py
# 这两种执行方式的 sys.path 不完全相同，所以这里显式把项目根目录加入导入路径。
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from serve.dataset_network_collector import DatasetNetworkCollector


class TestDatasetNetworkCollector(unittest.TestCase):
    """验证 DatasetNetworkCollector 的外部接口和关键保护规则。

    这个测试类刻意让 Bing 和 Pexels 分开输出目录：
    - test/out/bing 只保存 Bing 下载结果。
    - test/out/pexels 只保存 Pexels 下载结果。

    分开目录可以让人工检查更直接，也可以避免两个数据源都从 0001 开始命名时互相触发
    “同名文件禁止覆盖”的规则。单张和批量下载不再继续拆子目录，因为这两个接口本来就
    应该共享同一个 collector 实例里的全局编号，测试正好能验证编号是否连续递增。
    """

    OUTPUT_ROOT = Path(__file__).resolve().parent / "out"
    BING_OUTPUT_DIR = OUTPUT_ROOT / "bing"
    PEXELS_OUTPUT_DIR = OUTPUT_ROOT / "pexels"
    CONFLICT_OUTPUT_DIR = OUTPUT_ROOT / "conflict_check"

    # Bing 下载接口不接收关键词，只接收完整的 Bing 图片搜索 URL。
    # 这里沿用原脚本里的“玻璃反光”搜索页，测试目标是验证 SEARCH_URL 抓图链路可用。
    BING_SEARCH_URL = (
        "https://www.bing.com/images/search"
        "?q=%E7%8E%BB%E7%92%83%E5%8F%8D%E5%85%89&form=HDRSC2&first=1"
    )

    SINGLE_DOWNLOAD_COUNT = 1
    BATCH_DOWNLOAD_COUNT = 10

    @classmethod
    def setUpClass(cls):
        """在整套测试开始前清空 test/out。

        这里使用“整套测试只清一次”，而不是每个测试方法都清一次。
        原因是测试结束后必须保留真实图片给人工检查；如果每个测试方法都清空目录，
        后面执行的测试会删除前面测试刚下载好的图片，最终 out 目录里就看不到完整结果。

        注意：这里会无条件删除 E:\\meter\\test\\out 下的所有内容。
        所以不要把手动整理的重要文件放在 test/out 里。
        """
        if cls.OUTPUT_ROOT.exists():
            shutil.rmtree(cls.OUTPUT_ROOT)

        cls.BING_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        cls.PEXELS_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        cls.CONFLICT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    def test_01_reject_invalid_bing_search_url(self):
        """非法 Bing SEARCH_URL 必须被拒绝。

        这个测试故意传入 127.168.0.1。它虽然长得像 URL，但不是有效的公网图片搜索入口。
        如果这个测试失败，说明 BingDownload 没有在打开浏览器前拦住本地或内网地址，
        后续就可能把错误地址、内网地址甚至无意义地址交给 Selenium 处理。
        """
        collector = DatasetNetworkCollector(
            output_dir=self.CONFLICT_OUTPUT_DIR,
            thread_count=2,
            timeout=20,
        )

        with self.assertRaises(ValueError):
            collector.BingDownload("http://127.168.0.1/images/search?q=test")

    def test_02_reject_same_stem_even_with_different_extension(self):
        """同编号文件已经存在时必须抛出异常。

        工具类要求文件名按 0001、0002、0003 递增。
        这里先手动创建 0001.png，再请求下载 1 张 Pexels 图片。
        即使真实下载结果可能是 0001.jpg，也必须因为主文件名 0001 已经存在而抛异常。

        这个测试不放在 bing 或 pexels 图片目录里，是为了避免人为制造的假文件污染
        真实图片检查目录。
        """
        collector = DatasetNetworkCollector(
            output_dir=self.CONFLICT_OUTPUT_DIR,
            thread_count=2,
            timeout=20,
        )
        (self.CONFLICT_OUTPUT_DIR / "0001.png").write_bytes(b"already exists")

        with self.assertRaises(FileExistsError):
            collector.PexelsDownloadBatch("sky", self.SINGLE_DOWNLOAD_COUNT)

    def test_03_pexels_single_then_batch_keeps_real_images(self):
        """Pexels 单张下载和批量下载必须共用同一套连续编号。

        测试步骤：
        1. 创建一个输出到 test/out/pexels 的 collector。
        2. 先调用 PexelsDownload("sky") 下载 1 张，预期得到 0001。
        3. 再调用 PexelsDownloadBatch("sky", 10) 下载 10 张，预期继续得到 0002 到 0011。

        这样写不是为了临时跑完就删，而是为了让 test/out/pexels 最终保留 11 张真实图片。
        如果这个测试失败，通常说明 Pexels API 调用失败、图片响应不是合法图片、编号没有
        全局递增，或保存路径规则被破坏。
        """
        collector = DatasetNetworkCollector(
            output_dir=self.PEXELS_OUTPUT_DIR,
            thread_count=2,
            timeout=20,
        )

        single_path = collector.PexelsDownload("sky")
        batch_paths = collector.PexelsDownloadBatch("sky", self.BATCH_DOWNLOAD_COUNT)
        all_paths = [single_path, *batch_paths]

        self.assertIsNotNone(single_path)
        self.assertEqual(len(batch_paths), self.BATCH_DOWNLOAD_COUNT)
        self.assertEqual(
            [path.stem for path in all_paths if path is not None],
            [f"{index:04d}" for index in range(1, 12)],
        )

        for saved_path in all_paths:
            self.assertIsNotNone(saved_path)
            self.assertTrue(saved_path.exists())
            self.assertEqual(saved_path.parent, self.PEXELS_OUTPUT_DIR)

    def test_04_bing_single_then_batch_keeps_real_images(self):
        """Bing 单张下载和批量下载必须共用同一套连续编号。

        测试步骤：
        1. 创建一个输出到 test/out/bing 的 collector。
        2. 先调用 BingDownload(SEARCH_URL) 下载 1 张，预期得到 0001。
        3. 再调用 BingDownloadBatch(SEARCH_URL, 10) 下载 10 张，预期继续得到 0002 到 0011。

        Bing 搜索结果中有些原图链接可能会返回 403、405 或非图片响应。
        工具类应跳过这些失败链接，并继续使用后续候选链接，直到尽量凑够目标数量。
        如果这个测试失败，通常说明 Bing 页面结构变化、Selenium 无法启动、候选链接不足、
        下载结果不是图片，或编号保存规则被破坏。
        """
        collector = DatasetNetworkCollector(
            output_dir=self.BING_OUTPUT_DIR,
            thread_count=2,
            timeout=20,
        )

        single_path = collector.BingDownload(self.BING_SEARCH_URL)
        batch_paths = collector.BingDownloadBatch(
            self.BING_SEARCH_URL,
            self.BATCH_DOWNLOAD_COUNT,
        )
        all_paths = [single_path, *batch_paths]

        self.assertIsNotNone(single_path)
        self.assertEqual(len(batch_paths), self.BATCH_DOWNLOAD_COUNT)
        self.assertEqual(
            [path.stem for path in all_paths if path is not None],
            [f"{index:04d}" for index in range(1, 12)],
        )

        for saved_path in all_paths:
            self.assertIsNotNone(saved_path)
            self.assertTrue(saved_path.exists())
            self.assertEqual(saved_path.parent, self.BING_OUTPUT_DIR)


if __name__ == "__main__":
    unittest.main()
