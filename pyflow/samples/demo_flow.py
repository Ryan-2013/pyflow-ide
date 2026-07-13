"""
PyFlow IDE — 示範檔案
========================
這個檔案展示 PyFlow 的流程圖可視化功能。
打開後，右側會自動出現流程圖。雙擊定義節點可進入函式內部。
"""
from __future__ import annotations
import asyncio, json, time
from typing import Optional


# ── 資料處理管線 ──────────────────────────────────────────────────

def load_config(path: str) -> dict:
    """從 JSON 檔案載入設定。"""
    with open(path) as f:
        config = json.load(f)
    return config


def validate_input(data: list) -> tuple[bool, list[str]]:
    """驗證輸入資料，回傳 (是否有效, 錯誤訊息列表)。"""
    errors = []
    if not data:
        errors.append("資料不能為空")
    for i, item in enumerate(data):
        if not isinstance(item, (int, float)):
            errors.append(f"第 {i} 筆資料型別錯誤：{type(item).__name__}")
    return len(errors) == 0, errors


def normalize(data: list[float], method: str = "minmax") -> list[float]:
    """正規化數值資料。"""
    if not data:
        return []
    if method == "minmax":
        min_v, max_v = min(data), max(data)
        if max_v == min_v:
            return [0.0] * len(data)
        return [(x - min_v) / (max_v - min_v) for x in data]
    elif method == "zscore":
        mean = sum(data) / len(data)
        std  = (sum((x - mean)**2 for x in data) / len(data)) ** 0.5
        if std == 0:
            return [0.0] * len(data)
        return [(x - mean) / std for x in data]
    else:
        raise ValueError(f"未知正規化方法：{method}")


def compute_stats(data: list[float]) -> dict:
    """計算基本統計指標。"""
    if not data:
        return {}
    n    = len(data)
    mean = sum(data) / n
    sorted_data = sorted(data)
    median = sorted_data[n // 2] if n % 2 else (sorted_data[n//2-1] + sorted_data[n//2]) / 2
    return {
        "count":  n,
        "mean":   round(mean, 4),
        "median": round(median, 4),
        "min":    min(data),
        "max":    max(data),
        "range":  round(max(data) - min(data), 4),
    }


# ── 非同步處理 ────────────────────────────────────────────────────

async def fetch_data(url: str, timeout: float = 5.0) -> Optional[dict]:
    """（模擬）非同步取得資料。"""
    await asyncio.sleep(0.1)   # 模擬網路延遲
    return {"url": url, "data": [1.0, 2.0, 3.0, 4.0, 5.0]}


async def process_batch(urls: list[str]) -> list[dict]:
    """並行處理多個 URL。"""
    tasks   = [fetch_data(url) for url in urls]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return [r for r in results if isinstance(r, dict)]


# ── 主管線 ────────────────────────────────────────────────────────

class DataPipeline:
    """完整的資料處理管線。"""

    def __init__(self, config: dict):
        self.config    = config
        self.results   = []
        self.errors    = []

    def run(self, raw_data: list) -> dict:
        """執行完整管線：驗證 → 正規化 → 統計。"""
        # Step 1: 驗證
        valid, errors = validate_input(raw_data)
        if not valid:
            self.errors.extend(errors)
            return {"ok": False, "errors": errors}

        # Step 2: 正規化
        method     = self.config.get("normalize", "minmax")
        normalized = normalize(raw_data, method)

        # Step 3: 統計
        stats = compute_stats(normalized)

        self.results.append(stats)
        return {"ok": True, "normalized": normalized, "stats": stats}

    def summary(self) -> str:
        total  = len(self.results)
        failed = len(self.errors)
        return f"完成：{total} 批次，{failed} 個錯誤"


def main():
    """程式入口。"""
    config   = {"normalize": "minmax", "batch_size": 10}
    pipeline = DataPipeline(config)

    # 測試資料
    datasets = [
        [3.0, 1.0, 4.0, 1.5, 9.0, 2.6, 5.3],
        [10.0, 20.0, 30.0, 40.0, 50.0],
        [],           # 應該失敗
        [1.0, "x"],   # 應該失敗
    ]

    for i, data in enumerate(datasets):
        result = pipeline.run(data)
        status = "✅" if result["ok"] else "❌"
        print(f"  {status} 資料集 {i+1}: {pipeline.summary()}")

    print("\n完成！")
    return pipeline.results


if __name__ == "__main__":
    main()
