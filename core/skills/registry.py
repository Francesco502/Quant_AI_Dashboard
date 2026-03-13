"""Skills 发现与 prompt 拼接（Dexter 借鉴）"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import List, Dict, Any

_SKILLS_DIR_ENV = "SKILLS_DIR"
_SKILLS_ENABLED_ENV = "SKILLS_ENABLED"
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _is_skills_enabled() -> bool:
    val = os.getenv(_SKILLS_ENABLED_ENV, "true").strip().lower()
    return val in ("1", "true", "yes", "on")


def _skill_directories() -> List[Path]:
    dirs: List[Path] = []
    # 项目内 core/skills
    base = Path(__file__).resolve().parent
    if base.is_dir():
        dirs.append(base)
    # 环境变量指定
    custom = os.getenv(_SKILLS_DIR_ENV)
    if custom:
        p = Path(custom)
        if not p.is_absolute():
            p = Path.cwd() / p
        if p.is_dir():
            dirs.append(p)
    # 用户目录
    user_skills = Path.home() / ".quant" / "skills"
    if user_skills.is_dir():
        dirs.append(user_skills)
    return dirs


def _extract_frontmatter(content: str) -> tuple:
    """返回 (frontmatter_dict, body)。若无 --- 则 frontmatter 为空。"""
    m = _FRONTMATTER_RE.match(content)
    if not m:
        return {}, content.strip()
    fm = {}
    for line in m.group(1).splitlines():
        line = line.strip()
        if not line:
            continue
        colon = line.find(":")
        if colon > 0:
            key = line[:colon].strip()
            val = line[colon + 1:].strip().strip("'\"")
            fm[key] = val
    body = content[m.end():].strip()
    return fm, body


def discover_skills() -> List[Dict[str, Any]]:
    """
    扫描所有技能目录，返回 [{"name": "...", "description": "...", "path": "..."}, ...]。
    同名技能以后扫描到的覆盖前面的。
    """
    if not _is_skills_enabled():
        return []
    seen: Dict[str, Dict[str, Any]] = {}
    for skill_dir in _skill_directories():
        if not skill_dir.is_dir():
            continue
        for sub in skill_dir.iterdir():
            if not sub.is_dir():
                continue
            skill_file = sub / "SKILL.md"
            if not skill_file.is_file():
                continue
            try:
                text = skill_file.read_text(encoding="utf-8")
                fm, _ = _extract_frontmatter(text)
                name = fm.get("name") or sub.name
                desc = fm.get("description", "").strip()
                seen[name] = {"name": name, "description": desc, "path": str(skill_file)}
            except Exception:
                continue
    return list(seen.values())


def build_skills_prompt_section() -> str:
    """返回用于拼接到 system prompt 的字符串。"""
    skills = discover_skills()
    if not skills:
        return ""
    lines = ["## 可用技能\n"]
    for s in skills:
        lines.append(f"- **{s['name']}**: {s['description']}")
    lines.append("\n若分析中涉及上述技能描述的场景，可在结论中按技能要点组织输出。")
    return "\n".join(lines)
