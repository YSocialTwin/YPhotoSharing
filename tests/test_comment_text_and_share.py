"""Generated text clean-up, localized in-code prompts and share commentary (no identifier as caption)."""

import asyncio

import pytest

from YPhotoSharing import prompt_store as ps
from YPhotoSharing.common_utils import strip_wrapping_quotes
from YPhotoSharing.YClient.actions import share as share_mod


@pytest.mark.parametrize(
    "raw, expected",
    [
        ('"Che foto bellissima"', "Che foto bellissima"),
        ("“Great photo”", "Great photo"),
        ("«Bella»", "Bella"),
        ('""Bravo""', "Bravo"),
        ('He said "hi" to me', 'He said "hi" to me'),
        ('"one" and "two"', '"one" and "two"'),
        ('"', '"'),
        ("", ""),
    ],
)
def test_strip_wrapping_quotes(raw, expected):
    assert strip_wrapping_quotes(raw) == expected


def test_english_in_code_prompts_are_unchanged():
    assert ps.prompt("ygram_mention_author", author="ann") == "You may @mention the author (@ann). "
    assert ps.prompt("ygram_mention_others", users="@a, @b") == "You may also optionally mention these users: @a, @b"
    assert ps.prompt("ygram_mention_users", users="@a") == "You may optionally mention these users: @a"
    assert ps.prompt("ygram_memory_note", memory_context="x") == "[System note: x]"
    assert ps.prompt("ygram_default_persona") == "You are an Instagram user."
    assert ps.prompt("ygram_reply_caption") == "Replying to comment thread"
    assert ps.prompt("ygram_dm_caption") == "Sending a direct message."
    assert ps.prompt("ygram_describe_photo") == "Describe this photo:"


def test_italian_translates_every_new_key():
    keys = [k for k in ps.get.__globals__["_pack"]("en") if k.startswith("ygram_")]
    assert len(keys) == 9
    for key in keys:
        assert ps.get(key, "it") != ps.get(key, "en"), key


class _Remote:
    def __init__(self, fn):
        self._fn = fn

    async def remote(self, *a, **k):
        return self._fn(*a, **k)


class _Server:
    def __init__(self):
        self.posted = None
        self.get_recommendation = _Remote(lambda *a, **k: ["p1"])
        self.get_photo = _Remote(lambda pid: {"id": pid, "user_id": "u-parent", "image_url": "x.jpg", "caption": "Bel tramonto"})
        self.get_photo_topics = _Remote(lambda pid: [])
        self.get_user = _Remote(lambda uid: {"username": "marta"})
        self.post_photo = _Remote(self._post)

    def _post(self, data):
        self.posted = data
        return "new-id"


class _Llm:
    def __init__(self, text="\"Che meraviglia\""):
        self.generate_share_commentary = _Remote(lambda **k: text)


def _run(**kw):
    server = _Server()
    asyncio.run(share_mod.share_photo(server, "u1", "r1", **kw))
    return server.posted


def test_share_caption_is_the_generated_commentary_without_quotes():
    posted = _run(llm_service=_Llm(), agent_attrs={"llm": True})
    assert posted["caption"] == "Che meraviglia"
    assert posted["parent_photo_id"] == "p1"


def test_share_without_llm_carries_no_identifier():
    posted = _run()
    assert posted["caption"] == ""
    assert "u-parent" not in posted["caption"] and "Shared from" not in posted["caption"]


def test_share_survives_a_failing_llm():
    class Boom:
        generate_share_commentary = _Remote(lambda **k: (_ for _ in ()).throw(RuntimeError("down")))

    assert _run(llm_service=Boom(), agent_attrs={"llm": True})["caption"] == ""
