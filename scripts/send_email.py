#!/usr/bin/env python3
"""
📧 邮件发送模块 — 用于发送每日策略报告到指定邮箱

使用前配置：
  1. 设置环境变量 EMAIL_CONFIG 文件路径（默认 ~/.hermes/email_config.yaml）
  2. 在该文件中填写：
     sender: "863221102@qq.com"
     password: "你的QQ邮箱授权码"  ← 不是QQ密码！
     smtp_server: "smtp.qq.com"
     smtp_port: 587
"""

import os
import sys
import yaml
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path


DEFAULT_CONFIG_PATH = Path.home() / ".hermes" / "email_config.yaml"


def load_config(config_path: str = None) -> dict:
    """加载邮箱配置"""
    path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    if not path.exists():
        print(f"⚠️  未找到邮箱配置文件: {path}")
        print(f"   请创建文件并填写: ")
        print(f"     echo \"sender: '863221102@qq.com'\" > {path}")
        print(f"     echo \"password: '你的授权码'\" >> {path}")
        print(f"     echo \"smtp_server: 'smtp.qq.com'\" >> {path}")
        print(f"     echo \"smtp_port: 587\" >> {path}")
        sys.exit(1)

    with open(path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    required = ["sender", "password", "smtp_server", "smtp_port"]
    missing = [k for k in required if not config.get(k)]
    if missing:
        print(f"❌ 邮箱配置缺少字段: {', '.join(missing)}")
        print(f"   请编辑 {path}")
        sys.exit(1)

    return config


def send_email(
    subject: str,
    body: str,
    to: str,
    config_path: str = None,
) -> bool:
    """
    发送邮件

    参数:
        subject: 邮件主题
        body: 邮件正文（纯文本）
        to: 收件人邮箱
        config_path: 配置文件路径（可选）
    返回:
        True=成功, False=失败
    """
    config = load_config(config_path)

    msg = MIMEMultipart("alternative")
    msg["From"] = config["sender"]
    msg["To"] = to
    msg["Subject"] = subject

    # 纯文本正文
    msg.attach(MIMEText(body, "plain", "utf-8"))

    try:
        with smtplib.SMTP(config["smtp_server"], config["smtp_port"], timeout=30) as server:
            server.starttls()
            server.login(config["sender"], config["password"])
            server.sendmail(config["sender"], [to], msg.as_string())
        print(f"✅ 邮件已发送至 {to}")
        return True
    except smtplib.SMTPAuthenticationError:
        print(f"❌ SMTP 认证失败，请检查授权码是否正确")
        print(f"   编辑 {config_path or DEFAULT_CONFIG_PATH}")
        print(f"   QQ邮箱授权码获取: 设置 → 账户 → POP3/IMAP/SMTP → 生成授权码")
        return False
    except smtplib.SMTPException as e:
        print(f"❌ SMTP 错误: {e}")
        return False
    except Exception as e:
        print(f"❌ 发送邮件失败: {e}")
        return False


def main():
    """命令行入口：从 stdin 读取邮件正文"""
    import argparse

    parser = argparse.ArgumentParser(description="发送每日策略邮件")
    parser.add_argument("--to", default="863221102@qq.com", help="收件人邮箱")
    parser.add_argument("--subject", default="📈 每日投资策略报告", help="邮件主题")
    parser.add_argument("--config", help="配置文件路径")
    args = parser.parse_args()

    # 从 stdin 读取正文
    body = sys.stdin.read().strip()
    if not body:
        print("❌ 请在 stdin 中提供邮件正文（管道传入）")
        sys.exit(1)

    # 生成带时间的主题
    from datetime import datetime
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    subject = f"{args.subject} ({now})"

    success = send_email(subject, body, args.to, args.config)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
