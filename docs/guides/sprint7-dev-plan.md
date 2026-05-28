# Sprint 7: Python Sandbox — 并行开发计划

> 目标：Python 代码安全执行环境
> 依赖：Sprint 6（DAG Runtime + Python TaskExecutor Stub）

## 并行 Track 划分

### Track A: Sandbox 核心抽象 + 代码安全检查

**目录隔离**: `libs/datapilot-sandbox/src/datapilot_sandbox/`
**无外部依赖**，纯抽象层。

| # | 任务 | 产出文件 |
|---|------|----------|
| A-1 | Sandbox 配置 | `config.py` — SandboxConfig（CPU/内存/超时/输出限制/允许的库） |
| A-2 | 代码安全检查 | `security.py` — CodeSecurityChecker（AST 级禁止 os.system/subprocess/import os 等） |
| A-3 | 沙箱接口 | `sandbox.py` — SandboxExecutor ABC（execute/health_check/get_info） |
| A-4 | 执行结果 | `models.py` — SandboxResult, CodeExecutionError, SandboxInfo |
| A-5 | 允许库清单 | `allowed_modules.py` — 安全的 Python 库列表（pandas/numpy/sklearn/matplotlib/seaborn 等不含 I/O 的库） |
| A-6 | 单元测试 | `tests/unit/test_sandbox/` |

**接口定义**:
```python
@dataclass
class SandboxConfig:
    cpu_limit: float = 1.0          # CPU 核数
    memory_limit_mb: int = 512      # 内存 MB
    timeout_seconds: float = 30.0    # 执行超时
    max_output_bytes: int = 1048576  # 输出限制 1MB
    allowed_modules: list[str] = field(default_factory=lambda: DEFAULT_ALLOWED_MODULES)
    read_only_filesystem: bool = True
    network_disabled: bool = True

@dataclass
class SandboxResult:
    success: bool
    stdout: str = ""
    stderr: str = ""
    output_bytes: int = 0
    execution_time_ms: float = 0.0
    error: str = ""
    memory_used_mb: float = 0.0
    cpu_time_ms: float = 0.0

class SandboxExecutor(ABC):
    @abstractmethod
    async def execute(self, code: str, config: SandboxConfig | None = None) -> SandboxResult: ...
    @abstractmethod
    async def health_check(self) -> bool: ...
    @abstractmethod
    async def get_info(self) -> SandboxInfo: ...
```

---

### Track B: 本地进程 Sandbox 实现

**目录隔离**: `libs/datapilot-sandbox/src/datapilot_sandbox/`
**依赖**: Track A（抽象层）

| # | 任务 | 产出文件 |
|---|------|----------|
| B-1 | 进程 Sandbox | `local.py` — LocalProcessSandbox（subprocess 执行 Python 代码，资源限制通过 resource 模块） |
| B-2 | 环境管理 | `environment.py` — SandboxEnvironment（预装库检测、隔离环境信息） |
| B-3 | 超时控制 | `timeout.py` — asyncio 子进程超时管理（30s 强制终止 + 清理） |
| B-4 | 输出截断 | `output.py` — stdout/stderr 输出截断（1MB 限制 + 尾部标记） |
| B-5 | 单元测试 | `tests/unit/test_sandbox_local/` |

**实现策略**:
- 使用 `asyncio.create_subprocess_exec` 执行 Python 代码
- 执行前通过 AST 检查代码安全性
- `resource.setrlimit` 限制内存和 CPU 时间
- stdout/stderr 管道读取，超限截断
- 执行超时后 `process.kill()` 强制终止

---

### Track C: K8s Pod 池管理（接口 + Stub）

**目录隔离**: `libs/datapilot-sandbox/src/datapilot_sandbox/k8s/`
**依赖**: Track A（抽象层）

| # | 任务 | 产出文件 |
|---|------|----------|
| C-1 | Pod 池接口 | `pool.py` — PodPool ABC（acquire/release/warmup/cleanup/get_stats） |
| C-2 | Pod 生命周期 | `lifecycle.py` — PodLifecycle（Creating→Ready→Busy→Terminating→Terminated 状态机） |
| C-3 | 本地 Stub | `local_pool.py` — LocalPodPool（使用 Track B 的 LocalProcessSandbox 模拟 Pod 池） |
| C-4 | 定时清理 | `reaper.py` — PodReaper（定期清理僵尸 Pod，30s 超时强制销毁） |
| C-5 | 资源监控 | `monitor.py` — PoolMonitor（连接池使用率、平均延迟、自动扩缩策略） |
| C-6 | 单元测试 | `tests/unit/test_sandbox_k8s/` |

**Pod 状态机**:
```
Creating → Ready → Busy → Ready → ... → Terminating → Terminated
           ↑                         │
           └─────────────────────────┘
```

---

### Track D: Python 执行器集成 DAG

**目录隔离**: `libs/datapilot-dag/src/datapilot_dag/executor/`
**依赖**: Track A/B（Sandbox）, Sprint 6 DAG Runtime

| # | 任务 | 产出文件 |
|---|------|----------|
| D-1 | Python 执行器实现 | 替换 `python_executor.py` Stub 为真实实现（调用 Sandbox） |
| D-2 | 执行器注册更新 | 更新 `registry.py` — 使用真实 PythonTaskExecutor |
| D-3 | DAG 单元测试扩展 | `tests/unit/test_executor/` — 补充 Python 任务执行测试 |
| D-4 | Python DAG 示例 | `tests/integration/test_python_dag.py` — 端到端 Python DAG 测试 |

---

### Track E: 前端 Python 代码编辑器

**目录隔离**: `web/packages/chat-ui/src/`
**依赖**: 已有的 SqlEditor 组件

| # | 任务 | 产出文件 |
|---|------|----------|
| E-1 | Python 代码编辑器 | `components/PythonEditor.tsx` — 代码编辑器 + 行号 + 运行按钮 + 输出面板 |
| E-2 | 输出面板 | `components/OutputPanel.tsx` — stdout/stderr 输出展示（等宽字体、滚动、复制） |
| E-3 | Store 扩展 | 扩展 `dagStore.ts` — Python 代码执行状态 |
| E-4 | API 层 | `api/sandbox.ts` — Python 代码执行 API |
| E-5 | 类型定义 | `types/sandbox.ts` — Sandbox 相关类型 |
| E-6 | MSW Mock | 扩展 `mocks/handlers.ts` — Sandbox API Mock |
| E-7 | MessageBubble 集成 | 扩展 `MessageBubble.tsx` — Python 输出结果展示 |

---

## Track 间文件隔离矩阵

| 目录 | Track A | Track B | Track C | Track D | Track E |
|------|---------|---------|---------|---------|---------|
| `libs/datapilot-sandbox/` | 写(core) | 写(local) | 写(k8s/) | 读 | - |
| `libs/datapilot-dag/executor/` | - | - | - | 写 | - |
| `web/packages/chat-ui/src/` | - | - | - | - | 写 |
| `tests/unit/test_sandbox/` | 写 | - | - | - | - |
| `tests/unit/test_sandbox_local/` | - | 写 | - | - | - |
| `tests/unit/test_sandbox_k8s/` | - | - | 写 | - | - |
| `tests/integration/` | - | - | - | 写 | - |

**冲突风险点**:
- `python_executor.py`：仅 Track D 修改（替换 Stub）。
- `dagStore.ts`：仅 Track E 修改。
- `MessageBubble.tsx`：仅 Track E 修改。

## 验证方式

- Track A: `uv run pytest tests/unit/test_sandbox/ -v`
- Track B: `uv run pytest tests/unit/test_sandbox_local/ -v`
- Track C: `uv run pytest tests/unit/test_sandbox_k8s/ -v`
- Track D: `uv run pytest tests/unit/test_executor/ -v`
