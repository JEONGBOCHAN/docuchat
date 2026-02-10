# -*- coding: utf-8 -*-
"""Voice assignment domain rule.

Pure function that maps a speaker name to the appropriate voice,
used by both audio generation and script preview.
"""


def assign_voice_for_speaker(
    speaker: str,
    host_a_voice: str,
    host_b_voice: str,
) -> str:
    """Determine which voice to use for a given speaker.

    Rules:
      - If the speaker name contains "Host A" or "진행자" → host_a_voice
      - Otherwise → host_b_voice

    Args:
        speaker: The speaker name from the dialogue line.
        host_a_voice: Voice identifier for the primary host.
        host_b_voice: Voice identifier for the secondary host.

    Returns:
        The voice identifier to use.
    """
    if "Host A" in speaker or "진행자" in speaker:
        return host_a_voice
    return host_b_voice
