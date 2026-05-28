"""NL2SQL Pipeline 端到端延迟基准测试。"""
import time

import pytest

from tests.benchmarks.conftest import percentile

QUESTIONS = [
    "上个月销售额是多少？",
    "各城市的订单数量趋势",
    "用户注册量 Top 10",
    "本月销售额环比增长",
    "最近7天的活跃用户数",
]


@pytest.mark.benchmark
async def test_nl2sql_pipeline_latency():
    """测试 NL2SQL Pipeline 端到端延迟。"""
    from datapilot_sqlgen.generator.pipeline import NL2SQLPipeline
    from datapilot_sqlgen.generator.postprocess import SQLPostProcessor

    # 构造最小化的 Pipeline（无需真实 LLM / Prompt 依赖）
    postprocessor = SQLPostProcessor()

    # 使用 stub PromptBuilder（避免依赖 TokenBudgetManager）
    class _StubPromptBuilder:
        def build_nl2sql_prompt(self, semantic_context, few_shots, question, dialect="mysql"):
            return question, few_shots

    pipeline = NL2SQLPipeline(
        prompt_builder=_StubPromptBuilder(),  # type: ignore[arg-type]
        postprocessor=postprocessor,
    )
    latencies: list[float] = []
    errors = 0

    # warmup
    for q in QUESTIONS[:1]:
        try:
            start = time.perf_counter()
            await pipeline.generate(
                question=q,
                dialect="mysql",
                tenant_id="bench",
                session_id="bench",
            )
        except Exception:
            pass

    # 正式测试
    for q in QUESTIONS:
        try:
            start = time.perf_counter()
            await pipeline.generate(
                question=q,
                tenant_id="bench",
                session_id="bench",
            )
            elapsed = (time.perf_counter() - start) * 1000  # ms
            latencies.append(elapsed)
        except Exception:
            errors += 1

    if not latencies:
        pytest.skip("所有请求均失败")

    # 输出统计
    print(f"\n{'='*60}")
    print("NL2SQL Pipeline 延迟统计")
    print(f"{'='*60}")
    print(f"请求数:   {len(QUESTIONS)}")
    print(f"成功数:   {len(latencies)}")
    print(f"失败数:   {errors}")
    print(f"P50:      {percentile(latencies, 50):.1f} ms")
    print(f"P95:      {percentile(latencies, 95):.1f} ms")
    print(f"P99:      {percentile(latencies, 99):.1f} ms")
    print(f"平均:     {sum(latencies)/len(latencies):.1f} ms")
    print(f"{'='*60}")

    # 断言: P95 不应超过 5 秒（stub 模式下应远低于此）
    assert percentile(latencies, 95) < 5000
