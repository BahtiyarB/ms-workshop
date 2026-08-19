# travel_assistant/main.py
import logging
import os

import subprocess    # NEW
import sys           # NEW
from pathlib import Path  # NEW
from typing import Any    # NEW

from agent_framework import Agent
from agent_framework.azure import AzureAISearchContextProvider
from agent_framework.foundry import FoundryChatClient
from agent_framework_foundry_hosting import FoundryToolbox, ResponsesHostServer
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

from agent_framework import (  
    FileSkill,
    FileSkillScript,
    Skill,
    SkillScript,
    SkillsProvider,
)


from tools import convert_currency, get_local_time, get_weather

LOCAL_SKILLS_DIR = Path(__file__).parent / "skills"

class TrustedSkillsProvider(SkillsProvider):
    """A SkillsProvider that runs its skill tools without an approval gate.

    The hosted ResponsesHostServer runs the agent without an AgentSession, so
    ToolApprovalMiddleware can't be used to auto-approve. Our skills are authored
    in this repo, so we trust them and register their tools as ``never_require``.
    """

    def _create_tools(self, skills):
        tools = super()._create_tools(skills)
        for tool in tools:
            tool.approval_mode = "never_require"
        return tools



load_dotenv(override=True)

logger = logging.getLogger(__name__)


def main() -> None:
    credential = DefaultAzureCredential()

    client = FoundryChatClient(
        project_endpoint=os.environ["AZURE_AI_PROJECT_ENDPOINT"],
        model=os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"],
        credential=credential,
    )

    # FoundryToolbox reads TOOLBOX_ENDPOINT from the environment, authenticates
    # every request with the credential, and connects on first use. The toolbox
    # bundles web search, Code Interpreter, and the OctoTrip flights MCP server.
    toolbox = FoundryToolbox(credential)

    tools = [
        get_weather,
        get_local_time,
        convert_currency,
        toolbox,
    ]

    # RAG: search the destinations index before each turn and inject the top
    # matches into model context.
    search_endpoint = os.environ["AZURE_AI_SEARCH_ENDPOINT"]
    search_index_name = os.environ["AZURE_AI_SEARCH_INDEX_NAME"]
    context_providers = [
        AzureAISearchContextProvider(
            source_id="travelbuddy_destinations",
            endpoint=search_endpoint,
            index_name=search_index_name,
            credential=credential,
            mode="semantic",
            top_k=3,
        )
    ]

    context_providers.append(
        TrustedSkillsProvider.from_paths([LOCAL_SKILLS_DIR], script_runner=run_local_skill_script)
    )  # NEW — RAG provider from Step 5 stays

    agent = Agent(
        client=client,
        name="travel-buddy",
        instructions=(
            "You are TravelBuddy, a friendly travel assistant. "
            "Give practical, concise advice for trip planning, including local context, "
            "budget awareness, and safety-minded tips. "
            "Use your tools for weather, local time, and currency conversion "
            "when the traveler asks time-sensitive questions. Keep answers brief. "
            "Use the Foundry Toolbox for flight search (when the traveler gives no "
            "departure date, call get_local_time and use the date part of its "
            "iso_time as today's date), for web search of current "
            "travel advisories and events, and for Code Interpreter to analyze an "
            "uploaded itinerary.csv (budget totals, currency conversion, charts). "
            "Use the grounded destination context when relevant; if the destinations "
            "index does not contain enough detail, say what is missing."
            "When the traveler wants a downloadable trip guide or a day-by-day plan, "   # NEW
            "use the travel-guide skill to render a grounded PDF guide before answering."  # NEW            
        ),
        tools=tools,
        context_providers=context_providers,
        default_options={"store": False},
    )

    ResponsesHostServer(agent).run()


def run_local_skill_script(
    skill: Skill, script: SkillScript, args: dict[str, Any] | list[str] | None = None
) -> str:
    """Run a trusted file-based skill script with positional CLI arguments."""
    if not isinstance(skill, FileSkill) or not isinstance(script, FileSkillScript):
        return "Error: only file-based skill scripts can be run by this runner."

    skill_path = Path(skill.path).resolve()
    script_path = Path(script.full_path).resolve()
    if skill_path != script_path and skill_path not in script_path.parents:
        return f"Error: script '{script.name}' resolves outside the skill directory."

    command = [sys.executable, str(script_path)]
    if isinstance(args, list):
        for item in args:
            if not isinstance(item, str):
                return (
                    f"Error: script '{script.name}' only accepts string CLI arguments, "
                    f"but received a {type(item).__name__}."
                )
        command.extend(args)
    elif args is not None:
        return (
            f"Error: script '{script.name}' expects positional CLI arguments as a list "
            f"of strings, but received {type(args).__name__}."
        )

    try:
        completed = subprocess.run(
            command, cwd=skill_path, capture_output=True, check=False, text=True, timeout=60
        )
    except subprocess.TimeoutExpired:
        return f"Error: script '{script.name}' timed out after 60 seconds."

    if completed.returncode != 0:
        details = completed.stderr.strip() or completed.stdout.strip() or "no error output was produced."
        return f"Error: script '{script.name}' failed with exit code {completed.returncode}: {details}"
    return completed.stdout.strip() or f"Script '{script.name}' completed successfully."


if __name__ == "__main__":
    main()
