"""HMAC-SHA256 签名与验签。

仅使用 Python 标准库（hmac + hashlib），不引入额外依赖。
签名 payload 为 JSON 字符串（按 key 排序），确保确定性输出。
"""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any


def _canonical_payload(data: dict[str, Any]) -> str:
    """将数据字典转为排序后的 JSON 字符串，确保签名确定性。"""
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sign_license(data: dict[str, Any], secret: str) -> str:
    """对授权数据生成 HMAC-SHA256 签名。

    Args:
        data: 待签名的数据字典（不含 signature 字段）。
        secret: 签名密钥。

    Returns:
        十六进制编码的签名字符串。
    """
    payload = _canonical_payload(data)
    return hmac.new(
        secret.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def verify_signature(data: dict[str, Any], signature: str, secret: str) -> bool:
    """验签授权数据的 HMAC-SHA256 签名。

    使用 hmac.compare_digest 进行常量时间比较，防止时序攻击。

    Args:
        data: 授权数据字典（不含 signature 字段）。
        signature: 待验证的十六进制签名。
        secret: 签名密钥。

    Returns:
        签名是否有效。
    """
    expected = sign_license(data, secret)
    return hmac.compare_digest(expected, signature)
