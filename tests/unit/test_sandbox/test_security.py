"""代码安全检查器单元测试。"""

from __future__ import annotations

from datapilot_sandbox.models import SecurityLevel
from datapilot_sandbox.security import CodeSecurityChecker


class TestCodeSecurityChecker:
    """CodeSecurityChecker 测试。"""

    def setup_method(self) -> None:
        """每个测试方法前初始化检查器。"""
        self.checker = CodeSecurityChecker()

    # --- 安全代码 ---

    def test_safe_code_no_issues(self) -> None:
        """安全的纯计算代码不应产生任何问题。"""
        code = """
import math
result = math.sqrt(16)
print(result)
"""
        issues = self.checker.check(code)
        assert len(issues) == 0

    def test_safe_import_collections(self) -> None:
        """安全的标准库导入不应产生问题。"""
        code = "from collections import Counter"
        issues = self.checker.check(code)
        assert len(issues) == 0

    def test_safe_json_import(self) -> None:
        """json 模块是安全的。"""
        code = 'import json\ndata = json.loads(\'{"a": 1}\')'
        issues = self.checker.check(code)
        assert len(issues) == 0

    def test_safe_open_read_only(self) -> None:
        """open() 只读模式不应报错。"""
        code = """
with open("data.txt", "r") as f:
    content = f.read()
"""
        issues = self.checker.check(code)
        assert len(issues) == 0

    def test_safe_open_no_mode(self) -> None:
        """open() 无模式参数（默认只读）不应报错。"""
        code = """
with open("data.txt") as f:
    content = f.read()
"""
        issues = self.checker.check(code)
        assert len(issues) == 0

    def test_empty_code(self) -> None:
        """空代码不应产生问题。"""
        issues = self.checker.check("")
        assert len(issues) == 0

    def test_safe_re_import(self) -> None:
        """re 模块是安全的。"""
        code = 'import re\npattern = re.compile(r"\\d+")'
        issues = self.checker.check(code)
        assert len(issues) == 0

    # --- 危险 import ---

    def test_import_os(self) -> None:
        """import os 应报错。"""
        code = "import os"
        issues = self.checker.check(code)
        assert len(issues) == 1
        assert issues[0].level == SecurityLevel.ERROR
        assert issues[0].node_type == "Import"
        assert "os" in issues[0].message

    def test_import_subprocess(self) -> None:
        """import subprocess 应报错。"""
        code = "import subprocess"
        issues = self.checker.check(code)
        assert len(issues) == 1
        assert issues[0].level == SecurityLevel.ERROR
        assert "subprocess" in issues[0].message

    def test_import_ctypes(self) -> None:
        """import ctypes 应报错。"""
        code = "import ctypes"
        issues = self.checker.check(code)
        assert len(issues) == 1
        assert issues[0].level == SecurityLevel.ERROR

    def test_import_multiprocessing(self) -> None:
        """import multiprocessing 应报错。"""
        code = "import multiprocessing"
        issues = self.checker.check(code)
        assert len(issues) == 1
        assert issues[0].level == SecurityLevel.ERROR

    def test_import_threading(self) -> None:
        """import threading 应报错。"""
        code = "import threading"
        issues = self.checker.check(code)
        assert len(issues) == 1
        assert issues[0].level == SecurityLevel.ERROR

    def test_import_socket(self) -> None:
        """import socket 应报错。"""
        code = "import socket"
        issues = self.checker.check(code)
        assert len(issues) == 1
        assert issues[0].level == SecurityLevel.ERROR

    def test_import_os_path(self) -> None:
        """import os.path 也应报错（os 是顶层禁止模块）。"""
        code = "import os.path"
        issues = self.checker.check(code)
        assert len(issues) == 1
        assert issues[0].level == SecurityLevel.ERROR
        assert "os" in issues[0].message

    def test_from_import_os(self) -> None:
        """from os import system 应报错。"""
        code = "from os import system"
        issues = self.checker.check(code)
        assert len(issues) == 1
        assert issues[0].level == SecurityLevel.ERROR
        assert issues[0].node_type == "ImportFrom"

    def test_from_import_subprocess(self) -> None:
        """from subprocess import run 应报错。"""
        code = "from subprocess import run"
        issues = self.checker.check(code)
        assert len(issues) == 1
        assert issues[0].level == SecurityLevel.ERROR

    def test_from_import_pickle(self) -> None:
        """from pickle import loads 应报错。"""
        code = "from pickle import loads"
        issues = self.checker.check(code)
        assert len(issues) == 1
        assert issues[0].level == SecurityLevel.ERROR

    def test_import_shutil(self) -> None:
        """import shutil 应报错。"""
        code = "import shutil"
        issues = self.checker.check(code)
        assert len(issues) == 1
        assert issues[0].level == SecurityLevel.ERROR

    def test_import_ftplib(self) -> None:
        """import ftplib 应报错。"""
        code = "import ftplib"
        issues = self.checker.check(code)
        assert len(issues) == 1
        assert issues[0].level == SecurityLevel.ERROR

    def test_import_smtplib(self) -> None:
        """import smtplib 应报错。"""
        code = "import smtplib"
        issues = self.checker.check(code)
        assert len(issues) == 1
        assert issues[0].level == SecurityLevel.ERROR

    # --- 危险函数调用 ---

    def test_exec_call(self) -> None:
        """直接调用 exec() 应报错。"""
        code = 'exec("print(1)")'
        issues = self.checker.check(code)
        assert any(i.level == SecurityLevel.ERROR and "exec" in i.message for i in issues)

    def test_eval_call(self) -> None:
        """直接调用 eval() 应报错。"""
        code = 'eval("1 + 1")'
        issues = self.checker.check(code)
        assert any(i.level == SecurityLevel.ERROR and "eval" in i.message for i in issues)

    def test_compile_call(self) -> None:
        """直接调用 compile() 应报错。"""
        code = 'compile("1+1", "<string>", "eval")'
        issues = self.checker.check(code)
        assert any(i.level == SecurityLevel.ERROR and "compile" in i.message for i in issues)

    def test_double_underscore_import_call(self) -> None:
        """直接调用 __import__() 应报错。"""
        code = '__import__("os")'
        issues = self.checker.check(code)
        assert any(
            i.level == SecurityLevel.ERROR and "__import__" in i.message for i in issues
        )

    def test_os_system_call(self) -> None:
        """os.system() 调用应报错。"""
        code = """
import os
os.system("ls")
"""
        issues = self.checker.check(code)
        # 至少有两个问题：import os + os.system 调用
        assert len(issues) >= 2
        assert any("os.system" in i.message and i.level == SecurityLevel.ERROR for i in issues)

    def test_os_popen_call(self) -> None:
        """os.popen() 调用应报错。"""
        code = """
import os
os.popen("ls")
"""
        issues = self.checker.check(code)
        assert any("os.popen" in i.message for i in issues)

    def test_subprocess_run_call(self) -> None:
        """subprocess.run() 调用应报错。"""
        code = """
import subprocess
subprocess.run(["ls", "-l"])
"""
        issues = self.checker.check(code)
        assert any("subprocess.run" in i.message for i in issues)

    def test_subprocess_popen_call(self) -> None:
        """subprocess.Popen() 调用应报错。"""
        code = """
import subprocess
subprocess.Popen(["echo", "hello"])
"""
        issues = self.checker.check(code)
        assert any("subprocess.Popen" in i.message for i in issues)

    def test_subprocess_check_output_call(self) -> None:
        """subprocess.check_output() 调用应报错。"""
        code = """
import subprocess
result = subprocess.check_output(["ls"])
"""
        issues = self.checker.check(code)
        assert any("subprocess.check_output" in i.message for i in issues)

    def test_subprocess_call_call(self) -> None:
        """subprocess.call() 调用应报错。"""
        code = """
import subprocess
subprocess.call(["ls"])
"""
        issues = self.checker.check(code)
        assert any("subprocess.call" in i.message for i in issues)

    def test_sys_exit_call(self) -> None:
        """sys.exit() 调用应报错。"""
        code = """
import sys
sys.exit(1)
"""
        issues = self.checker.check(code)
        assert any(
            "sys.exit" in i.message and i.level == SecurityLevel.ERROR for i in issues
        )

    def test_os_exit_call(self) -> None:
        """os._exit() 调用应报错。"""
        code = """
import os
os._exit(1)
"""
        issues = self.checker.check(code)
        assert any(
            "os._exit" in i.message and i.level == SecurityLevel.ERROR for i in issues
        )

    # --- 文件写入 ---

    def test_open_write_mode(self) -> None:
        """open() 写模式应报错。"""
        code = '''
open("output.txt", "w")
'''
        issues = self.checker.check(code)
        assert any("写模式" in i.message and i.level == SecurityLevel.ERROR for i in issues)

    def test_open_append_mode(self) -> None:
        """open() 追加模式应报错。"""
        code = '''
open("output.txt", "a")
'''
        issues = self.checker.check(code)
        assert any("写模式" in i.message and i.level == SecurityLevel.ERROR for i in issues)

    def test_open_exclusive_mode(self) -> None:
        """open() 独占创建模式应报错。"""
        code = '''
open("output.txt", "x")
'''
        issues = self.checker.check(code)
        assert any("写模式" in i.message and i.level == SecurityLevel.ERROR for i in issues)

    def test_open_write_binary_mode(self) -> None:
        """open() 二进制写模式应报错。"""
        code = '''
open("output.bin", "wb")
'''
        issues = self.checker.check(code)
        assert any("写模式" in i.message and i.level == SecurityLevel.ERROR for i in issues)

    def test_open_write_plus_mode(self) -> None:
        """open() w+ 模式应报错。"""
        code = '''
open("output.txt", "w+")
'''
        issues = self.checker.check(code)
        assert any("写模式" in i.message and i.level == SecurityLevel.ERROR for i in issues)

    def test_open_keyword_write_mode(self) -> None:
        """open() 使用 mode 关键字参数的写模式应报错。"""
        code = '''
open("output.txt", mode="w")
'''
        issues = self.checker.check(code)
        assert any("写模式" in i.message and i.level == SecurityLevel.ERROR for i in issues)

    # --- 网络操作 ---

    def test_import_http_client(self) -> None:
        """import http.client 应报错。"""
        code = "import http.client"
        issues = self.checker.check(code)
        assert len(issues) == 1
        assert issues[0].level == SecurityLevel.ERROR

    def test_import_urllib_request(self) -> None:
        """import urllib.request 应报错。"""
        code = "import urllib.request"
        issues = self.checker.check(code)
        assert len(issues) == 1
        assert issues[0].level == SecurityLevel.ERROR

    def test_from_import_urllib(self) -> None:
        """from urllib.request import urlopen 应报错。"""
        code = "from urllib.request import urlopen"
        issues = self.checker.check(code)
        assert len(issues) == 1
        assert issues[0].level == SecurityLevel.ERROR

    # --- 语法错误 ---

    def test_syntax_error(self) -> None:
        """语法错误的代码应返回错误。"""
        code = "def foo(:\n    pass"
        issues = self.checker.check(code)
        assert len(issues) == 1
        assert issues[0].level == SecurityLevel.ERROR
        assert "语法错误" in issues[0].message

    # --- 多个问题 ---

    def test_multiple_issues_sorted_by_line(self) -> None:
        """多个问题应按行号排序返回。"""
        code = """import os
import subprocess
import math
import threading
"""
        issues = self.checker.check(code)
        # 三个禁止导入：os(1), subprocess(2), threading(4)
        assert len(issues) == 3
        lines = [i.line for i in issues]
        assert lines == sorted(lines)
        assert lines[0] == 1  # os
        assert lines[1] == 2  # subprocess
        assert lines[2] == 4  # threading

    def test_mixed_dangerous_operations(self) -> None:
        """混合多种危险操作应全部检测出来。"""
        code = """import os
os.system("rm -rf /")
exec("print('hello')")
"""
        issues = self.checker.check(code)
        assert len(issues) >= 3
        for i in issues:
            assert i.level in (SecurityLevel.ERROR, SecurityLevel.WARNING)

    # --- 属性访问检查 ---

    def test_dangerous_attribute_access(self) -> None:
        """访问 os.system 属性应产生警告。"""
        code = """
import os
func = os.system
"""
        issues = self.checker.check(code)
        assert any(
            "危险属性" in i.message and i.level == SecurityLevel.WARNING for i in issues
        )

    # --- 安全的第三方库导入 ---

    def test_safe_import_pandas(self) -> None:
        """import pandas 是安全的，不应报错。"""
        code = "import pandas"
        issues = self.checker.check(code)
        assert len(issues) == 0

    def test_safe_import_numpy(self) -> None:
        """import numpy 是安全的，不应报错。"""
        code = "import numpy"
        issues = self.checker.check(code)
        assert len(issues) == 0

    def test_safe_import_sklearn(self) -> None:
        """import sklearn 是安全的，不应报错。"""
        code = "import sklearn"
        issues = self.checker.check(code)
        assert len(issues) == 0

    def test_safe_import_math(self) -> None:
        """import math 是安全的，不应报错。"""
        code = "import math"
        issues = self.checker.check(code)
        assert len(issues) == 0

    def test_safe_import_statistics(self) -> None:
        """import statistics 是安全的，不应报错。"""
        code = "import statistics"
        issues = self.checker.check(code)
        assert len(issues) == 0

    # --- 纯计算代码 ---

    def test_safe_pure_computation(self) -> None:
        """纯计算代码（print, range, sum）不应报错。"""
        code = """
result = sum(range(1, 101))
print(f"1到100的和: {result}")
"""
        issues = self.checker.check(code)
        assert len(issues) == 0

    def test_safe_list_comprehension(self) -> None:
        """列表推导式不应报错。"""
        code = """
squares = [x**2 for x in range(10)]
evens = [x for x in squares if x % 2 == 0]
"""
        issues = self.checker.check(code)
        assert len(issues) == 0

    def test_safe_lambda_and_map(self) -> None:
        """lambda 和 map/filter 不应报错。"""
        code = """
numbers = [1, 2, 3, 4, 5]
doubled = list(map(lambda x: x * 2, numbers))
filtered = list(filter(lambda x: x > 3, doubled))
"""
        issues = self.checker.check(code)
        assert len(issues) == 0

    def test_safe_function_definition(self) -> None:
        """函数定义不应报错。"""
        code = """
def fibonacci(n: int) -> list[int]:
    if n <= 1:
        return [0]
    fib = [0, 1]
    for i in range(2, n):
        fib.append(fib[i-1] + fib[i-2])
    return fib

result = fibonacci(10)
print(result)
"""
        issues = self.checker.check(code)
        assert len(issues) == 0

    def test_safe_class_definition(self) -> None:
        """类定义不应报错。"""
        code = """
class DataPoint:
    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y

    def distance_to_origin(self) -> float:
        return (self.x**2 + self.y**2) ** 0.5
"""
        issues = self.checker.check(code)
        assert len(issues) == 0

    def test_safe_dict_and_set_operations(self) -> None:
        """字典和集合操作不应报错。"""
        code = """
data = {"a": 1, "b": 2, "c": 3}
keys = set(data.keys())
values = list(data.values())
merged = {**data, "d": 4}
"""
        issues = self.checker.check(code)
        assert len(issues) == 0

    # --- import sys（不在 DANGEROUS_IMPORTS 中，但 sys.exit() 调用会被检测） ---

    def test_import_sys_not_in_dangerous_imports(self) -> None:
        """import sys 本身不在 AST 检查器的禁止导入列表中。

        注意：sys 在 SandboxConfig.forbidden_modules 中被禁止，
        但 CodeSecurityChecker.DANGEROUS_IMPORTS 不包含 sys。
        sys.exit() 的调用通过 _check_call 中的 exit 属性检测。
        """
        code = "import sys"
        issues = self.checker.check(code)
        assert len(issues) == 0

    def test_from_import_sys_not_in_dangerous_imports(self) -> None:
        """from sys import ... 本身不在 AST 检查器的禁止导入列表中。"""
        code = "from sys import version"
        issues = self.checker.check(code)
        assert len(issues) == 0

    # --- 其他边界情况 ---

    def test_syntax_error_reports_line_number(self) -> None:
        """语法错误应报告正确的行号。"""
        code = "x = 1\ny = 2\ndef (\n"
        issues = self.checker.check(code)
        assert len(issues) == 1
        assert issues[0].rule == "syntax_error"
        assert issues[0].line == 3

    def test_import_importlib_not_in_dangerous_imports(self) -> None:
        """import importlib 本身不在 AST 检查器的禁止导入列表中。

        注意：importlib 在 SandboxConfig.forbidden_modules 中被禁止，
        但 CodeSecurityChecker.DANGEROUS_IMPORTS 不包含 importlib。
        """
        code = "import importlib"
        issues = self.checker.check(code)
        assert len(issues) == 0

    def test_safe_multiple_safe_imports(self) -> None:
        """多个安全的 import 语句不应报错。"""
        code = """
import math
import json
import re
from collections import Counter
from statistics import mean
"""
        issues = self.checker.check(code)
        assert len(issues) == 0

    def test_check_resets_between_calls(self) -> None:
        """多次调用 check 方法之间应重置内部状态。"""
        code_bad = "import os"
        code_good = "import math"
        issues_bad = self.checker.check(code_bad)
        issues_good = self.checker.check(code_good)
        assert len(issues_bad) == 1
        assert len(issues_good) == 0
