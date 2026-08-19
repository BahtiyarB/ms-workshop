# travel_assistant/main.py — Python entry point that hosts TravelBuddy: it creates
# the Foundry model client, defines the agent, and starts the Responses server.
# Complete the one TODO inside main() below.
import os

from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient
from agent_framework_foundry_hosting import FoundryToolbox, ResponsesHostServer  # <-- add FoundryToolbox
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv
# travel_assistant/main.py
from tools import convert_currency, get_local_time, get_weather

load_dotenv(override=True)


def main() -> None:
    # Foundry model client, built from your .env settings.
    client = FoundryChatClient(
        project_endpoint=os.environ["AZURE_AI_PROJECT_ENDPOINT"],
        model=os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"],
        credential=DefaultAzureCredential(),

        client = FoundryChatClient(
            project_endpoint=os.environ["AZURE_AI_PROJECT_ENDPOINT"],
            model=os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"],
            credential=credential,                # <-- reuse the same credential
    ),

    # FoundryToolbox resolves the toolbox endpoint from the environment
    # (TOOLBOX_ENDPOINT, or FOUNDRY_PROJECT_ENDPOINT + TOOLBOX_NAME), authenticates
    # every request with the credential, and transparently forwards the platform
    # per-request call-id to the toolbox. The hosting server enters the agent, which
    # connects the toolbox on first use and closes it at shutdown.
    toolbox = FoundryToolbox(credential)
    )

    # TODO: write TravelBuddy's system instructions. Describe a friendly travel
    # assistant that gives practical, concise trip-planning advice — local context,
    # budget awareness, and safety-minded tips.
    agent = Agent(
        client=client,
        name="travel-buddy",
        instructions="You are TravelBuddy, a friendly and concise travel assistant." \
            "Give practical trip-planning advice tailored to the user’s destination" \
            "dates, interests, travel style, and budget. Recommend realistic itineraries, " \
            "local food and experiences, transport options, cultural etiquette, seasonal " \
            "considerations, and money-saving tips.Prioritize traveler safety by mentioning " \
            "relevant scams, neighborhood precautions, entry requirements, emergency contacts, " \
            "payment methods, and connectivity advice when useful.Keep responses clear, " \
            "actionable, and easy to skim. Ask only the most important clarifying questions " \
            "when essential details are missing." \
#            "Use the OctoTrip Flights MCP server when the traveler asks about " \
#            "flights, routes, fares, or schedules; pass IATA airport codes and a " \
#            "departure date (YYYY-MM-DD) — if the traveler doesn't give one, call " \
#            "get_local_time and use the date part of its iso_time as today's date — " \
#            "and summarize the options you find." \
            "Use the Foundry Toolbox for flight search (when the traveler gives no "
            "departure date, call get_local_time and use the date part of its "
            "iso_time as today's date), for web search of current "
            "travel advisories and events, and for Code Interpreter to analyze an "
            "uploaded itinerary.csv (budget totals, currency conversion, charts)."
               "" ,
        # History is managed by the hosting infrastructure, so don't store it server-side.
    tools = [
        get_weather,        # <-- kept from Step 2
        get_local_time,     # <-- kept from Step 2
        convert_currency,   # <-- kept from Step 2
        toolbox,            # <-- replaces the Step 3 client.get_mcp_tool(...) entry
    ],
        default_options={"store": False},
    )

    ResponsesHostServer(agent).run()


if __name__ == "__main__":
    main()
