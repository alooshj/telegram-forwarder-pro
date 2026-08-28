"""
Transformation Pipeline
-----------------------
Enterprise transformation pipeline for Telegram messages:
- Keyword filtering (Whitelist / Blacklist)
- Automated mention (@username) and link (http/t.me) stripping
- Dynamic header and footer templating with runtime context variables
- Regex and text replacement rules
"""

import re
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class TransformationPipeline:
    """Handles text filtering, sanitization, pattern replacement, and templating."""

    # Pre-compiled regex patterns for maximum performance
    MENTION_PATTERN = re.compile(r"(?<!\w)@[a-zA-Z0-9_]{3,}")
    LINK_PATTERN = re.compile(r"(https?://\S+|t\.me/[a-zA-Z0-9_\+\-]+|www\.\S+)")

    @classmethod
    def check_keywords(cls, text: str, whitelist: list = None, blacklist: list = None) -> tuple[bool, str]:
        """
        Check if text satisfies whitelist and blacklist keyword constraints.
        Returns (is_allowed: bool, reason: str).
        """
        if not text:
            text = ""

        text_lower = text.lower()

        # 1. Check blacklist (if any blacklisted keyword appears, reject)
        if blacklist:
            for kw in blacklist:
                if not kw:
                    continue
                kw_str = str(kw).strip().lower()
                if kw_str and kw_str in text_lower:
                    return False, f"Post contains blacklisted keyword: '{kw}'"

        # 2. Check whitelist (if whitelist is specified, at least one keyword must be present)
        if whitelist and len(whitelist) > 0:
            clean_whitelist = [str(w).strip().lower() for w in whitelist if str(w).strip()]
            if clean_whitelist:
                matched = any(w in text_lower for w in clean_whitelist)
                if not matched:
                    return False, "Post does not contain any required whitelist keywords"

        return True, ""

    @classmethod
    def strip_mentions(cls, text: str, replacement: str = "") -> str:
        """Remove or replace @usernames from text."""
        if not text:
            return ""
        return cls.MENTION_PATTERN.sub(replacement, text).strip()

    @classmethod
    def strip_links(cls, text: str, replacement: str = "") -> str:
        """Remove or replace web and Telegram links from text."""
        if not text:
            return ""
        return cls.LINK_PATTERN.sub(replacement, text).strip()

    @classmethod
    def apply_templating(
        cls,
        text: str,
        header_template: str = "",
        footer_template: str = "",
        context: dict = None
    ) -> str:
        """
        Apply header and footer templates with dynamic variable substitution.
        Variables supported:
        - {source_title}, {source_id}, {source_username}
        - {target_title}, {target_id}
        - {date}, {time}, {msg_id}
        """
        if not context:
            context = {}

        now = datetime.now(timezone.utc)
        safe_ctx = {
            "source_title": str(context.get("source_title") or ""),
            "source_id": str(context.get("source_id") or ""),
            "source_username": str(context.get("source_username") or ""),
            "target_title": str(context.get("target_title") or ""),
            "target_id": str(context.get("target_id") or ""),
            "msg_id": str(context.get("msg_id") or ""),
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M:%S"),
        }

        def _fill_template(tpl: str) -> str:
            if not tpl:
                return ""
            res = tpl
            for k, v in safe_ctx.items():
                res = res.replace(f"{{{k}}}", v)
            return res.strip()

        header = _fill_template(header_template)
        footer = _fill_template(footer_template)

        result_parts = []
        if header:
            result_parts.append(header)
        if text:
            result_parts.append(text)
        if footer:
            result_parts.append(footer)

        return "\n\n".join(result_parts) if result_parts else text

    def process(self, text: str, rule: dict, context: dict = None) -> tuple[bool, str, str]:
        """
        Full pipeline transformation:
        1. Check keywords (whitelist/blacklist)
        2. Strip mentions/links if enabled in rule
        3. Apply replacements
        4. Apply header/footer templating
        Returns (is_allowed: bool, transformed_text: str, reason: str).
        """
        if text is None:
            text = ""

        # 1. Keyword validation
        whitelist = rule.get("whitelist_keywords") or []
        blacklist = rule.get("blacklist_keywords") or []
        is_allowed, reason = self.check_keywords(text, whitelist, blacklist)
        if not is_allowed:
            return False, text, reason

        result = text

        # 2. Automated Stripping
        if rule.get("strip_mentions"):
            mention_rep = rule.get("mention_replacement", "")
            result = self.strip_mentions(result, mention_rep)

        if rule.get("strip_links"):
            link_rep = rule.get("link_replacement", "")
            result = self.strip_links(result, link_rep)

        # 3. Dynamic Templating
        header_tpl = rule.get("header_template") or rule.get("header") or ""
        footer_tpl = rule.get("footer_template") or rule.get("footer") or ""
        if header_tpl or footer_tpl:
            result = self.apply_templating(result, header_tpl, footer_tpl, context)

        return True, result, ""
