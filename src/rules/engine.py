"""
Rules Engine
------------
Applies text replacement rules to posts before forwarding.
Rules are stored in MongoDB and can be managed via the web dashboard.
Supports: username replacement, link replacement, text stripping, and footer branding.
"""

import re
import logging

logger = logging.getLogger(__name__)


class RulesEngine:
    """Apply configurable text transformation rules to post content."""

    def __init__(self, db=None):
        self.db = db

    def load_rules(self, source_id=None, target_id=None) -> list:
        """Load active rules matching global rules and channel-specific rules."""
        if self.db is None:
            return []

        all_rules = list(self.db.rules.find({"active": True}))
        if not source_id and not target_id:
            return all_rules

        matching_rules = []
        for r in all_rules:
            r_src = r.get("source_id")
            r_tgt = r.get("target_id")
            r_targets = r.get("target_ids") or []

            # 1. Global rules (no specific source and target) apply to all channels
            is_global = not r_src and not r_tgt and not r_targets
            if is_global:
                matching_rules.append(r)
                continue

            # 2. Check source match
            src_match = True
            if r_src:
                src_match = (str(r_src).strip().lower() == str(source_id).strip().lower())

            # 3. Check target match
            tgt_match = True
            if r_tgt or r_targets:
                norm_tgt = str(target_id).strip().lower()
                matches_main = bool(r_tgt and str(r_tgt).strip().lower() == norm_tgt)
                matches_list = any(str(t).strip().lower() == norm_tgt for t in r_targets)
                tgt_match = matches_main or matches_list

            if src_match and tgt_match:
                matching_rules.append(r)

        return matching_rules

    def apply_rules(self, text: str, source_id=None, target_id=None) -> str:
        """Apply all matching rules to the text in priority order."""
        if not text:
            return text

        rules = self.load_rules(source_id, target_id)
        if not rules:
            return text

        # Sort by priority (lower number = higher priority)
        rules = sorted(rules, key=lambda r: r.get("priority", 0))

        result = text
        for rule in rules:
            result = self._apply_single_rule(result, rule)

        return result

    def _apply_single_rule(self, text: str, rule: dict) -> str:
        """Apply a single transformation rule."""
        rule_type = rule.get("type", "replace")
        active = rule.get("active", True)

        if not active:
            return text

        try:
            if rule_type == "replace":
                # Replace specific text patterns
                pattern = rule.get("pattern", "")
                replacement = rule.get("replacement", "")
                result = text.replace(pattern, replacement) if pattern else text

            elif rule_type == "regex":
                # Apply regex replacement
                pattern = rule.get("pattern", "")
                replacement = rule.get("replacement", "")
                if pattern:
                    result = re.sub(pattern, replacement, text)
                else:
                    result = text

            elif rule_type == "strip":
                # Strip unwanted text patterns
                pattern = rule.get("pattern", "")
                if pattern:
                    result = re.sub(pattern, "", text)
                else:
                    result = text

            elif rule_type == "footer":
                # Append branding footer
                footer = rule.get("replacement", "")
                if footer:
                    result = text + "\n\n" + footer
                else:
                    result = text

            elif rule_type == "prefix":
                # Prepend text
                prefix = rule.get("replacement", "")
                if prefix:
                    result = prefix + "\n" + text
                else:
                    result = text

            else:
                result = text

            return result

        except re.error as e:
            logger.warning(f"Regex error in rule '{rule.get('_id', 'unknown')}': {e}")
            return text
        except Exception as e:
            logger.error(f"Error applying rule: {e}")
            return text

    def is_blacklisted(self, channel_id: int) -> bool:
        """Check if a channel is in the blacklist."""
        if self.db is None:
            return False

        entry = self.db.blacklist.find_one({"channel_id": channel_id})
        return entry is not None

    def create_default_rules(self):
        """Create default rules if none exist."""
        if self.db is None:
            return

        count = self.db.rules.count_documents({})
        if count == 0:
            defaults = [
                {
                    "name": "Strip @usernames",
                    "type": "regex",
                    "pattern": r"@\w+",
                    "replacement": "[username]",
                    "priority": 1,
                    "active": True,
                },
                {
                    "name": "Branding Footer",
                    "type": "footer",
                    "replacement": "Forwarded by Telegram Forwarder Pro",
                    "priority": 99,
                    "active": True,
                },
            ]
            self.db.rules.insert_many(defaults)
            logger.info("Created default rules")
