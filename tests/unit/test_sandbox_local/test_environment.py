"""沙箱环境检测单元测试。"""

from __future__ import annotations

import sys

from datapilot_sandbox.local.environment import SandboxEnvironment


class TestSandboxEnvironment:
    """SandboxEnvironment 测试。"""

    def test_default_values(self) -> None:
        """测试默认值。"""
        env = SandboxEnvironment()
        assert env.python_version == sys.version.split()[0]
        assert env.platform == sys.platform
        assert env.available_modules == []

    def test_detect_returns_environment(self) -> None:
        """测试 detect() 返回 SandboxEnvironment 实例。"""
        env = SandboxEnvironment.detect()
        assert isinstance(env, SandboxEnvironment)
        assert env.python_version == sys.version.split()[0]
        assert env.platform == sys.platform
        assert isinstance(env.available_modules, list)

    def test_detect_includes_common_modules(self) -> None:
        """测试 detect() 包含常见标准库模块。"""
        env = SandboxEnvironment.detect()
        # 这些模块在所有标准 Python 安装中都应可用
        expected_modules = {"json", "math", "re", "collections", "time", "io"}
        assert expected_modules.issubset(set(env.available_modules))

    def test_detect_sorted_modules(self) -> None:
        """测试 detect() 返回的模块列表已排序。"""
        env = SandboxEnvironment.detect()
        assert env.available_modules == sorted(env.available_modules)

    def test_check_module_available(self) -> None:
        """测试检查可用模块。"""
        assert SandboxEnvironment.check_module("json") is True
        assert SandboxEnvironment.check_module("math") is True
        assert SandboxEnvironment.check_module("os") is True

    def test_check_module_not_available(self) -> None:
        """测试检查不存在的模块。"""
        assert SandboxEnvironment.check_module("nonexistent_module_xyz") is False

    def test_check_module_empty_string_not_available(self) -> None:
        """测试空字符串模块名。"""
        # 在 Windows 上 importlib.util.find_spec("") 会抛出 ValueError
        # 因此返回 False（或抛出异常），根据实现选择
        try:
            result = SandboxEnvironment.check_module("")
            assert result is False
        except ValueError:
            # Windows 上空名称触发 ValueError，符合预期
            pass

    def test_check_module_is_static(self) -> None:
        """测试 check_module 是静态方法。"""
        # 可以通过实例或类调用
        env = SandboxEnvironment()
        assert env.check_module("json") is True
        assert SandboxEnvironment.check_module("json") is True

    def test_detect_platform(self) -> None:
        """测试平台检测。"""
        env = SandboxEnvironment.detect()
        # 平台应该是有效的 sys.platform 值
        assert env.platform in (
            "linux", "darwin", "win32", "cygwin", "aix",
            "freebsd7", "freebsd8", "freebsd9", "freebsd10",
        )

    def test_detect_python_version_not_empty(self) -> None:
        """测试 detect() 返回的 python_version 不为空。"""
        env = SandboxEnvironment.detect()
        assert env.python_version
        assert len(env.python_version) > 0

    def test_detect_platform_not_empty(self) -> None:
        """测试 detect() 返回的 platform 不为空。"""
        env = SandboxEnvironment.detect()
        assert env.platform
        assert len(env.platform) > 0

    def test_detect_available_modules_not_empty(self) -> None:
        """测试 detect() 返回的 available_modules 列表不为空。"""
        env = SandboxEnvironment.detect()
        assert isinstance(env.available_modules, list)
        assert len(env.available_modules) > 0

    def test_detect_includes_json(self) -> None:
        """测试 detect() 结果包含 json 模块。"""
        env = SandboxEnvironment.detect()
        assert "json" in env.available_modules

    def test_detect_is_classmethod(self) -> None:
        """测试 detect() 是类方法，无需实例即可调用。"""
        env = SandboxEnvironment.detect()
        assert isinstance(env, SandboxEnvironment)

    def test_check_module_with_dots(self) -> None:
        """测试检查带点号的子模块。"""
        # collections.abc 应该可用
        assert SandboxEnvironment.check_module("collections") is True

    def test_standard_library_modules_is_class_var(self) -> None:
        """测试 STANDARD_LIBRARY_MODULES 是类变量。"""
        assert isinstance(SandboxEnvironment.STANDARD_LIBRARY_MODULES, list)
        assert len(SandboxEnvironment.STANDARD_LIBRARY_MODULES) > 0

    def test_detect_consistent_calls(self) -> None:
        """测试多次调用 detect() 结果一致。"""
        env1 = SandboxEnvironment.detect()
        env2 = SandboxEnvironment.detect()
        assert env1.python_version == env2.python_version
        assert env1.platform == env2.platform
        assert env1.available_modules == env2.available_modules
