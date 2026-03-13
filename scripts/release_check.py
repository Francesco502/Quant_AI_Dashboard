#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
发布就绪检查脚本
使用 Playwright 检查项目的功能Complete度和发布准备状态
"""

import sys
import os
from pathlib import Path
from playwright.sync_api import sync_playwright


def check_Homepage(page):
    """检查主页功能"""
    print("检查主页...")
    try:
        page.goto("http://localhost:8686/", wait_until="networkidle")

        # 检查关键元素
        checks = {
            "标题": page.get_by_role("heading", name="市场概览").is_visible(),
            "资产卡片": page.get_by_text("总资产").is_visible(),
            "盈亏卡片": page.get_by_text("当日盈亏").is_visible(),
            "图表容器": page.locator(".recharts-responsive-container").count() > 0,
        }

        passed = sum(checks.values())
        total = len(checks)
        print(f"  主页检查: {passed}/{total} 通过")
        return checks
    except Exception as e:
        print(f"  主页检查失败: {e}")
        return None


def check_market_page(page):
    """检查市场页面"""
    print("检查市场页面...")
    try:
        page.goto("http://localhost:8686/market", wait_until="networkidle")

        checks = {
            "标题": page.get_by_role("heading", name="AI 市场分析").is_visible(),
            "AI预测Tab": page.get_by_role("tab", name="AI 预测").is_visible(),
            "技术指标Tab": page.get_by_role("tab", name="技术指标").is_visible(),
            "预测输入": page.get_by_text("标的 (Asset)").is_visible(),
        }

        passed = sum(checks.values())
        total = len(checks)
        print(f"  市场页面: {passed}/{total} 通过")
        return checks
    except Exception as e:
        print(f"  市场页面检查失败: {e}")
        return None


def check_backtest_page(page):
    """检查回测页面"""
    print("检查回测页面...")
    try:
        page.goto("http://localhost:8686/backtest", wait_until="networkidle")

        checks = {
            "标题": page.get_by_role("heading", name="历史回测").is_visible(),
            "策略选择": page.get_by_text("选择策略").is_visible(),
            "开始回测按钮": page.get_by_text("开始回测").is_visible(),
            "组合回测Tab": page.get_by_text("组合回测").is_visible(),
        }

        passed = sum(checks.values())
        total = len(checks)
        print(f"  回测页面: {passed}/{total} 通过")
        return checks
    except Exception as e:
        print(f"  回测页面检查失败: {e}")
        return None


def check_strategies_page(page):
    """检查策略页面"""
    print("检查策略页面...")
    try:
        page.goto("http://localhost:8686/strategies", wait_until="networkidle")

        checks = {
            "标题": page.get_by_role("heading", name="量化战法").is_visible(),
            "运行策略Tab": page.get_by_role("tab", name="运行策略").is_visible(),
            "选股配置": page.get_by_text("配置并运行您的选股策略").is_visible(),
        }

        passed = sum(checks.values())
        total = len(checks)
        print(f"  策略页面: {passed}/{total} 通过")
        return checks
    except Exception as e:
        print(f"  策略页面检查失败: {e}")
        return None


def check_login_page(page):
    """检查登录页面"""
    print("检查登录页面...")
    try:
        page.goto("http://localhost:8686/login", wait_until="networkidle")

        checks = {
            "标题": page.get_by_role("heading", name="用户登录").is_visible(),
            "用户名输入": page.get_by_placeholder("用户名").is_visible(),
            "密码输入": page.get_by_label("密码", exact=True).is_visible(),
            "登录按钮": page.get_by_role("button", name="登录").is_visible(),
            "注册链接": page.get_by_text("没有账号？").is_visible(),
        }

        passed = sum(checks.values())
        total = len(checks)
        print(f"  登录页面: {passed}/{total} 通过")
        return checks
    except Exception as e:
        print(f"  登录页面检查失败: {e}")
        return None


def check_api_health(page):
    """检查API健康状态"""
    print("检查API健康...")
    try:
        response = page.request.get("http://localhost:8685/api/health")
        if response.ok:
            data = response.json()
            print(f"  API健康: 通过 (status={data.get('status', 'unknown')})")
            return {"api_healthy": True, "status": data.get("status")}
        else:
            print(f"  API健康: 失败 (status={response.status})")
            return {"api_healthy": False, "status": response.status}
    except Exception as e:
        print(f"  API健康检查失败: {e}")
        return {"api_healthy": False, "error": str(e)}


def generate_report(results):
    """生成检查报告"""
    print("\n" + "=" * 60)
    print("发布就绪检查报告")
    print("=" * 60)

    total_checks = 0
    total_passed = 0
    critical_failures = []
    warnings = []

    for category, data in results.items():
        if data is None:
            warnings.append(f"{category}: 无法连接或超时")
            continue

        if isinstance(data, dict) and "api_healthy" in data:
            # Special handling for API health
            total_checks += 1
            if data.get("api_healthy"):
                total_passed += 1
            else:
                critical_failures.append(f"{category}: {data.get('error', 'API不可用')}")
        else:
            # Normal category with checks dict
            passed = sum(data.values()) if data else 0
            total = len(data) if data else 0
            total_checks += total
            total_passed += passed

            if passed < total:
                for check, status in (data or {}).items():
                    if not status:
                        warnings.append(f"{category} - {check}:未通过")

    # Calculate score
    if total_checks > 0:
        score = (total_passed / total_checks) * 100
    else:
        score = 0

    print(f"\n总体评分: {score:.1f}%")
    print(f"通过: {total_passed}/{total_checks}")

    if critical_failures:
        print("\n严重问题（阻塞发布）:")
        for issue in critical_failures:
            print(f"  ❌ {issue}")

    if warnings:
        print("\n警告（建议修复）:")
        for issue in warnings:
            print(f"  ⚠️  {issue}")

    # Release readiness assessment
    print("\n" + "-" * 40)
    print("发布就绪评估:")

    if score >= 90 and not critical_failures:
        print("  ✅ 完全就绪 - 可以发布")
        print("  说明: 所有核心功能正常，可以部署到生产环境")
    elif score >= 70 and len(critical_failures) == 0:
        print("  ⚠️  基本就绪 - 建议预发布")
        print("  说明: 核心功能正常，但有一些小问题建议修复")
    elif score >= 50:
        print("  ⚠️  部分就绪 - 需要修复")
        print("  说明: 有几个关键功能需要修复后才能发布")
    else:
        print("  ❌ 未就绪 - 需要大量修复")
        print("  说明: 项目还需要较多工作才能发布")

    print("\n" + "=" * 60)

    return {
        "score": score,
        "passed": total_passed,
        "total": total_checks,
        "critical_failures": critical_failures,
        "warnings": warnings,
        "ready": score >= 90 and not critical_failures
    }


def main():
    """主函数"""
    print("开始发布就绪检查...")
    print("确保前端服务在 http://localhost:8686 运行")
    print("按 Ctrl+C 中断")

    results = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # 设置超时
        page.set_default_timeout(30000)

        try:
            # 按优先级检查
            results["api_health"] = check_api_health(page)

            results["homepage"] = check_Homepage(page)
            results["login_page"] = check_login_page(page)
            results["market_page"] = check_market_page(page)
            results["backtest_page"] = check_backtest_page(page)
            results["strategies_page"] = check_strategies_page(page)

        except Exception as e:
            print(f"\n检查过程中出错: {e}")
            print("可能的原因:")
            print("  1. 前端服务未在 http://localhost:8686 运行")
            print("  2. 网络连接问题")
            print("  3. 服务响应超时")

            # 尝试检查端口
            import socket
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                if s.connect_ex(('localhost', 8686)) != 0:
                    print("\n  端口 8686 未打开 - 前端服务未运行")
                s.close()

            # 尝试检查API端口
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                if s.connect_ex(('localhost', 8685)) != 0:
                    print("  端口 8685 未打开 - 后端API未运行")
                s.close()

        finally:
            browser.close()

    # 生成报告
    report = generate_report(results)

    # 保存报告
    report_path = Path("release_check_report.txt")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("发布就绪检查报告\n")
        f.write("=" * 60 + "\n\n")
        f.write(f"总体评分: {report['score']:.1f}%\n")
        f.write(f"通过: {report['passed']}/{report['total']}\n\n")

        if report['critical_failures']:
            f.write("严重问题:\n")
            for issue in report['critical_failures']:
                f.write(f"  - {issue}\n")

        if report['warnings']:
            f.write("\n警告:\n")
            for issue in report['warnings']:
                f.write(f"  - {issue}\n")

        f.write(f"\n就绪状态: {'可以发布' if report['ready'] else '需要修复'}\n")

    print(f"\n报告已保存到: {report_path}")

    return 0 if report['ready'] else 1


if __name__ == "__main__":
    sys.exit(main())
