"""CLI 授权生成工具。

用法示例：
    python -m datapilot_license.cli generate \
        --licensee "Acme Corp" \
        --ips "10.0.0.0/8,192.168.1.0/24" \
        --days 365 \
        --features "nl2sql,semantic_model" \
        --key "my-signing-key"
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from .crypto import sign_license
from .license import LicenseData


def _build_license_data(
    licensee: str,
    ips: list[str],
    days: int,
    features: list[str],
    signing_key: str,
    product: str = "DataPilot",
) -> dict:
    """构建授权数据字典。

    先构造 LicenseData 模型（临时签名），通过 model_dump(mode="json") 序列化
    后签名，确保生成与验证时的序列化格式完全一致。
    """
    now = datetime.now(UTC)
    expires = now + timedelta(days=days)

    # 先创建模型（用占位签名）
    model = LicenseData(
        product=product,
        licensee=licensee,
        license_key=uuid.uuid4().hex,
        issued_at=now,
        expires_at=expires,
        allowed_ips=ips,
        max_concurrent_users=100,
        features=features,
        signature="placeholder",
    )

    # 用 model_dump 得到与验证时一致的序列化格式
    payload = model.model_dump(exclude={"signature"}, mode="json")
    signature = sign_license(payload, signing_key)
    payload["signature"] = signature

    return payload


def _cmd_generate(args: argparse.Namespace) -> None:
    """执行 generate 子命令。"""
    ips = [ip.strip() for ip in args.ips.split(",") if ip.strip()] if args.ips else []
    features = [f.strip() for f in args.features.split(",") if f.strip()] if args.features else []

    license_data = _build_license_data(
        licensee=args.licensee,
        ips=ips,
        days=args.days,
        features=features,
        signing_key=args.key,
        product=args.product,
    )

    output_path = Path(args.output)
    output_path.write_text(
        json.dumps(license_data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"授权文件已生成: {output_path}")
    print(f"  被授权方: {args.licensee}")
    print(f"  有效期: {args.days} 天")
    print(f"  功能列表: {', '.join(features) if features else '(全部)'}")
    print(f"  IP 白名单: {', '.join(ips) if ips else '(不限制)'}")


def _build_parser() -> argparse.ArgumentParser:
    """构建 CLI 参数解析器。"""
    parser = argparse.ArgumentParser(
        prog="datapilot_license",
        description="DataPilot 产品授权管理工具",
    )
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # generate 子命令
    gen_parser = subparsers.add_parser("generate", help="生成授权文件")
    gen_parser.add_argument(
        "--licensee",
        required=True,
        help="被授权方名称",
    )
    gen_parser.add_argument(
        "--ips",
        default="",
        help="IP 白名单（逗号分隔，支持 CIDR，如 10.0.0.0/8,192.168.1.0/24）",
    )
    gen_parser.add_argument(
        "--days",
        type=int,
        default=365,
        help="授权有效天数，默认 365",
    )
    gen_parser.add_argument(
        "--features",
        default="",
        help="已授权功能列表（逗号分隔，如 nl2sql,semantic_model）",
    )
    gen_parser.add_argument(
        "--key",
        required=True,
        help="签名密钥",
    )
    gen_parser.add_argument(
        "--product",
        default="DataPilot",
        help="产品名称，默认 DataPilot",
    )
    gen_parser.add_argument(
        "--output",
        default="license.json",
        help="输出文件路径，默认 license.json",
    )

    return parser


def main(argv: list[str] | None = None) -> None:
    """CLI 入口函数。"""
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "generate":
        _cmd_generate(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
