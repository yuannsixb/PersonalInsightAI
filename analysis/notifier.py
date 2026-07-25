# notifier.py — 通知模块
#
# 支持：
#   1. 邮件通知（需要配置 SMTP）
#   2. 控制台输出（默认）
#
# 不配置邮箱的话，通知内容会打印到控制台

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from database.db import get_config


def send_notification(subject, content, notify_type='console'):
    """
    发送通知
    notify_type: 'console' | 'email'
    """
    if notify_type == 'email':
        return _send_email(subject, content)
    else:
        return _send_console(subject, content)


def _send_console(subject, content):
    print(f'[通知] {subject}')
    print(content[:200] + ('...' if len(content) > 200 else ''))
    return True


def _send_email(subject, content):
    """发送邮件通知"""
    email_to = get_config('通知邮箱')
    if not email_to:
        print('未配置通知邮箱，跳过邮件发送')
        return False

    email_from = get_config('发件邮箱')
    smtp_server = get_config('SMTP服务器')
    smtp_port = get_config('SMTP端口')
    smtp_pwd = get_config('SMTP密码')

    if not all([email_from, smtp_server, smtp_port, smtp_pwd]):
        print('邮箱配置不完整，跳过邮件发送')
        return False

    try:
        msg = MIMEMultipart()
        msg['From'] = email_from
        msg['To'] = email_to
        msg['Subject'] = subject
        msg.attach(MIMEText(content, 'plain', 'utf-8'))

        server = smtplib.SMTP(smtp_server, int(smtp_port))
        server.starttls()
        server.login(email_from, smtp_pwd)
        server.send_message(msg)
        server.quit()
        print(f'邮件已发送到 {email_to}')
        return True
    except Exception as e:
        print(f'邮件发送失败: {e}')
        return False


def notify_insight_ready(report_text):
    """通知用户新报告已生成"""
    subject = 'PersonalInsightAI · 新洞察报告已生成'

    # 取报告前 5 行做摘要
    lines = report_text.strip().split('\n')
    summary = '\n'.join(lines[:8])

    content = f'您的个人洞察报告已生成：\n\n{summary}\n\n详情请查看 Dashboard。'

    send_notification(subject, content)


if __name__ == '__main__':
    test_report = 'PersonalInsightAI 洞察报告\n生成时间: 2026-07-18 14:00\n数据量: 100 条\n\n【用户画像】\n类型: 效率优化型'
    notify_insight_ready(test_report)
