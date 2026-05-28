"""Pod 生命周期管理单元测试。

测试 Pod 状态转移的合法性和非法转移拒绝。
"""

from __future__ import annotations

import pytest

from datapilot_sandbox.k8s.lifecycle import PodInfo, PodLifecycle, PodState


# ---------- 辅助函数 ----------


def _make_pod(pod_id: str = "pod-1", state: PodState = PodState.CREATING) -> PodInfo:
    """创建测试用 PodInfo。"""
    return PodInfo(
        pod_id=pod_id,
        state=state,
        python_version="3.11",
        created_at=1000.0,
        last_used_at=1000.0,
    )


def _setup_pod_to_state(lifecycle: PodLifecycle, pod_id: str, target_state: PodState) -> None:
    """将 Pod 通过合法路径设置到目标状态。"""
    lifecycle.add(_make_pod(pod_id, PodState.CREATING))

    if target_state == PodState.CREATING:
        return
    # ERROR 可以直接从 CREATING 转移
    if target_state == PodState.ERROR:
        lifecycle.transition(pod_id, PodState.ERROR)
        return
    # 其他状态都需要先到 READY
    lifecycle.transition(pod_id, PodState.READY)

    if target_state == PodState.READY:
        return
    if target_state == PodState.TERMINATING:
        lifecycle.transition(pod_id, PodState.TERMINATING)
        return
    if target_state == PodState.BUSY:
        lifecycle.transition(pod_id, PodState.BUSY)
        return
    if target_state == PodState.TERMINATED:
        lifecycle.transition(pod_id, PodState.TERMINATING)
        lifecycle.transition(pod_id, PodState.TERMINATED)
        return


# ---------- 测试：合法状态转移 ----------


class TestValidTransitions:
    """合法状态转移测试。"""

    @pytest.mark.parametrize(
        ("initial_state", "target_state"),
        [
            (PodState.CREATING, PodState.READY),
            (PodState.CREATING, PodState.ERROR),
            (PodState.READY, PodState.BUSY),
            (PodState.READY, PodState.TERMINATING),
            (PodState.BUSY, PodState.READY),
            (PodState.BUSY, PodState.TERMINATING),
            (PodState.BUSY, PodState.ERROR),
            (PodState.TERMINATING, PodState.TERMINATED),
            (PodState.ERROR, PodState.TERMINATED),
        ],
        ids=[
            "CREATING->READY",
            "CREATING->ERROR",
            "READY->BUSY",
            "READY->TERMINATING",
            "BUSY->READY",
            "BUSY->TERMINATING",
            "BUSY->ERROR",
            "TERMINATING->TERMINATED",
            "ERROR->TERMINATED",
        ],
    )
    def test_valid_transition(self, initial_state: PodState, target_state: PodState) -> None:
        """所有合法转移应返回 True。"""
        lifecycle = PodLifecycle()
        if initial_state == PodState.TERMINATED:
            pytest.skip("TERMINATED 是终止状态，不能作为初始状态")
        _setup_pod_to_state(lifecycle, "pod-1", initial_state)
        assert lifecycle.transition("pod-1", target_state) is True


# ---------- 测试：非法状态转移 ----------


class TestInvalidTransitions:
    """非法状态转移测试。"""

    @pytest.mark.parametrize(
        ("initial_state", "target_state"),
        [
            (PodState.CREATING, PodState.BUSY),
            (PodState.CREATING, PodState.TERMINATING),
            (PodState.CREATING, PodState.TERMINATED),
            (PodState.READY, PodState.CREATING),
            (PodState.READY, PodState.ERROR),
            (PodState.READY, PodState.TERMINATED),
            (PodState.BUSY, PodState.CREATING),
            (PodState.BUSY, PodState.BUSY),
            (PodState.TERMINATING, PodState.READY),
            (PodState.TERMINATING, PodState.BUSY),
            (PodState.TERMINATING, PodState.CREATING),
            (PodState.TERMINATING, PodState.ERROR),
            (PodState.TERMINATED, PodState.CREATING),
            (PodState.TERMINATED, PodState.READY),
            (PodState.TERMINATED, PodState.BUSY),
            (PodState.ERROR, PodState.READY),
            (PodState.ERROR, PodState.BUSY),
            (PodState.ERROR, PodState.CREATING),
        ],
        ids=[
            "CREATING->BUSY",
            "CREATING->TERMINATING",
            "CREATING->TERMINATED",
            "READY->CREATING",
            "READY->ERROR",
            "READY->TERMINATED",
            "BUSY->CREATING",
            "BUSY->BUSY",
            "TERMINATING->READY",
            "TERMINATING->BUSY",
            "TERMINATING->CREATING",
            "TERMINATING->ERROR",
            "TERMINATED->CREATING",
            "TERMINATED->READY",
            "TERMINATED->BUSY",
            "ERROR->READY",
            "ERROR->BUSY",
            "ERROR->CREATING",
        ],
    )
    def test_invalid_transition(self, initial_state: PodState, target_state: PodState) -> None:
        """非法转移应返回 False。"""
        lifecycle = PodLifecycle()
        _setup_pod_to_state(lifecycle, "pod-1", initial_state)
        assert lifecycle.transition("pod-1", target_state) is False


# ---------- 测试：Pod 注册 ----------


class TestPodRegistration:
    """Pod 注册和管理测试。"""

    def test_add_pod_must_be_creating(self) -> None:
        """注册 Pod 时状态必须为 CREATING。"""
        lifecycle = PodLifecycle()
        with pytest.raises(ValueError, match="CREATING"):
            lifecycle.add(_make_pod("pod-1", PodState.READY))

    def test_add_and_get_pod(self) -> None:
        """添加和获取 Pod。"""
        lifecycle = PodLifecycle()
        pod = _make_pod("pod-1")
        lifecycle.add(pod)
        retrieved = lifecycle.get("pod-1")
        assert retrieved is not None
        assert retrieved.pod_id == "pod-1"
        assert retrieved.state == PodState.CREATING

    def test_get_nonexistent_pod(self) -> None:
        """获取不存在的 Pod 返回 None。"""
        lifecycle = PodLifecycle()
        assert lifecycle.get("nonexistent") is None

    def test_remove_pod(self) -> None:
        """移除 Pod。"""
        lifecycle = PodLifecycle()
        lifecycle.add(_make_pod("pod-1"))
        assert lifecycle.remove("pod-1") is True
        assert lifecycle.get("pod-1") is None

    def test_remove_nonexistent_pod(self) -> None:
        """移除不存在的 Pod 返回 False。"""
        lifecycle = PodLifecycle()
        assert lifecycle.remove("nonexistent") is False

    def test_transition_nonexistent_pod(self) -> None:
        """转移不存在的 Pod 返回 False。"""
        lifecycle = PodLifecycle()
        assert lifecycle.transition("nonexistent", PodState.READY) is False

    def test_list_by_state(self) -> None:
        """按状态列出 Pod。"""
        lifecycle = PodLifecycle()
        lifecycle.add(_make_pod("pod-1"))
        lifecycle.add(_make_pod("pod-2"))
        lifecycle.add(_make_pod("pod-3"))

        lifecycle.transition("pod-1", PodState.READY)
        lifecycle.transition("pod-2", PodState.ERROR)
        # pod-3 保持 CREATING

        assert len(lifecycle.list_by_state(PodState.CREATING)) == 1
        assert len(lifecycle.list_by_state(PodState.READY)) == 1
        assert len(lifecycle.list_by_state(PodState.ERROR)) == 1

    def test_transition_preserves_other_fields(self) -> None:
        """状态转移后其他字段保持不变。"""
        lifecycle = PodLifecycle()
        pod = PodInfo(
            pod_id="pod-1",
            state=PodState.CREATING,
            python_version="3.12",
            cpu_used=0.5,
            memory_used_mb=256.0,
            created_at=1000.0,
            last_used_at=2000.0,
            task_count=5,
            error="some error",
        )
        lifecycle.add(pod)
        lifecycle.transition("pod-1", PodState.READY)

        updated = lifecycle.get("pod-1")
        assert updated is not None
        assert updated.state == PodState.READY
        assert updated.python_version == "3.12"
        assert updated.cpu_used == 0.5
        assert updated.memory_used_mb == 256.0
        assert updated.created_at == 1000.0
        assert updated.last_used_at == 2000.0
        assert updated.task_count == 5
        assert updated.error == "some error"

    def test_pods_property_returns_copy(self) -> None:
        """pods 属性返回副本，外部修改不影响内部状态。"""
        lifecycle = PodLifecycle()
        lifecycle.add(_make_pod("pod-1"))
        pods = lifecycle.pods
        pods.clear()
        assert len(lifecycle.pods) == 1

    def test_transition_creates_new_podinfo_copy(self) -> None:
        """状态转移后返回的 PodInfo 是新的副本，非原始引用。"""
        lifecycle = PodLifecycle()
        lifecycle.add(_make_pod("pod-1"))
        original = lifecycle.get("pod-1")
        assert original is not None

        lifecycle.transition("pod-1", PodState.READY)
        after = lifecycle.get("pod-1")
        assert after is not None
        # 状态已变更
        assert after.state == PodState.READY
        # 确认是不同的对象（副本）
        assert original is not after

    def test_add_non_creating_state_raises(self) -> None:
        """非 CREATING 状态的 Pod 不能直接 add，各状态都应抛 ValueError。"""
        lifecycle = PodLifecycle()
        for state in PodState:
            if state == PodState.CREATING:
                continue
            with pytest.raises(ValueError, match="CREATING"):
                lifecycle.add(_make_pod(f"pod-{state}", state))


# ---------- 测试：完整生命周期 ----------


class TestFullLifecycle:
    """完整生命周期测试。"""

    def test_normal_lifecycle(self) -> None:
        """正常生命周期：CREATING -> READY -> BUSY -> READY -> TERMINATING -> TERMINATED。"""
        lifecycle = PodLifecycle()
        lifecycle.add(_make_pod("pod-1"))

        # CREATING -> READY
        assert lifecycle.transition("pod-1", PodState.READY) is True
        assert lifecycle.get("pod-1") is not None
        assert lifecycle.get("pod-1").state == PodState.READY

        # READY -> BUSY
        assert lifecycle.transition("pod-1", PodState.BUSY) is True
        assert lifecycle.get("pod-1").state == PodState.BUSY

        # BUSY -> READY
        assert lifecycle.transition("pod-1", PodState.READY) is True
        assert lifecycle.get("pod-1").state == PodState.READY

        # READY -> TERMINATING
        assert lifecycle.transition("pod-1", PodState.TERMINATING) is True
        assert lifecycle.get("pod-1").state == PodState.TERMINATING

        # TERMINATING -> TERMINATED
        assert lifecycle.transition("pod-1", PodState.TERMINATED) is True
        assert lifecycle.get("pod-1").state == PodState.TERMINATED

    def test_error_recovery(self) -> None:
        """错误恢复路径：CREATING -> ERROR -> TERMINATED。"""
        lifecycle = PodLifecycle()
        lifecycle.add(_make_pod("pod-1"))

        assert lifecycle.transition("pod-1", PodState.ERROR) is True
        assert lifecycle.get("pod-1").state == PodState.ERROR

        assert lifecycle.transition("pod-1", PodState.TERMINATED) is True
        assert lifecycle.get("pod-1").state == PodState.TERMINATED

    def test_busy_error_path(self) -> None:
        """执行出错路径：BUSY -> ERROR -> TERMINATED。"""
        lifecycle = PodLifecycle()
        lifecycle.add(_make_pod("pod-1"))
        lifecycle.transition("pod-1", PodState.READY)
        lifecycle.transition("pod-1", PodState.BUSY)

        assert lifecycle.transition("pod-1", PodState.ERROR) is True
        assert lifecycle.transition("pod-1", PodState.TERMINATED) is True

    def test_busy_to_terminating_to_terminated(self) -> None:
        """BUSY -> TERMINATING -> TERMINATED 路径。"""
        lifecycle = PodLifecycle()
        lifecycle.add(_make_pod("pod-1"))
        lifecycle.transition("pod-1", PodState.READY)
        lifecycle.transition("pod-1", PodState.BUSY)

        assert lifecycle.transition("pod-1", PodState.TERMINATING) is True
        assert lifecycle.transition("pod-1", PodState.TERMINATED) is True

    def test_ready_to_terminating_to_terminated(self) -> None:
        """READY -> TERMINATING -> TERMINATED 路径。"""
        lifecycle = PodLifecycle()
        lifecycle.add(_make_pod("pod-1"))
        lifecycle.transition("pod-1", PodState.READY)

        assert lifecycle.transition("pod-1", PodState.TERMINATING) is True
        assert lifecycle.transition("pod-1", PodState.TERMINATED) is True

    def test_terminated_is_final_state(self) -> None:
        """TERMINATED 是终态，不能再转移到任何状态。"""
        lifecycle = PodLifecycle()
        lifecycle.add(_make_pod("pod-1"))
        lifecycle.transition("pod-1", PodState.READY)
        lifecycle.transition("pod-1", PodState.TERMINATING)
        lifecycle.transition("pod-1", PodState.TERMINATED)

        for target in PodState:
            assert lifecycle.transition("pod-1", target) is False
