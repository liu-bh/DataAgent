"""Pod 生命周期状态管理。

定义 Pod 状态枚举、PodInfo 数据结构，以及状态转移逻辑。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import ClassVar


class PodState(StrEnum):
    """Pod 生命周期状态。"""

    CREATING = "creating"
    READY = "ready"
    BUSY = "busy"
    TERMINATING = "terminating"
    TERMINATED = "terminated"
    ERROR = "error"


@dataclass
class PodInfo:
    """Pod 元信息。"""

    pod_id: str
    state: PodState
    python_version: str = ""
    cpu_used: float = 0.0
    memory_used_mb: float = 0.0
    created_at: float = 0.0
    last_used_at: float = 0.0
    task_count: int = 0
    error: str = ""


# 合法状态转移表：key 为 (from_state, to_state)
_ALLOWED_TRANSITIONS: dict[tuple[PodState, PodState], bool] = {
    (PodState.CREATING, PodState.READY): True,
    (PodState.CREATING, PodState.ERROR): True,
    (PodState.READY, PodState.BUSY): True,
    (PodState.READY, PodState.TERMINATING): True,
    (PodState.BUSY, PodState.READY): True,
    (PodState.BUSY, PodState.TERMINATING): True,
    (PodState.BUSY, PodState.ERROR): True,
    (PodState.TERMINATING, PodState.TERMINATED): True,
    (PodState.ERROR, PodState.TERMINATED): True,
}


class PodLifecycle:
    """Pod 生命周期管理器。

    维护所有 Pod 的状态，提供线程安全的状态转移校验。
    """

    def __init__(self) -> None:
        # pod_id -> PodInfo
        self._pods: dict[str, PodInfo] = {}

    @property
    def pods(self) -> dict[str, PodInfo]:
        """返回所有 Pod 的快照。"""
        return dict(self._pods)

    def get(self, pod_id: str) -> PodInfo | None:
        """获取指定 Pod 信息，不存在时返回 None。"""
        return self._pods.get(pod_id)

    def add(self, pod: PodInfo) -> None:
        """注册一个新 Pod，状态必须为 CREATING。"""
        if pod.state != PodState.CREATING:
            raise ValueError(f"新 Pod 初始状态必须为 CREATING，当前: {pod.state}")
        self._pods[pod.pod_id] = pod

    def remove(self, pod_id: str) -> bool:
        """移除 Pod 记录，返回是否成功。"""
        return self._pods.pop(pod_id, None) is not None

    def transition(self, pod_id: str, new_state: PodState) -> bool:
        """状态转移，返回是否成功。

        合法转移:
        CREATING -> READY, ERROR
        READY -> BUSY, TERMINATING
        BUSY -> READY, TERMINATING, ERROR
        TERMINATING -> TERMINATED
        ERROR -> TERMINATED
        """
        pod = self._pods.get(pod_id)
        if pod is None:
            return False

        if (pod.state, new_state) not in _ALLOWED_TRANSITIONS:
            return False

        # 创建新的 PodInfo 副本（避免外部引用被篡改）
        self._pods[pod_id] = PodInfo(
            pod_id=pod.pod_id,
            state=new_state,
            python_version=pod.python_version,
            cpu_used=pod.cpu_used,
            memory_used_mb=pod.memory_used_mb,
            created_at=pod.created_at,
            last_used_at=pod.last_used_at,
            task_count=pod.task_count,
            error=pod.error,
        )
        return True

    def list_by_state(self, state: PodState) -> list[PodInfo]:
        """列出指定状态的所有 Pod。"""
        return [p for p in self._pods.values() if p.state == state]
