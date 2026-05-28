"""允许模块清单单元测试。"""

from __future__ import annotations

from datapilot_sandbox.allowed_modules import DEFAULT_ALLOWED_MODULES


class TestDefaultAllowedModules:
    """DEFAULT_ALLOWED_MODULES 测试。"""

    def test_is_list(self) -> None:
        """允许模块清单应为列表。"""
        assert isinstance(DEFAULT_ALLOWED_MODULES, list)

    def test_not_empty(self) -> None:
        """允许模块清单不应为空。"""
        assert len(DEFAULT_ALLOWED_MODULES) > 0

    def test_all_strings(self) -> None:
        """所有模块名应为字符串。"""
        for module in DEFAULT_ALLOWED_MODULES:
            assert isinstance(module, str), f"模块名应为字符串: {module!r}"

    def test_no_empty_strings(self) -> None:
        """不应包含空字符串。"""
        assert "" not in DEFAULT_ALLOWED_MODULES

    def test_no_duplicates(self) -> None:
        """不应包含重复模块名。"""
        assert len(DEFAULT_ALLOWED_MODULES) == len(set(DEFAULT_ALLOWED_MODULES))

    def test_contains_math(self) -> None:
        """应包含 math 模块。"""
        assert "math" in DEFAULT_ALLOWED_MODULES

    def test_contains_json(self) -> None:
        """应包含 json 模块。"""
        assert "json" in DEFAULT_ALLOWED_MODULES

    def test_contains_statistics(self) -> None:
        """应包含 statistics 模块。"""
        assert "statistics" in DEFAULT_ALLOWED_MODULES

    def test_contains_pandas(self) -> None:
        """应包含 pandas 模块。"""
        assert "pandas" in DEFAULT_ALLOWED_MODULES

    def test_contains_numpy(self) -> None:
        """应包含 numpy 模块。"""
        assert "numpy" in DEFAULT_ALLOWED_MODULES

    def test_does_not_contain_os(self) -> None:
        """不应包含 os 模块。"""
        assert "os" not in DEFAULT_ALLOWED_MODULES

    def test_does_not_contain_subprocess(self) -> None:
        """不应包含 subprocess 模块。"""
        assert "subprocess" not in DEFAULT_ALLOWED_MODULES

    def test_does_not_contain_socket(self) -> None:
        """不应包含 socket 模块。"""
        assert "socket" not in DEFAULT_ALLOWED_MODULES

    def test_does_not_contain_ctypes(self) -> None:
        """不应包含 ctypes 模块。"""
        assert "ctypes" not in DEFAULT_ALLOWED_MODULES

    def test_does_not_contain_multiprocessing(self) -> None:
        """不应包含 multiprocessing 模块。"""
        assert "multiprocessing" not in DEFAULT_ALLOWED_MODULES

    def test_does_not_contain_threading(self) -> None:
        """不应包含 threading 模块。"""
        assert "threading" not in DEFAULT_ALLOWED_MODULES

    def test_contains_itertools(self) -> None:
        """应包含 itertools 模块。"""
        assert "itertools" in DEFAULT_ALLOWED_MODULES

    def test_contains_collections(self) -> None:
        """应包含 collections 模块。"""
        assert "collections" in DEFAULT_ALLOWED_MODULES

    def test_contains_datetime(self) -> None:
        """应包含 datetime 模块。"""
        assert "datetime" in DEFAULT_ALLOWED_MODULES

    def test_contains_re(self) -> None:
        """应包含 re 模块。"""
        assert "re" in DEFAULT_ALLOWED_MODULES

    def test_does_not_contain_pickle(self) -> None:
        """不应包含 pickle 模块（反序列化安全风险）。"""
        assert "pickle" not in DEFAULT_ALLOWED_MODULES

    def test_does_not_contain_shutil(self) -> None:
        """不应包含 shutil 模块（文件操作风险）。"""
        assert "shutil" not in DEFAULT_ALLOWED_MODULES

    def test_contains_sklearn(self) -> None:
        """应包含 sklearn 模块。"""
        assert "sklearn" in DEFAULT_ALLOWED_MODULES

    def test_contains_scipy(self) -> None:
        """应包含 scipy 模块。"""
        assert "scipy" in DEFAULT_ALLOWED_MODULES

    def test_contains_matplotlib(self) -> None:
        """应包含 matplotlib 模块。"""
        assert "matplotlib" in DEFAULT_ALLOWED_MODULES

    def test_does_not_contain_signal(self) -> None:
        """不应包含 signal 模块（信号操作风险）。"""
        assert "signal" not in DEFAULT_ALLOWED_MODULES

    def test_does_not_contain_importlib(self) -> None:
        """不应包含 importlib 模块（动态导入风险）。"""
        assert "importlib" not in DEFAULT_ALLOWED_MODULES
