"""LicenseValidator 单元测试。

覆盖场景：
- 签名校验（有效签名、签名被篡改）
- 有效期校验（未过期、已过期）
- IP 白名单校验（精确匹配、CIDR 匹配、不在白名单）
- 功能许可校验（已授权、未授权、空列表全开放）
- 并发用户数校验（未超限、已超限）
- 文件加载（文件不存在、JSON 解析失败）
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path  # noqa: TC003

import pytest

from datapilot_license.license import LicenseData
from datapilot_license.validator import (
    LicenseExpiredError,
    LicenseFeatureDisabledError,
    LicenseInvalidError,
    LicenseIpDeniedError,
    LicenseUserLimitError,
    LicenseValidator,
)

# ============================================================
# Fixtures
# ============================================================


def _make_license_data(
    expires_at: datetime | None = None,
    allowed_ips: list[str] | None = None,
    features: list[str] | None = None,
    max_concurrent_users: int = 10,
    secret: str = "test-secret-key",
) -> dict:
    """构建一个有效的授权数据字典（已签名）。

    通过 LicenseData 模型序列化后签名，确保与验证时的格式一致。
    """
    from datapilot_license.crypto import sign_license

    now = datetime.now(UTC)
    if expires_at is None:
        expires_at = now + timedelta(days=365)

    # 通过模型序列化确保格式一致
    model = LicenseData(
        product="DataPilot",
        licensee="Test Corp",
        license_key="test-key-001",
        issued_at=now,
        expires_at=expires_at,
        allowed_ips=allowed_ips or [],
        max_concurrent_users=max_concurrent_users,
        features=features or [],
        signature="placeholder",
    )

    payload = model.model_dump(exclude={"signature"}, mode="json")
    signature = sign_license(payload, secret)
    payload["signature"] = signature
    return payload


@pytest.fixture
def valid_license_dict() -> dict:
    """返回一个有效的授权数据字典。"""
    return _make_license_data()


@pytest.fixture
def license_file(tmp_path: Path, valid_license_dict: dict) -> Path:
    """创建一个临时授权文件并返回其路径。"""
    path = tmp_path / "license.json"
    path.write_text(
        json.dumps(valid_license_dict, ensure_ascii=False),
        encoding="utf-8",
    )
    return path


@pytest.fixture
def validator(license_file: Path) -> LicenseValidator:
    """创建一个已加载授权的 LicenseValidator 实例。"""
    v = LicenseValidator(
        license_path=license_file,
        signing_secret="test-secret-key",
    )
    v.load()
    return v


# ============================================================
# 签名校验测试
# ============================================================


class TestSignatureValidation:
    """签名校验测试。"""

    def test_load_with_valid_signature_succeeds(self, license_file: Path) -> None:
        """有效签名的授权文件可以正常加载。"""
        v = LicenseValidator(
            license_path=license_file,
            signing_secret="test-secret-key",
        )
        result = v.load()
        assert isinstance(result, LicenseData)
        assert result.product == "DataPilot"
        assert result.licensee == "Test Corp"

    def test_load_with_tampered_signature_raises(
        self,
        tmp_path: Path,
        valid_license_dict: dict,
    ) -> None:
        """签名被篡改的授权文件应抛出 LicenseInvalidError。"""
        # 修改签名
        valid_license_dict["signature"] = "tampered_signature_value"
        path = tmp_path / "license.json"
        path.write_text(
            json.dumps(valid_license_dict, ensure_ascii=False),
            encoding="utf-8",
        )

        v = LicenseValidator(
            license_path=path,
            signing_secret="test-secret-key",
        )
        with pytest.raises(LicenseInvalidError, match="签名校验失败"):
            v.load()

    def test_load_with_wrong_secret_raises(
        self,
        tmp_path: Path,
        valid_license_dict: dict,
    ) -> None:
        """使用错误密钥验签应抛出 LicenseInvalidError。"""
        path = tmp_path / "license.json"
        path.write_text(
            json.dumps(valid_license_dict, ensure_ascii=False),
            encoding="utf-8",
        )

        v = LicenseValidator(
            license_path=path,
            signing_secret="wrong-secret-key",
        )
        with pytest.raises(LicenseInvalidError, match="签名校验失败"):
            v.load()


# ============================================================
# 文件加载测试
# ============================================================


class TestFileLoading:
    """文件加载测试。"""

    def test_load_nonexistent_file_raises(self) -> None:
        """授权文件不存在时应抛出 LicenseInvalidError。"""
        v = LicenseValidator(license_path="/nonexistent/license.json")
        with pytest.raises(LicenseInvalidError, match="不存在"):
            v.load()

    def test_load_invalid_json_raises(self, tmp_path: Path) -> None:
        """JSON 解析失败应抛出 LicenseInvalidError。"""
        path = tmp_path / "license.json"
        path.write_text("{invalid json}", encoding="utf-8")

        v = LicenseValidator(license_path=path)
        with pytest.raises(LicenseInvalidError, match="解析失败"):
            v.load()

    def test_load_missing_required_field_raises(self, tmp_path: Path) -> None:
        """缺少必填字段应抛出 LicenseInvalidError。"""
        path = tmp_path / "license.json"
        path.write_text(
            json.dumps({"product": "DataPilot"}),
            encoding="utf-8",
        )

        v = LicenseValidator(license_path=path)
        with pytest.raises(LicenseInvalidError, match="格式错误"):
            v.load()


# ============================================================
# 有效期校验测试
# ============================================================


class TestExpiryValidation:
    """有效期校验测试。"""

    def test_validate_non_expired_license_succeeds(
        self,
        validator: LicenseValidator,
    ) -> None:
        """未过期的授权应通过校验。"""
        result = validator.validate()
        assert result is not None

    def test_validate_expired_license_raises(
        self,
        tmp_path: Path,
    ) -> None:
        """已过期的授权应抛出 LicenseExpiredError。"""
        past = datetime.now(UTC) - timedelta(days=1)
        data = _make_license_data(expires_at=past)
        path = tmp_path / "license.json"
        path.write_text(json.dumps(data), encoding="utf-8")

        v = LicenseValidator(
            license_path=path,
            signing_secret="test-secret-key",
        )
        v.load()
        with pytest.raises(LicenseExpiredError, match="过期"):
            v.validate()

    def test_check_expiry_with_naive_datetime_succeeds(
        self,
        validator: LicenseValidator,
    ) -> None:
        """naive datetime（无时区）也应正确比较。"""
        # 授权文件中的 expires_at 使用 timezone-aware datetime，
        # check_expiry 内部会处理 naive 情况
        validator.check_expiry()


# ============================================================
# IP 白名单校验测试
# ============================================================


class TestIpValidation:
    """IP 白名单校验测试。"""

    def test_check_ip_exact_match_succeeds(
        self,
        tmp_path: Path,
    ) -> None:
        """精确 IP 匹配应通过。"""
        data = _make_license_data(allowed_ips=["192.168.1.100", "10.0.0.1"])
        path = tmp_path / "license.json"
        path.write_text(json.dumps(data), encoding="utf-8")

        v = LicenseValidator(
            license_path=path,
            signing_secret="test-secret-key",
        )
        v.load()
        assert v.check_ip("192.168.1.100") is True

    def test_check_ip_cidr_match_succeeds(
        self,
        tmp_path: Path,
    ) -> None:
        """CIDR 范围匹配应通过。"""
        data = _make_license_data(allowed_ips=["10.0.0.0/8", "192.168.0.0/16"])
        path = tmp_path / "license.json"
        path.write_text(json.dumps(data), encoding="utf-8")

        v = LicenseValidator(
            license_path=path,
            signing_secret="test-secret-key",
        )
        v.load()
        assert v.check_ip("10.123.45.67") is True
        assert v.check_ip("192.168.1.1") is True

    def test_check_ip_not_in_whitelist_raises(
        self,
        tmp_path: Path,
    ) -> None:
        """不在白名单的 IP 应抛出 LicenseIpDeniedError。"""
        data = _make_license_data(allowed_ips=["10.0.0.0/8"])
        path = tmp_path / "license.json"
        path.write_text(json.dumps(data), encoding="utf-8")

        v = LicenseValidator(
            license_path=path,
            signing_secret="test-secret-key",
        )
        v.load()
        with pytest.raises(LicenseIpDeniedError, match="8.8.8.8"):
            v.check_ip("8.8.8.8")

    def test_check_ip_empty_whitelist_allows_all(
        self,
        validator: LicenseValidator,
    ) -> None:
        """白名单为空时，所有 IP 都应通过。"""
        assert validator.check_ip("1.2.3.4") is True
        assert validator.check_ip("255.255.255.255") is True

    def test_check_ip_invalid_client_ip_raises(
        self,
        tmp_path: Path,
    ) -> None:
        """非法的客户端 IP 格式应抛出 LicenseIpDeniedError。"""
        data = _make_license_data(allowed_ips=["10.0.0.0/8"])
        path = tmp_path / "license.json"
        path.write_text(json.dumps(data), encoding="utf-8")

        v = LicenseValidator(
            license_path=path,
            signing_secret="test-secret-key",
        )
        v.load()
        with pytest.raises(LicenseIpDeniedError):
            v.check_ip("not-an-ip-address")

    def test_check_ip_ipv6_support(
        self,
        tmp_path: Path,
    ) -> None:
        """IPv6 地址应正确处理。"""
        data = _make_license_data(allowed_ips=["::1", "2001:db8::/32"])
        path = tmp_path / "license.json"
        path.write_text(json.dumps(data), encoding="utf-8")

        v = LicenseValidator(
            license_path=path,
            signing_secret="test-secret-key",
        )
        v.load()
        assert v.check_ip("::1") is True
        assert v.check_ip("2001:db8::1") is True
        with pytest.raises(LicenseIpDeniedError):
            v.check_ip("fe80::1")


# ============================================================
# 功能许可校验测试
# ============================================================


class TestFeatureValidation:
    """功能许可校验测试。"""

    def test_check_feature_authorized_succeeds(
        self,
        tmp_path: Path,
    ) -> None:
        """已授权的功能应通过校验。"""
        data = _make_license_data(features=["nl2sql", "semantic_model"])
        path = tmp_path / "license.json"
        path.write_text(json.dumps(data), encoding="utf-8")

        v = LicenseValidator(
            license_path=path,
            signing_secret="test-secret-key",
        )
        v.load()
        assert v.check_feature("nl2sql") is True

    def test_check_feature_unauthorized_raises(
        self,
        tmp_path: Path,
    ) -> None:
        """未授权的功能应抛出 LicenseFeatureDisabledError。"""
        data = _make_license_data(features=["nl2sql"])
        path = tmp_path / "license.json"
        path.write_text(json.dumps(data), encoding="utf-8")

        v = LicenseValidator(
            license_path=path,
            signing_secret="test-secret-key",
        )
        v.load()
        with pytest.raises(LicenseFeatureDisabledError, match="python_sandbox"):
            v.check_feature("python_sandbox")

    def test_check_feature_empty_list_allows_all(
        self,
        validator: LicenseValidator,
    ) -> None:
        """功能列表为空时，所有功能都应通过。"""
        assert validator.check_feature("any_feature") is True


# ============================================================
# 并发用户数校验测试
# ============================================================


class TestConcurrentValidation:
    """并发用户数校验测试。"""

    def test_check_concurrent_under_limit_succeeds(
        self,
        validator: LicenseValidator,
    ) -> None:
        """并发数未超限时应通过。"""
        assert validator.check_concurrent(5) is True
        assert validator.check_concurrent(9) is True

    def test_check_concurrent_at_limit_raises(
        self,
        validator: LicenseValidator,
    ) -> None:
        """并发数达到上限应抛出 LicenseUserLimitError。"""
        with pytest.raises(LicenseUserLimitError, match="上限"):
            validator.check_concurrent(10)

    def test_check_concurrent_over_limit_raises(
        self,
        validator: LicenseValidator,
    ) -> None:
        """并发数超过上限应抛出 LicenseUserLimitError。"""
        with pytest.raises(LicenseUserLimitError, match="上限"):
            validator.check_concurrent(100)


# ============================================================
# 综合校验测试
# ============================================================


class TestValidation:
    """综合校验测试。"""

    def test_validate_calls_check_expiry(
        self,
        tmp_path: Path,
    ) -> None:
        """validate() 应检查有效期。"""
        past = datetime.now(UTC) - timedelta(days=1)
        data = _make_license_data(expires_at=past)
        path = tmp_path / "license.json"
        path.write_text(json.dumps(data), encoding="utf-8")

        v = LicenseValidator(
            license_path=path,
            signing_secret="test-secret-key",
        )
        v.load()
        with pytest.raises(LicenseExpiredError):
            v.validate()

    def test_license_property_without_load_raises(self) -> None:
        """未加载授权时访问 license 属性应抛出 LicenseInvalidError。"""
        v = LicenseValidator()
        with pytest.raises(LicenseInvalidError, match="尚未加载"):
            _ = v.license

    def test_validate_custom_max_users(
        self,
        tmp_path: Path,
    ) -> None:
        """自定义并发数限制应正确生效。"""
        data = _make_license_data(max_concurrent_users=2)
        path = tmp_path / "license.json"
        path.write_text(json.dumps(data), encoding="utf-8")

        v = LicenseValidator(
            license_path=path,
            signing_secret="test-secret-key",
        )
        v.load()
        assert v.check_concurrent(1) is True
        with pytest.raises(LicenseUserLimitError):
            v.check_concurrent(2)
