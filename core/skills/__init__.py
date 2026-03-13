"""Skills 技能目录（Dexter 借鉴）

SKILL.md 格式：YAML frontmatter（name, description）+ Markdown 正文。
扫描 core/skills/ 与可选用户目录，将技能元数据注入 system prompt。
"""

from .registry import discover_skills, build_skills_prompt_section

__all__ = ["discover_skills", "build_skills_prompt_section"]
