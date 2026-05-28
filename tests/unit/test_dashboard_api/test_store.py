"""Dashboard 存储单元测试。"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# 确保项目源码路径可被导入
project_root = Path(__file__).resolve().parent.parent.parent.parent / "services" / "agent-service" / "src"
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

libs_root = Path(__file__).resolve().parent.parent.parent.parent / "libs"
for lib_dir in libs_root.iterdir():
    if lib_dir.is_dir():
        lib_src = lib_dir / "src"
        if lib_src.exists() and str(lib_src) not in sys.path:
            sys.path.insert(0, str(lib_src))

from datapilot_agent.dashboard.store import DashboardStore


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def store() -> DashboardStore:
    """创建空的 DashboardStore 实例。"""
    return DashboardStore()


@pytest.fixture
def populated_store(store: DashboardStore) -> DashboardStore:
    """创建包含 3 个 Dashboard 的 Store。"""
    for i in range(3):
        store.save({
            "title": f"测试 Dashboard {i + 1}",
            "description": f"描述 {i + 1}",
            "chart_specs": [
                {
                    "title": f"面板 {i + 1}-A",
                    "chart_type": "bar",
                    "chart_config": {},
                    "data_source": {},
                },
                {
                    "title": f"面板 {i + 1}-B",
                    "chart_type": "line",
                    "chart_config": {},
                    "data_source": {},
                },
            ],
            "columns": 2,
        })
    return store


# ---------------------------------------------------------------------------
# 测试: save
# ---------------------------------------------------------------------------


class TestDashboardStoreSave:
    """save 方法测试。"""

    def test_save_returns_dashboard_id(self, store: DashboardStore) -> None:
        """save 应返回非空的 dashboard_id。"""
        dashboard_id = store.save({
            "title": "测试",
            "description": "描述",
            "chart_specs": [],
            "columns": 2,
        })

        assert dashboard_id is not None
        assert isinstance(dashboard_id, str)
        assert len(dashboard_id) > 0

    def test_save_generates_unique_id(self, store: DashboardStore) -> None:
        """每次 save 应生成不同的 ID。"""
        id1 = store.save({"title": "A", "chart_specs": []})
        id2 = store.save({"title": "B", "chart_specs": []})

        assert id1 != id2

    def test_save_stores_layout(self, store: DashboardStore) -> None:
        """save 后应能通过 get 检索到布局。"""
        dashboard_id = store.save({
            "title": "我的 Dashboard",
            "description": "测试描述",
            "chart_specs": [],
            "columns": 3,
        })

        layout = store.get(dashboard_id)
        assert layout is not None
        assert layout.title == "我的 Dashboard"
        assert layout.description == "测试描述"
        assert layout.columns == 3

    def test_save_creates_panels_from_specs(self, store: DashboardStore) -> None:
        """save 应将 chart_specs 转换为 panels。"""
        dashboard_id = store.save({
            "title": "面板测试",
            "chart_specs": [
                {"title": "销量图", "chart_type": "bar"},
                {"title": "趋势图", "chart_type": "line"},
                {"title": "占比图", "chart_type": "pie"},
            ],
            "columns": 3,
        })

        layout = store.get(dashboard_id)
        assert layout is not None
        assert len(layout.panels) == 3
        assert layout.panels[0]["title"] == "销量图"
        assert layout.panels[0]["chart_type"] == "bar"
        assert layout.panels[2]["chart_type"] == "pie"

    def test_save_assigns_panel_positions(self, store: DashboardStore) -> None:
        """save 应为面板分配行列位置。"""
        dashboard_id = store.save({
            "title": "位置测试",
            "chart_specs": [
                {"title": "A", "chart_type": "bar"},
                {"title": "B", "chart_type": "bar"},
                {"title": "C", "chart_type": "bar"},
                {"title": "D", "chart_type": "bar"},
            ],
            "columns": 2,
        })

        layout = store.get(dashboard_id)
        assert layout is not None
        # 4 个面板, 2 列布局
        assert layout.panels[0]["row"] == 0
        assert layout.panels[0]["col"] == 0
        assert layout.panels[1]["row"] == 0
        assert layout.panels[1]["col"] == 1
        assert layout.panels[2]["row"] == 1
        assert layout.panels[2]["col"] == 0
        assert layout.panels[3]["row"] == 1
        assert layout.panels[3]["col"] == 1

    def test_save_records_created_at(self, store: DashboardStore) -> None:
        """save 应记录创建时间。"""
        dashboard_id = store.save({"title": "时间测试", "chart_specs": []})

        created_at = store.get_created_at(dashboard_id)
        assert created_at is not None
        assert len(created_at) > 0


# ---------------------------------------------------------------------------
# 测试: get
# ---------------------------------------------------------------------------


class TestDashboardStoreGet:
    """get 方法测试。"""

    def test_get_existing_dashboard(self, populated_store: DashboardStore) -> None:
        """获取存在的 Dashboard 应返回布局。"""
        layouts = populated_store.list_all()
        dashboard_id = getattr(layouts[0], "dashboard_id", "")

        layout = populated_store.get(dashboard_id)
        assert layout is not None

    def test_get_nonexistent_dashboard(self, store: DashboardStore) -> None:
        """获取不存在的 Dashboard 应返回 None。"""
        layout = store.get("nonexistent-id")
        assert layout is None


# ---------------------------------------------------------------------------
# 测试: list_all
# ---------------------------------------------------------------------------


class TestDashboardStoreListAll:
    """list_all 方法测试。"""

    def test_list_all_returns_all(self, populated_store: DashboardStore) -> None:
        """list_all 应返回所有 Dashboard。"""
        result = populated_store.list_all()
        assert len(result) == 3

    def test_list_all_respects_limit(self, populated_store: DashboardStore) -> None:
        """list_all 应遵守 limit 参数。"""
        result = populated_store.list_all(limit=2)
        assert len(result) == 2

    def test_list_all_empty_store(self, store: DashboardStore) -> None:
        """空存储应返回空列表。"""
        result = store.list_all()
        assert result == []


# ---------------------------------------------------------------------------
# 测试: delete
# ---------------------------------------------------------------------------


class TestDashboardStoreDelete:
    """delete 方法测试。"""

    def test_delete_existing(self, populated_store: DashboardStore) -> None:
        """删除存在的 Dashboard 应返回 True。"""
        layouts = populated_store.list_all()
        dashboard_id = getattr(layouts[0], "dashboard_id", "")

        result = populated_store.delete(dashboard_id)
        assert result is True

    def test_delete_nonexistent(self, store: DashboardStore) -> None:
        """删除不存在的 Dashboard 应返回 False。"""
        result = store.delete("nonexistent-id")
        assert result is False

    def test_delete_removes_from_store(self, populated_store: DashboardStore) -> None:
        """删除后再次获取应返回 None。"""
        layouts = populated_store.list_all()
        dashboard_id = getattr(layouts[0], "dashboard_id", "")

        populated_store.delete(dashboard_id)
        assert populated_store.get(dashboard_id) is None
        assert len(populated_store.list_all()) == 2

    def test_delete_clears_created_at(self, populated_store: DashboardStore) -> None:
        """删除后 created_at 也应被清除。"""
        layouts = populated_store.list_all()
        dashboard_id = getattr(layouts[0], "dashboard_id", "")

        populated_store.delete(dashboard_id)
        assert populated_store.get_created_at(dashboard_id) is None


# ---------------------------------------------------------------------------
# 测试: update
# ---------------------------------------------------------------------------


class TestDashboardStoreUpdate:
    """update 方法测试。"""

    def test_update_title(self, populated_store: DashboardStore) -> None:
        """更新标题应生效。"""
        layouts = populated_store.list_all()
        dashboard_id = getattr(layouts[0], "dashboard_id", "")

        updated = populated_store.update(dashboard_id, {"title": "新标题"})
        assert updated is not None
        assert updated.title == "新标题"

    def test_update_description(self, populated_store: DashboardStore) -> None:
        """更新描述应生效。"""
        layouts = populated_store.list_all()
        dashboard_id = getattr(layouts[0], "dashboard_id", "")

        updated = populated_store.update(dashboard_id, {"description": "新描述"})
        assert updated is not None
        assert updated.description == "新描述"

    def test_update_add_panels(self, populated_store: DashboardStore) -> None:
        """添加面板应增加 panels 数量。"""
        layouts = populated_store.list_all()
        dashboard_id = getattr(layouts[0], "dashboard_id", "")
        original_panel_count = len(layouts[0].panels)

        updated = populated_store.update(dashboard_id, {
            "add_panels": [
                {"title": "新面板", "chart_type": "pie", "chart_config": {}, "data_source": {}},
            ],
        })
        assert updated is not None
        assert len(updated.panels) == original_panel_count + 1
        assert updated.panels[-1]["title"] == "新面板"

    def test_update_remove_panels(self, populated_store: DashboardStore) -> None:
        """移除面板应减少 panels 数量。"""
        layouts = populated_store.list_all()
        dashboard_id = getattr(layouts[0], "dashboard_id", "")
        panel_id = layouts[0].panels[0]["panel_id"]

        updated = populated_store.update(dashboard_id, {
            "remove_panel_ids": [panel_id],
        })
        assert updated is not None
        panel_ids = [p["panel_id"] for p in updated.panels]
        assert panel_id not in panel_ids

    def test_update_nonexistent(self, store: DashboardStore) -> None:
        """更新不存在的 Dashboard 应返回 None。"""
        result = store.update("nonexistent-id", {"title": "新标题"})
        assert result is None

    def test_update_none_title_ignored(self, populated_store: DashboardStore) -> None:
        """title 为 None 时不应更新。"""
        layouts = populated_store.list_all()
        dashboard_id = getattr(layouts[0], "dashboard_id", "")
        original_title = layouts[0].title

        updated = populated_store.update(dashboard_id, {"title": None})
        assert updated is not None
        assert updated.title == original_title


# ---------------------------------------------------------------------------
# 测试: clear
# ---------------------------------------------------------------------------


class TestDashboardStoreClear:
    """clear 方法测试。"""

    def test_clear_empties_store(self, populated_store: DashboardStore) -> None:
        """clear 后存储应为空。"""
        populated_store.clear()
        assert populated_store.list_all() == []
        assert len(populated_store._dashboards) == 0
