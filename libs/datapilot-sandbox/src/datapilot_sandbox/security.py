"""AST 级代码安全检查。

通过遍历 Python AST（抽象语法树），检测代码中是否存在危险操作，
包括：进程调用、文件写入、网络访问、动态执行等。
"""

from __future__ import annotations

import ast

from datapilot_sandbox.models import CodeSecurityIssue, SecurityLevel


class CodeSecurityChecker:
    """AST 级代码安全检查器。

    检查 Python 代码中是否存在危险操作：
    - os.system, os.popen, subprocess 调用
    - import os 后的危险操作
    - exec, eval, compile 动态执行
    - 文件 I/O（open + 写模式 w/a/x）
    - 网络操作（socket, http.client, urllib）
    - import ctypes（C 扩展加载）
    - import multiprocessing / threading（进程/线程创建）
    - __import__ 动态导入
    - sys.exit / os._exit（强制退出）
    """

    # 危险的函数调用名称
    DANGEROUS_CALLS: set[str] = {
        "system", "popen", "run", "Popen", "call", "check_output", "check_call",
    }

    # 禁止导入的模块（顶层模块名）
    DANGEROUS_IMPORTS: set[str] = {
        "os",
        "subprocess",
        "ctypes",
        "multiprocessing",
        "threading",
        "socket",
        "http",
        "urllib",
        "ftplib",
        "smtplib",
        "pickle",
        "shelve",
        "shutil",
    }

    # 禁止的属性访问
    FORBIDDEN_ATTRS: set[str] = {
        "system", "popen", "spawn", "kill", "exec", "eval", "compile",
    }

    # 禁止直接调用的内置函数名称
    FORBIDDEN_BUILTINS: set[str] = {"exec", "eval", "compile", "__import__"}

    def __init__(self) -> None:
        self._issues: list[CodeSecurityIssue] = []
        self._imported_modules: set[str] = set()

    def check(self, code: str) -> list[CodeSecurityIssue]:
        """检查代码安全性，返回问题列表。

        如果存在 error 级别问题，代码不应被执行。

        Args:
            code: 待检查的 Python 源代码。

        Returns:
            安全问题列表，按行号排序。
        """
        self._issues = []
        self._imported_modules = set()

        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return [
                CodeSecurityIssue(
                    level=SecurityLevel.ERROR,
                    rule="syntax_error",
                    line=e.lineno or 0,
                    message=f"语法错误: {e.msg}",
                    node_type="SyntaxError",
                )
            ]

        self._visit(tree)
        # 按行号排序
        self._issues.sort(key=lambda issue: issue.line)
        return self._issues

    def _visit(self, node: ast.AST) -> None:
        """递归遍历 AST 节点。"""
        for child in ast.iter_child_nodes(node):
            self._check_node(child)
            self._visit(child)

    def _check_node(self, node: ast.AST) -> None:
        """检查单个 AST 节点的安全性。"""
        if isinstance(node, ast.Import):
            self._check_import(node)
        elif isinstance(node, ast.ImportFrom):
            self._check_import_from(node)
        elif isinstance(node, ast.Call):
            self._check_call(node)
        elif isinstance(node, ast.Attribute):
            self._check_attribute(node)
        elif isinstance(node, ast.Name):
            self._check_name(node)

    def _check_import(self, node: ast.Import) -> None:
        """检查 import 语句。"""
        for alias in node.names:
            module_name = alias.name
            # 检查顶层模块名（支持 os, os.path 等）
            top_module = module_name.split(".")[0]
            if top_module in self.DANGEROUS_IMPORTS:
                self._issues.append(
                    CodeSecurityIssue(
                        level=SecurityLevel.ERROR,
                        rule="forbidden_import",
                        line=node.lineno,
                        message=f"禁止导入模块 '{module_name}'",
                        node_type="Import",
                    )
                )
            self._imported_modules.add(module_name)

    def _check_import_from(self, node: ast.ImportFrom) -> None:
        """检查 from ... import ... 语句。"""
        if node.module is None:
            return
        top_module = node.module.split(".")[0]
        if top_module in self.DANGEROUS_IMPORTS:
            self._issues.append(
                CodeSecurityIssue(
                    level=SecurityLevel.ERROR,
                    rule="forbidden_import",
                    line=node.lineno,
                    message=f"禁止从模块 '{node.module}' 导入",
                    node_type="ImportFrom",
                )
            )
        self._imported_modules.add(node.module)

    def _check_call(self, node: ast.Call) -> None:
        """检查函数调用。

        检测：
        1. exec/eval/compile/__import__ 直接调用
        2. os.system 等属性调用
        3. open() 的写模式调用
        4. subprocess.run 等调用
        """
        # 检查直接调用内置危险函数（exec, eval 等）
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
            if func_name in self.FORBIDDEN_BUILTINS:
                self._issues.append(
                    CodeSecurityIssue(
                        level=SecurityLevel.ERROR,
                        rule="forbidden_builtin",
                        line=node.lineno,
                        message=f"禁止调用内置函数 '{func_name}'",
                        node_type="Call",
                    )
                )

        # 检查 open() 的写模式（直接调用 open(...) 的情况）
        if isinstance(node.func, ast.Name) and node.func.id == "open" and self._has_write_mode(node):
            self._issues.append(
                CodeSecurityIssue(
                    level=SecurityLevel.ERROR,
                    rule="write_mode",
                    line=node.lineno,
                    message="禁止以写模式打开文件",
                    node_type="Call",
                )
            )

        # 检查属性调用：os.system, subprocess.run 等
        if isinstance(node.func, ast.Attribute):
            attr_name = node.func.attr

            # 检查 os.system 等危险调用
            if attr_name in self.DANGEROUS_CALLS:
                module = self._get_module_name(node.func.value)
                if module and module in self.DANGEROUS_IMPORTS:
                    self._issues.append(
                        CodeSecurityIssue(
                            level=SecurityLevel.ERROR,
                            rule="dangerous_call",
                            line=node.lineno,
                            message=f"禁止调用 '{module}.{attr_name}'",
                            node_type="Call",
                        )
                    )
                else:
                    # 即使模块不在导入列表中，也发出警告
                    self._issues.append(
                        CodeSecurityIssue(
                            level=SecurityLevel.WARNING,
                            rule="suspicious_call",
                            line=node.lineno,
                            message=f"可疑调用 '{attr_name}'，可能为危险操作",
                            node_type="Call",
                        )
                    )

            # 检查 os._exit / sys.exit
            if attr_name in {"exit", "_exit"}:
                module = self._get_module_name(node.func.value)
                if module in {"os", "sys"}:
                    self._issues.append(
                        CodeSecurityIssue(
                            level=SecurityLevel.ERROR,
                            rule="dangerous_call",
                            line=node.lineno,
                            message=f"禁止调用 '{module}.{attr_name}'",
                            node_type="Call",
                        )
                    )

            # 检查 open() 的写模式（属性形式，如 io.open）
            if attr_name == "open" and self._has_write_mode(node):
                self._issues.append(
                    CodeSecurityIssue(
                        level=SecurityLevel.ERROR,
                        rule="write_mode",
                        line=node.lineno,
                        message="禁止以写模式打开文件",
                        node_type="Call",
                    )
                )

    def _check_attribute(self, node: ast.Attribute) -> None:
        """检查属性访问。

        检测对危险属性的访问，如 os.system（即使未调用，也可能是传递引用）。
        """
        if node.attr in self.FORBIDDEN_ATTRS:
            module = self._get_module_name(node.value)
            if module and module in self.DANGEROUS_IMPORTS:
                self._issues.append(
                    CodeSecurityIssue(
                        level=SecurityLevel.WARNING,
                        rule="forbidden_attr",
                        line=node.lineno,
                        message=f"访问危险属性 '{module}.{node.attr}'",
                        node_type="Attribute",
                    )
                )

    def _check_name(self, node: ast.Name) -> None:
        """检查名字引用。

        检测 exec/eval/compile 作为变量名的直接引用。
        """
        # 在赋值上下文中不做检查（如 func = eval 是定义，不是调用）
        # 这里仅作为备用检测，主要在 _check_call 中处理
        pass

    def _get_module_name(self, node: ast.expr) -> str | None:
        """从 AST 节点推断模块名称。

        例如：Attribute(value=Name(id='os')) -> 'os'
              Attribute(value=Attribute(value=Name(id='os'), attr='path')) -> 'os.path'
        """
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            parent = self._get_module_name(node.value)
            if parent:
                return f"{parent}.{node.attr}"
            return None
        return None

    def _has_write_mode(self, call_node: ast.Call) -> bool:
        """检查 open() 调用是否使用了写模式。

        写模式包括：'w', 'w+', 'a', 'a+', 'x', 'x+', 'wb', 'ab', 'xb' 等。
        """
        # open() 的模式参数是第二个位置参数或 mode 关键字参数
        mode_value: str | None = None

        # 检查位置参数：open(file, mode='r')
        if len(call_node.args) >= 2:
            mode_arg = call_node.args[1]
            mode_value = self._get_string_value(mode_arg)

        # 检查关键字参数：open(file, mode='w')
        for keyword in call_node.keywords:
            if keyword.arg == "mode":
                mode_value = self._get_string_value(keyword.value)
                break

        if mode_value is None:
            return False

        # 检查模式是否包含写操作字符
        write_chars = {"w", "a", "x"}
        mode_lower = mode_value.lower()
        return any(c in mode_lower for c in write_chars)

    def _get_string_value(self, node: ast.expr) -> str | None:
        """从 AST 节点提取字符串常量值。"""
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        return None
