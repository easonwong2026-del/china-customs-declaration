#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
来源清单更新脚本
功能：
  - 更新来源查询时间
  - 检查来源是否失效
  - 记录资料版本
  - 标记历史版本
  - 生成变更日志
  - 提醒需要重新核实的动态资料
"""

import json
import os
import sys
from datetime import datetime
from urllib.request import urlopen, Request
from urllib.error import URLError


DEFAULT_MANIFEST = "source-manifest.json"


def load_manifest(path: str) -> dict:
    """加载来源清单"""
    if not os.path.exists(path):
        return {"metadata": {}, "sources": []}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_manifest(manifest: dict, path: str) -> None:
    """保存来源清单"""
    # 备份旧版本
    if os.path.exists(path):
        backup = path.replace(".json", f".{datetime.now().strftime('%Y%m%d')}.bak")
        with open(path, "r", encoding="utf-8") as src:
            with open(backup, "w", encoding="utf-8") as dst:
                dst.write(src.read())
        print(f"旧版本已备份到: {backup}")

    with open(path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"来源清单已保存: {path}")


def check_url(url: str) -> tuple[bool, str]:
    """检查URL是否可访问"""
    try:
        req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(req, timeout=10) as response:
            status = response.getcode()
            if 200 <= status < 400:
                return True, f"正常 (HTTP {status})"
            return False, f"HTTP {status}"
    except URLError as e:
        return False, f"无法连接: {e.reason}"
    except Exception as e:
        return False, f"错误: {e}"


def update_retrieved_date(manifest: dict) -> dict:
    """更新所有来源的查询日期"""
    today = datetime.now().strftime("%Y-%m-%d")
    updated = 0
    for src in manifest.get("sources", []):
        if src.get("status") == "current":
            src["retrieved_at"] = today
            updated += 1
    manifest["metadata"]["last_updated"] = today
    print(f"已更新 {updated} 个当前有效来源的查询日期")
    return manifest


def check_all_sources(manifest: dict) -> dict:
    """检查所有来源的可访问性"""
    issues = []
    for src in manifest.get("sources", []):
        url = src.get("official_source", "")
        if not url:
            continue
        print(f"检查: {src.get('title', '未命名')} ...", end=" ")
        ok, msg = check_url(url)
        if ok:
            print("✓")
        else:
            print(f"✗ ({msg})")
            issues.append({
                "source_id": src.get("id"),
                "title": src.get("title"),
                "url": url,
                "issue": msg,
            })
    return {
        "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total": len(manifest.get("sources", [])),
        "issues_found": len(issues),
        "issues": issues,
    }


def mark_historical(manifest: dict, source_id: str) -> dict:
    """将指定来源标记为历史版本"""
    for src in manifest.get("sources", []):
        if src.get("id") == source_id:
            if src.get("status") == "current":
                src["status"] = "historical"
                src["superseded_at"] = datetime.now().strftime("%Y-%m-%d")
                print(f"已将来源 {source_id} 标记为历史版本")
            else:
                print(f"来源 {source_id} 当前状态为 '{src.get('status')}'，无需标记")
            return manifest
    print(f"未找到来源: {source_id}")
    return manifest


def generate_changelog(manifest: dict) -> str:
    """生成变更日志摘要"""
    lines = [f"# 来源清单变更日志", f"\n更新日期: {datetime.now().strftime('%Y-%m-%d')}", ""]
    for src in manifest.get("sources", []):
        notes = src.get("notes", "")
        status = src.get("status", "unknown")
        marker = ""
        if status == "historical":
            marker = "[已废止]"
        elif status == "superseded":
            marker = "[被替代]"
        elif status == "uncertain":
            marker = "[状态不确定]"
        lines.append(f"- {marker} {src.get('title', '未命名')} ({src.get('id')}) - {status}")
        if notes:
            lines.append(f"  备注: {notes}")
    return "\n".join(lines)


def reminder_dynamic(manifest: dict) -> list[str]:
    """提醒需要重新核实的动态资料"""
    reminders = []
    for src in manifest.get("sources", []):
        if src.get("dynamic_data"):
            reminders.append(
                f"- {src.get('title')} ({src.get('id')}) - "
                f"上次查询: {src.get('retrieved_at', '未记录')}"
            )
    return reminders


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="海关资料来源清单管理工具")
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST,
                        help=f"来源清单文件路径（默认: {DEFAULT_MANIFEST}）")
    parser.add_argument("--update-dates", action="store_true",
                        help="更新所有当前来源的查询日期")
    parser.add_argument("--check", action="store_true",
                        help="检查所有来源URL的可访问性")
    parser.add_argument("--mark-historical", type=str, metavar="SOURCE_ID",
                        help="将指定来源标记为历史版本")
    parser.add_argument("--changelog", action="store_true",
                        help="生成变更日志")
    parser.add_argument("--remind", action="store_true",
                        help="显示需要重新核实的动态资料")
    parser.add_argument("--status", action="store_true",
                        help="显示来源状态摘要")

    args = parser.parse_args()

    manifest = load_manifest(args.manifest)
    if not manifest.get("sources"):
        print(f"错误: 加载来源清单失败或无数据 ({args.manifest})")
        sys.exit(1)

    if args.update_dates:
        manifest = update_retrieved_date(manifest)
        save_manifest(manifest, args.manifest)

    if args.check:
        print("检查来源可访问性...\n")
        result = check_all_sources(manifest)
        print(f"\n检查完成: {result['total']}个来源, "
              f"{result['issues_found']}个问题")
        if result["issues"]:
            print("\n问题详情:")
            for issue in result["issues"]:
                print(f"  - [{issue['source_id']}] {issue['title']}: {issue['issue']}")

    if args.mark_historical:
        manifest = mark_historical(manifest, args.mark_historical)
        save_manifest(manifest, args.manifest)

    if args.changelog:
        log = generate_changelog(manifest)
        log_path = "CHANGELOG.md"
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(log)
        print(f"��更日志已保存: {log_path}")

    if args.remind:
        reminders = reminder_dynamic(manifest)
        if reminders:
            print("\n需要重新核实的动态资料:")
            for r in reminders:
                print(r)
        else:
            print("未标记需要动态核实的资料")

    if args.status:
        print("\n来源状态摘要:")
        statuses: dict[str, int] = {}
        for src in manifest.get("sources", []):
            s = src.get("status", "unknown")
            statuses[s] = statuses.get(s, 0) + 1
        for status, count in statuses.items():
            print(f"  {status}: {count}个")
        print(f"  总计: {sum(statuses.values())}个来源")

    # 如果没有指定任何参数，打印帮助
    if not any([args.update_dates, args.check, args.mark_historical,
                args.changelog, args.remind, args.status]):
        print("未指定操作。使用 --help 查看可用选项。\n")
        print("常用命令:")
        print("  --status        查看来源状态摘要")
        print("  --check         检查来源URL可访问性")
        print("  --remind        提醒需要重新核实的动态资料")
        print("  --update-dates  更新查询日期")
