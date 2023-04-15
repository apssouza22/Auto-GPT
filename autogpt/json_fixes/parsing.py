"""Fix and parse JSON strings."""

import contextlib
import json
from typing import Any, Dict, Union

from autogpt.config import Config
from autogpt.json_fixes.auto_fix import fix_json
from autogpt.json_fixes.bracket_termination import balance_braces
from autogpt.json_fixes.escaping import fix_invalid_escape
from autogpt.json_fixes.missing_quotes import add_quotes_to_property_names
from autogpt.logs import logger

CFG = Config()


JSON_SCHEMA = """
{
    "command": {
        "name": "command name",
        "args": {
            "arg name": "value"
        }
    },
    "thoughts":
    {
        "text": "thought",
        "reasoning": "reasoning",
        "plan": "- short bulleted\n- list that conveys\n- long-term plan",
        "criticism": "constructive self-criticism",
        "speak": "thoughts summary to say to user"
    }
}
"""


def correct_json(json_to_load: str) -> str:
    """
    Correct common JSON errors.

    Args:
        json_to_load (str): The JSON string.
    """

    try:
        if CFG.debug_mode:
            print("json", json_to_load)
        json.loads(json_to_load)
        return json_to_load
    except json.JSONDecodeError as e:
        if CFG.debug_mode:
            print("json loads error", e)
        error_message = str(e)
        if error_message.startswith("Invalid \\escape"):
            json_to_load = fix_invalid_escape(json_to_load, error_message)
        if error_message.startswith(
            "Expecting property name enclosed in double quotes"
        ):
            json_to_load = add_quotes_to_property_names(json_to_load)
            try:
                json.loads(json_to_load)
                return json_to_load
            except json.JSONDecodeError as e:
                if CFG.debug_mode:
                    print("json loads error - add quotes", e)
                error_message = str(e)
        if balanced_str := balance_braces(json_to_load):
            return balanced_str
    return json_to_load


def fix_and_parse_json(
    json_to_load: str, try_to_fix_with_gpt: bool = True
) -> Union[str, Dict[Any, Any]]:
    """Fix and parse JSON string

    Args:
        json_to_load (str): The JSON string.
        try_to_fix_with_gpt (bool, optional): Try to fix the JSON with GPT.
            Defaults to True.

    Returns:
        Union[str, Dict[Any, Any]]: The parsed JSON.
    """

    with contextlib.suppress(json.JSONDecodeError):
        json_to_load = json_to_load.replace("\t", "")
        return json.loads(json_to_load)

    with contextlib.suppress(json.JSONDecodeError):
        json_to_load = correct_json(json_to_load)
        return json.loads(json_to_load)
    try:
        maybe_fixed_json = extract_longest_curly_braces_content(json_to_load)
        return json.loads(maybe_fixed_json)
    except (json.JSONDecodeError, ValueError) as e:
        return try_ai_fix(try_to_fix_with_gpt, e, json_to_load)

def extract_longest_curly_braces_content(string):
    """
    :param string: The string to extract the longest content from.
    Extract the longest content between valid curly braces in a string.
    This is useful when the return contain multiple JSON objects or texts.
    """
    stack = []
    start = -1
    result = ''
    longest_len = 0
    longest_content = ''
    for i in range(len(string)):
        if string[i] == '{':
            stack.append(i)
        elif string[i] == '}':
            if len(stack) == 0:
                start = i
            else:
                start = stack.pop()
                if len(stack) == 0:
                    content = string[start + 1:i]
                    content_len = len(content)
                    if content_len > longest_len:
                        longest_len = content_len
                        longest_content = content
    return f"{{{longest_content}}}"

def try_ai_fix(
    try_to_fix_with_gpt: bool, exception: Exception, json_to_load: str
) -> Union[str, Dict[Any, Any]]:
    """Try to fix the JSON with the AI

    Args:
        try_to_fix_with_gpt (bool): Whether to try to fix the JSON with the AI.
        exception (Exception): The exception that was raised.
        json_to_load (str): The JSON string to load.

    Raises:
        exception: If try_to_fix_with_gpt is False.

    Returns:
        Union[str, Dict[Any, Any]]: The JSON string or dictionary.
    """
    if not try_to_fix_with_gpt:
        raise exception

    logger.warn(
        "Warning: Failed to parse AI output, attempting to fix."
        "\n If you see this warning frequently, it's likely that"
        " your prompt is confusing the AI. Try changing it up"
        " slightly."
    )
    # Now try to fix this up using the ai_functions
    ai_fixed_json = fix_json(json_to_load, JSON_SCHEMA)

    if ai_fixed_json != "failed":
        return json.loads(ai_fixed_json)
    # This allows the AI to react to the error message,
    #   which usually results in it correcting its ways.
    logger.error("Failed to fix AI output, telling the AI.")
    return json_to_load
