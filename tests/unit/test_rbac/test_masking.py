"""数据脱敏器单元测试。

覆盖 DataMasker 的各种场景：
- 内置规则：手机号、身份证、邮箱、银行卡
- 自定义规则
- full / partial / hash / replace 四种脱敏方式
- 通配符列名匹配
- 边界情况：空值、None、非字符串值
"""

from __future__ import annotations

import pytest

from datapilot_queryexec.rbac.masking import DataMasker
from datapilot_queryexec.rbac.models import MaskRule


class TestBuiltinPhoneMasking:
    """内置手机号脱敏测试。"""

    @pytest.fixture()
    def masker(self) -> DataMasker:
        """创建默认脱敏器。"""
        return DataMasker()

    def test_phone_masking(self, masker: DataMasker) -> None:
        """手机号中间四位替换为 ****。"""
        row = {"name": "张三", "user_phone": "13812345678"}
        masked_row, masked_cols = masker.mask_row(row, ["user_phone"])
        assert masked_row["user_phone"] == "138****5678"
        assert "user_phone" in masked_cols

    def test_phone_with_prefix(self, masker: DataMasker) -> None:
        """phone 在列名中间也可以匹配。"""
        row = {"mobile_phone": "13987654321"}
        masked_row, masked_cols = masker.mask_row(row, ["mobile_phone"])
        assert masked_row["mobile_phone"] == "139****4321"
        assert "mobile_phone" in masked_cols

    def test_phone_11_digits(self, masker: DataMasker) -> None:
        """标准 11 位手机号。"""
        row = {"phone": "15011112222"}
        masked_row, _ = masker.mask_row(row, ["phone"])
        assert masked_row["phone"] == "150****2222"


class TestBuiltinIdCardMasking:
    """内置身份证脱敏测试。"""

    @pytest.fixture()
    def masker(self) -> DataMasker:
        """创建默认脱敏器。"""
        return DataMasker()

    def test_id_card_masking(self, masker: DataMasker) -> None:
        """身份证中间 8 位替换。"""
        row = {"user_id_card": "110101199001011234"}
        masked_row, masked_cols = masker.mask_row(row, ["user_id_card"])
        assert masked_row["user_id_card"] == "110101********1234"
        assert "user_id_card" in masked_cols


class TestBuiltinBankCardMasking:
    """内置银行卡脱敏测试。"""

    @pytest.fixture()
    def masker(self) -> DataMasker:
        """创建默认脱敏器。"""
        return DataMasker()

    def test_bank_card_masking(self, masker: DataMasker) -> None:
        """银行卡号保留前四后四。"""
        row = {"bank_card": "6222021234567890123"}
        masked_row, masked_cols = masker.mask_row(row, ["bank_card"])
        assert masked_row["bank_card"] == "6222****0123"
        assert "bank_card" in masked_cols

    def test_bank_account_name(self, masker: DataMasker) -> None:
        """bank_card_no 列名也可匹配（通配符 *bank*）。"""
        row = {"bank_card_no": "6217001234567890"}
        masked_row, masked_cols = masker.mask_row(row, ["bank_card_no"])
        assert "bank_card_no" in masked_cols


class TestBuiltinEmailMasking:
    """内置邮箱脱敏测试。"""

    @pytest.fixture()
    def masker(self) -> DataMasker:
        """创建默认脱敏器。"""
        return DataMasker()

    def test_email_masking(self, masker: DataMasker) -> None:
        """邮箱保留前两位和域名。"""
        row = {"user_email": "zhangsan@example.com"}
        masked_row, masked_cols = masker.mask_row(row, ["user_email"])
        assert masked_row["user_email"] == "zh***@example.com"
        assert "user_email" in masked_cols

    def test_email_with_work_prefix(self, masker: DataMasker) -> None:
        """work_email 列名可匹配。"""
        row = {"work_email": "lisi@company.cn"}
        masked_row, masked_cols = masker.mask_row(row, ["work_email"])
        assert "work_email" in masked_cols
        assert "***@" in masked_row["work_email"]


class TestMaskResult:
    """mask_result 结果集脱敏测试。"""

    @pytest.fixture()
    def masker(self) -> DataMasker:
        """创建默认脱敏器。"""
        return DataMasker()

    def test_multiple_rows(self, masker: DataMasker) -> None:
        """多行数据脱敏。"""
        rows = [
            {"name": "张三", "phone": "13812345678"},
            {"name": "李四", "phone": "13987654321"},
            {"name": "王五", "phone": "15011112222"},
        ]
        masked_rows, masked_cols = masker.mask_result(rows, ["phone"])
        assert len(masked_rows) == 3
        assert "phone" in masked_cols
        # 每行手机号都被脱敏
        for row in masked_rows:
            assert "****" in row["phone"]
            assert len(row["phone"]) == 11

    def test_empty_rows(self, masker: DataMasker) -> None:
        """空结果集。"""
        masked_rows, masked_cols = masker.mask_result([], ["phone"])
        assert masked_rows == []
        assert masked_cols == []

    def test_dedup_masked_columns(self, masker: DataMasker) -> None:
        """被脱敏的列名去重。"""
        rows = [
            {"phone": "13812345678", "work_phone": "13987654321"},
        ]
        masked_rows, masked_cols = masker.mask_result(rows, ["phone", "work_phone"])
        assert len(masked_cols) == 2


class TestMaskTypeFull:
    """full 完全替换脱敏测试。"""

    def test_full_mask(self) -> None:
        """完全替换为固定字符。"""
        masker = DataMasker(custom_rules=[
            MaskRule(column_name="secret", mask_type="full", replacement="***")
        ])
        row = {"secret": "my-password-123"}
        masked_row, masked_cols = masker.mask_row(row, ["secret"])
        assert masked_row["secret"] == "***"
        assert "secret" in masked_cols


class TestMaskTypeHash:
    """hash MD5 哈希脱敏测试。"""

    def test_hash_mask(self) -> None:
        """MD5 哈希脱敏。"""
        import hashlib

        masker = DataMasker(custom_rules=[
            MaskRule(column_name="password", mask_type="hash")
        ])
        row = {"password": "abc123"}
        masked_row, masked_cols = masker.mask_row(row, ["password"])
        expected = hashlib.md5("abc123".encode("utf-8")).hexdigest()
        assert masked_row["password"] == expected
        assert len(masked_row["password"]) == 32
        assert "password" in masked_cols


class TestMaskTypeReplace:
    """replace 固定替换脱敏测试。"""

    def test_replace_mask(self) -> None:
        """固定字符串替换。"""
        masker = DataMasker(custom_rules=[
            MaskRule(column_name="api_key", mask_type="replace", replacement="[REDACTED]")
        ])
        row = {"api_key": "sk-12345-abcdef"}
        masked_row, masked_cols = masker.mask_row(row, ["api_key"])
        assert masked_row["api_key"] == "[REDACTED]"
        assert "api_key" in masked_cols


class TestMaskTypePartialNoPattern:
    """partial 脱敏无正则模式测试。"""

    def test_partial_without_pattern(self) -> None:
        """partial 类型没有正则模式时，保留首尾字符。"""
        masker = DataMasker(custom_rules=[
            MaskRule(column_name="address", mask_type="partial", replacement="***")
        ])
        row = {"address": "北京市朝阳区"}
        masked_row, masked_cols = masker.mask_row(row, ["address"])
        assert masked_row["address"] == "北***区"
        assert "address" in masked_cols

    def test_partial_short_value(self) -> None:
        """partial 类型短字符串（<=2字符）直接替换。"""
        masker = DataMasker(custom_rules=[
            MaskRule(column_name="code", mask_type="partial", replacement="***")
        ])
        row = {"code": "ab"}
        masked_row, masked_cols = masker.mask_row(row, ["code"])
        assert masked_row["code"] == "***"
        assert "code" in masked_cols


class TestMaskingEdgeCases:
    """脱敏边界情况测试。"""

    @pytest.fixture()
    def masker(self) -> DataMasker:
        """创建默认脱敏器。"""
        return DataMasker()

    def test_none_value(self, masker: DataMasker) -> None:
        """None 值跳过脱敏。"""
        row = {"phone": None}
        masked_row, masked_cols = masker.mask_row(row, ["phone"])
        assert masked_row["phone"] is None
        assert masked_cols == []

    def test_non_string_value(self, masker: DataMasker) -> None:
        """非字符串值跳过脱敏。"""
        row = {"phone": 12345}
        masked_row, masked_cols = masker.mask_row(row, ["phone"])
        assert masked_row["phone"] == 12345
        assert masked_cols == []

    def test_column_not_in_row(self, masker: DataMasker) -> None:
        """列不存在于行中时跳过。"""
        row = {"name": "张三"}
        masked_row, masked_cols = masker.mask_row(row, ["phone"])
        assert masked_row == {"name": "张三"}
        assert masked_cols == []

    def test_no_matching_rule(self, masker: DataMasker) -> None:
        """没有匹配的脱敏规则时原样返回。"""
        row = {"name": "张三"}
        masked_row, masked_cols = masker.mask_row(row, ["name"])
        assert masked_row["name"] == "张三"
        assert masked_cols == []

    def test_column_not_in_columns_list(self, masker: DataMasker) -> None:
        """列不在检查列表中时不脱敏。"""
        row = {"phone": "13812345678", "name": "张三"}
        masked_row, masked_cols = masker.mask_row(row, ["name"])
        assert masked_row["phone"] == "13812345678"
        assert masked_cols == []


class TestCustomRules:
    """自定义脱敏规则测试。"""

    def test_add_custom_rule(self) -> None:
        """添加自定义规则。"""
        masker = DataMasker()
        masker.add_rule(MaskRule(
            column_name="*salary*",
            mask_type="replace",
            replacement="[保密]",
        ))
        row = {"monthly_salary": "15000"}
        masked_row, masked_cols = masker.mask_row(row, ["monthly_salary"])
        assert masked_row["monthly_salary"] == "[保密]"
        assert "monthly_salary" in masked_cols

    def test_custom_rule_via_constructor(self) -> None:
        """通过构造函数传入自定义规则。"""
        masker = DataMasker(custom_rules=[
            MaskRule(column_name="*ssn*", mask_type="partial", pattern=r"(\d{3})\d{2}(\d{4})", replacement=r"\1**\2")
        ])
        row = {"user_ssn": "123456789"}
        masked_row, masked_cols = masker.mask_row(row, ["user_ssn"])
        assert masked_row["user_ssn"] == "123**6789"
        assert "user_ssn" in masked_cols

    def test_wildcard_matching(self) -> None:
        """通配符匹配多个列名。"""
        masker = DataMasker(custom_rules=[
            MaskRule(column_name="*secret*", mask_type="full", replacement="[HIDDEN]")
        ])
        row = {
            "api_secret": "abc",
            "db_secret_key": "def",
            "public_info": "ghi",
        }
        masked_row, masked_cols = masker.mask_row(
            row, ["api_secret", "db_secret_key", "public_info"]
        )
        assert masked_row["api_secret"] == "[HIDDEN]"
        assert masked_row["db_secret_key"] == "[HIDDEN]"
        assert masked_row["public_info"] == "ghi"  # 不匹配 *secret*
        assert len(masked_cols) == 2
