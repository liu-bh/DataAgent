"""数据脱敏器。

对查询结果中的敏感字段进行脱敏处理，支持多种脱敏策略和通配符列名匹配。
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

import structlog

from datapilot_queryexec.rbac.models import MaskRule

logger = structlog.get_logger(__name__)


class DataMasker:
    """数据脱敏器，对查询结果进行敏感字段脱敏。

    支持四种脱敏方式：
    - full: 完全替换为固定字符
    - partial: 正则部分替换
    - hash: MD5 哈希
    - replace: 固定字符串替换

    列名匹配支持通配符 *，如 *email* 可匹配 user_email、work_email 等。
    """

    BUILTIN_RULES: dict[str, MaskRule] = {
        "phone": MaskRule(
            column_name="*phone*",
            mask_type="partial",
            pattern=r"(\d{3})\d{4}(\d{4})",
            replacement=r"\1****\2",
            examples=["138****1234"],
        ),
        "id_card": MaskRule(
            column_name="*id_card*",
            mask_type="partial",
            pattern=r"(\d{6})\d{8}(\d{4})",
            replacement=r"\1********\2",
            examples=["110********1234"],
        ),
        "bank_card": MaskRule(
            column_name="*bank*",
            mask_type="partial",
            pattern=r"(\d{4})\d+(\d{4})",
            replacement=r"\1****\2",
            examples=["6222****1234"],
        ),
        "email": MaskRule(
            column_name="*email*",
            mask_type="partial",
            pattern=r"(.{2}).+(@.+)",
            replacement=r"\1***\2",
            examples=["zh***@example.com"],
        ),
    }

    def __init__(self, custom_rules: list[MaskRule] | None = None) -> None:
        """初始化脱敏器。

        Args:
            custom_rules: 自定义脱敏规则，会覆盖同名的内置规则。
        """
        self._rules: list[MaskRule] = list(self.BUILTIN_RULES.values())
        if custom_rules:
            for rule in custom_rules:
                self.add_rule(rule)

    def add_rule(self, rule: MaskRule) -> None:
        """添加自定义脱敏规则。

        如果规则中的列名通配符模式与已有规则重复，将追加到规则列表中（不覆盖内置规则）。

        Args:
            rule: 脱敏规则。
        """
        self._rules.append(rule)
        logger.debug("脱敏规则: 添加自定义规则", column=rule.column_name, mask_type=rule.mask_type)

    def mask_row(
        self, row: dict[str, Any], columns: list[str]
    ) -> tuple[dict[str, Any], list[str]]:
        """对单行数据执行脱敏。

        Args:
            row: 原始数据行（字典形式）。
            columns: 需要检查脱敏的列名列表。

        Returns:
            (masked_row, masked_column_names): 脱敏后的行和被脱敏的列名列表。
        """
        masked_row = dict(row)
        masked_columns: list[str] = []

        for col in columns:
            if col not in masked_row:
                continue

            value = masked_row[col]
            if value is None or not isinstance(value, str):
                continue

            matched_rule = self._find_rule(col)
            if matched_rule is None:
                continue

            masked_value = self._apply_mask(value, matched_rule)
            if masked_value != value:
                masked_row[col] = masked_value
                masked_columns.append(col)

        return masked_row, masked_columns

    def mask_result(
        self, rows: list[dict[str, Any]], columns: list[str]
    ) -> tuple[list[dict[str, Any]], list[str]]:
        """对整个结果集执行脱敏。

        Args:
            rows: 原始结果集（字典列表）。
            columns: 需要检查脱敏的列名列表。

        Returns:
            (masked_rows, masked_column_names): 脱敏后的结果集和被脱敏的列名列表（去重）。
        """
        if not rows:
            return [], []

        all_masked_columns: set[str] = set()
        masked_rows: list[dict[str, Any]] = []

        for row in rows:
            masked_row, masked_cols = self.mask_row(row, columns)
            masked_rows.append(masked_row)
            all_masked_columns.update(masked_cols)

        return masked_rows, sorted(all_masked_columns)

    def _find_rule(self, column_name: str) -> MaskRule | None:
        """根据列名查找匹配的脱敏规则。

        使用通配符匹配：规则中的 * 匹配任意字符序列。

        Args:
            column_name: 实际列名。

        Returns:
            匹配的脱敏规则，如果没有匹配则返回 None。
        """
        for rule in self._rules:
            if self._match_wildcard(rule.column_name, column_name):
                return rule
        return None

    @staticmethod
    def _match_wildcard(pattern: str, column_name: str) -> bool:
        """通配符匹配。

        将通配符模式中的 * 转换为正则表达式 .* 进行匹配。
        匹配是大小写不敏感的。

        Args:
            pattern: 通配符模式（如 *email*）。
            column_name: 实际列名。

        Returns:
            是否匹配。
        """
        # 转义正则特殊字符，然后将 * 替换为 .*
        escaped = re.escape(pattern).replace(r"\*", ".*")
        return bool(re.fullmatch(escaped, column_name, re.IGNORECASE))

    @staticmethod
    def _apply_mask(value: str, rule: MaskRule) -> str:
        """根据脱敏规则对值执行脱敏。

        Args:
            value: 原始值。
            rule: 脱敏规则。

        Returns:
            脱敏后的值。
        """
        mask_type = rule.mask_type.lower()

        if mask_type == "full":
            # 完全替换为固定字符
            return rule.replacement

        if mask_type == "partial":
            # 正则部分替换
            if rule.pattern:
                return re.sub(rule.pattern, rule.replacement, value)
            # 没有正则模式时，保留首尾字符
            if len(value) <= 2:
                return rule.replacement
            return value[0] + rule.replacement + value[-1]

        if mask_type == "hash":
            # MD5 哈希
            return hashlib.md5(value.encode("utf-8")).hexdigest()

        if mask_type == "replace":
            # 固定字符串替换
            return rule.replacement

        # 未知脱敏类型，原样返回
        logger.warning("脱敏: 未知的脱敏类型", mask_type=mask_type)
        return value
