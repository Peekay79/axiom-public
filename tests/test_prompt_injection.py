#!/usr/bin/env python3
"""Tests for prompt-only interaction model injection.

The interaction model block must be present in the LLM prompt payload (system-level
prompt content), but must never appear in user-facing Discord output such as the
memory banner.
"""

import sys
import types
import unittest

sys.path.insert(0, "/workspace")


def _ensure_discord_importable_for_tests() -> None:
    """Provide a minimal stub of `discord` if discord.py isn't installed.

    `discord_interface.py` imports discord at module import time. In CI/unit-test
    environments where discord.py isn't available, we stub the minimal surface
    used during import (Intents + commands.Bot decorators).
    """

    try:
        import discord  # noqa: F401

        return
    except Exception:
        pass

    discord_mod = types.ModuleType("discord")

    class _DummyIntents:
        def __init__(self):
            self.messages = False
            self.message_content = False

        @classmethod
        def default(cls):
            return cls()

    discord_mod.Intents = _DummyIntents

    ext_mod = types.ModuleType("discord.ext")
    commands_mod = types.ModuleType("discord.ext.commands")

    class _DummyBot:
        def __init__(self, *args, **kwargs):
            pass

        def command(self, *args, **kwargs):
            def _decorator(fn):
                return fn

            return _decorator

        def event(self, fn):
            return fn

    commands_mod.Bot = _DummyBot

    # Wire module tree
    discord_mod.ext = ext_mod
    ext_mod.commands = commands_mod

    sys.modules.setdefault("discord", discord_mod)
    sys.modules.setdefault("discord.ext", ext_mod)
    sys.modules.setdefault("discord.ext.commands", commands_mod)


class TestInteractionModelPromptInjection(unittest.TestCase):
    def test_build_bot_prompt_contains_interaction_model(self):
        _ensure_discord_importable_for_tests()
        from discord_interface import _build_bot_prompt

        prompt = _build_bot_prompt(
            user_text="Hello",
            world_map_block="",
            recall_block="",
            live_context="",
            boot_prompt_text="You are Axiom.",
        )
        self.assertIn("INTERACTION MODEL", prompt)

    def test_user_visible_memory_banner_does_not_contain_interaction_model(self):
        from utils.memory_recall import build_memory_banner

        banner = build_memory_banner(
            retrieved_count=3,
            selected_count=2,
            top_score=0.9,
            conf_threshold=0.25,
            world_injected=False,
            world_entity_id=None,
            guardrail_mode=False,
        )
        self.assertNotIn("INTERACTION MODEL", banner)


if __name__ == "__main__":
    unittest.main()
