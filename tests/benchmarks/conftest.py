"""基准测试共享配置。"""


def percentile(data: list[float], p: float) -> float:
    """计算百分位数。"""
    if not data:
        return 0.0
    sorted_data = sorted(data)
    idx = int(len(sorted_data) * p / 100)
    return sorted_data[min(idx, len(sorted_data) - 1)]
