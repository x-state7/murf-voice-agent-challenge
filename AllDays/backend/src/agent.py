import json
import logging
import os
import uuid
import random
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import List, Dict, Optional, Annotated

from dotenv import load_dotenv
from pydantic import Field
from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    JobProcess,
    RoomInputOptions,
    WorkerOptions,
    cli,
    function_tool,
    RunContext,
)
from livekit.plugins import murf, silero, google, deepgram, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("voice_improv_battle")
load_dotenv(".env.local")

# Improv Scenarios
SCENARIOS = [
    "You are a barista who has to tell a customer that their latte is actually a portal to another dimension.",
    "You are a time-travelling tour guide explaining modern smartphones to someone from the 1800s.",
    "You are a restaurant waiter who must calmly tell a customer that their order has escaped the kitchen.",
    "You are a customer trying to return an obviously cursed object to a very skeptical shop owner.",
    "You are an overenthusiastic TV infomercial host selling a product that clearly does not work as advertised.",
    "You are an astronaut who just discovered the ship's coffee machine has developed a personality.",
    "You are a nervous wedding officiant who keeps getting the couple's names mixed up in ridiculous ways.",
    "You are a ghost trying to give a performance review to a living employee.",
    "You are a medieval king reacting to a very modern delivery service showing up at court.",
    "You are a detective interrogating a suspect who only answers in awkward metaphors."
]

@dataclass
class Userdata:
    player_name: Optional[str] = None
    session_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    started_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    improv_state: Dict = field(default_factory=lambda: {
        "current_round": 0,
        "max_rounds": 3,
        "rounds": [],
        "phase": "idle",
        "used_indices": []
    })
    history: List[Dict] = field(default_factory=list)


def _pick_scenario(userdata: Userdata) -> str:
    used = userdata.improv_state.get("used_indices", [])
    candidates = [i for i in range(len(SCENARIOS)) if i not in used]
    if not candidates:
        userdata.improv_state["used_indices"] = []
        candidates = list(range(len(SCENARIOS)))
    idx = random.choice(candidates)
    userdata.improv_state["used_indices"].append(idx)
    return SCENARIOS[idx]


def _host_reaction_text(performance: str) -> str:
    tones = ["supportive", "neutral", "mildly_critical"]
    tone = random.choice(tones)
    highlights = []
    
    if any(w in performance.lower() for w in ("funny", "lol", "hahaha", "haha")):
        highlights.append("great comedic timing")
    if any(w in performance.lower() for w in ("sad", "cry", "tears")):
        highlights.append("good emotional depth")
    if any(w in performance.lower() for w in ("pause", "...")):
        highlights.append("interesting use of silence")
    if not highlights:
        highlights.append(random.choice(["nice character choices", "bold commitment", "unexpected twist"]))

    chosen = random.choice(highlights)
    if tone == "supportive":
        return f"Love that — {chosen}! That was playful and clear. Nice work. Ready for the next one?"
    elif tone == "neutral":
        return f"Hmm — {chosen}. That landed in parts; you had interesting ideas. Let's try the next scene and lean into one choice."
    else:
        return f"Okay — {chosen}, but that felt a bit rushed. Try to make stronger choices next time. Don't be afraid to exaggerate."


def save_session_data(userdata: Userdata):
    """Save improv session data to JSON file in Day-10-Works folder."""
    folder_path = "Day-10-Works"
    os.makedirs(folder_path, exist_ok=True)
    
    counter = 1
    while os.path.exists(os.path.join(folder_path, f"improv_session_{counter}.json")):
        counter += 1
    
    filename = os.path.join(folder_path, f"improv_session_{counter}.json")
    
    session_data = {
        "session_id": userdata.session_id,
        "player_name": userdata.player_name,
        "started_at": userdata.started_at,
        "ended_at": datetime.utcnow().isoformat() + "Z",
        "total_rounds": userdata.improv_state.get("current_round", 0),
        "max_rounds": userdata.improv_state.get("max_rounds", 3),
        "rounds": userdata.improv_state.get("rounds", []),
        "history": userdata.history
    }
    
    with open(filename, 'w') as f:
        json.dump(session_data, f, indent=2)
    
    logger.info(f"Saved improv session to {filename}")
    return filename


@function_tool
async def start_show(
    ctx: RunContext[Userdata],
    name: Annotated[Optional[str], Field(description="Player name", default=None)] = None,
    max_rounds: Annotated[int, Field(description="Number of rounds (3-5 recommended)", default=3)] = 3,
) -> str:
    userdata = ctx.userdata
    userdata.player_name = name.strip() if name else "Contestant"
    
    max_rounds = max(1, min(8, max_rounds))
    userdata.improv_state["max_rounds"] = int(max_rounds)
    userdata.improv_state["current_round"] = 0
    userdata.improv_state["rounds"] = []
    userdata.improv_state["phase"] = "intro"
    userdata.history.append({
        "time": datetime.utcnow().isoformat() + "Z",
        "action": "start_show",
        "name": userdata.player_name
    })

    intro = (
        f"Welcome to Improv Battle! I'm your host — let's get ready to play. "
        f"{userdata.player_name}, we'll run {userdata.improv_state['max_rounds']} rounds. "
        "Rules: I'll give you a quick scene, you'll improvise in character. When you're done say 'End scene' or pause — I'll react and move on. Have fun!"
    )
    
    scenario = _pick_scenario(userdata)
    userdata.improv_state["current_round"] = 1
    userdata.improv_state["phase"] = "awaiting_improv"
    userdata.history.append({
        "time": datetime.utcnow().isoformat() + "Z",
        "action": "present_scenario",
        "round": 1,
        "scenario": scenario
    })

    return intro + "\nRound 1: " + scenario + "\nStart improvising now!"


@function_tool
async def next_scenario(ctx: RunContext[Userdata]) -> str:
    userdata = ctx.userdata
    if userdata.improv_state.get("phase") == "done":
        return "The show is already over. Say 'start show' to play again."

    cur = userdata.improv_state.get("current_round", 0)
    maxr = userdata.improv_state.get("max_rounds", 3)
    if cur >= maxr:
        userdata.improv_state["phase"] = "done"
        return await summarize_show(ctx)

    next_round = cur + 1
    scenario = _pick_scenario(userdata)
    userdata.improv_state["current_round"] = next_round
    userdata.improv_state["phase"] = "awaiting_improv"
    userdata.history.append({
        "time": datetime.utcnow().isoformat() + "Z",
        "action": "present_scenario",
        "round": next_round,
        "scenario": scenario
    })
    return f"Round {next_round}: {scenario}\nGo!"


@function_tool
async def record_performance(
    ctx: RunContext[Userdata],
    performance: Annotated[str, Field(description="Player's improv performance")],
) -> str:
    userdata = ctx.userdata
    round_no = userdata.improv_state.get("current_round", 0)
    
    last_entry = userdata.history[-1] if userdata.history else {}
    scenario = last_entry.get("scenario", "(unknown)")
    
    reaction = _host_reaction_text(performance)

    userdata.improv_state["rounds"].append({
        "round": round_no,
        "scenario": scenario,
        "performance": performance,
        "reaction": reaction,
    })
    userdata.improv_state["phase"] = "reacting"
    userdata.history.append({
        "time": datetime.utcnow().isoformat() + "Z",
        "action": "record_performance",
        "round": round_no
    })

    if round_no >= userdata.improv_state.get("max_rounds", 3):
        userdata.improv_state["phase"] = "done"
        closing = "\n" + reaction + "\nThat's the final round. "
        closing += (await summarize_show(ctx))
        return closing

    return reaction + "\nWhen you're ready, say 'Next' or I'll give you the next scene."


@function_tool
async def summarize_show(ctx: RunContext[Userdata]) -> str:
    userdata = ctx.userdata
    rounds = userdata.improv_state.get("rounds", [])
    if not rounds:
        return "No rounds were played. Thanks for stopping by Improv Battle!"

    summary_lines = [f"Thanks for playing, {userdata.player_name}! Here's a short recap:"]
    
    for r in rounds:
        perf_snip = (r.get("performance") or "").strip()
        if len(perf_snip) > 80:
            perf_snip = perf_snip[:77] + "..."
        summary_lines.append(
            f"Round {r.get('round')}: {r.get('scenario')} — You: '{perf_snip}' | Host: {r.get('reaction')}"
        )

    mentions_character = sum(
        1 for r in rounds 
        if any(w in (r.get('performance') or '').lower() for w in ('i am', "i'm", 'as a', 'character', 'role'))
    )
    mentions_emotion = sum(
        1 for r in rounds 
        if any(w in (r.get('performance') or '').lower() for w in ('sad', 'angry', 'happy', 'love', 'cry', 'tears'))
    )

    profile = "You seem to be a player who "
    if mentions_character > len(rounds) / 2:
        profile += "commits to character choices"
    elif mentions_emotion > 0:
        profile += "brings emotional color to scenes"
    else:
        profile += "likes surprising beats and twists"
    profile += ". Keep leaning into clear choices and stronger stakes."

    summary_lines.append(profile)
    summary_lines.append("Thanks for performing on Improv Battle — hope to see you again!")

    userdata.history.append({
        "time": datetime.utcnow().isoformat() + "Z",
        "action": "summarize_show"
    })
    
    return "\n".join(summary_lines)


@function_tool
async def stop_show(
    ctx: RunContext[Userdata],
    confirm: Annotated[bool, Field(description="Confirm stop", default=False)] = False
) -> str:
    userdata = ctx.userdata
    if not confirm:
        return "Are you sure you want to stop the show? Say 'stop show yes' to confirm."
    userdata.improv_state["phase"] = "done"
    userdata.history.append({
        "time": datetime.utcnow().isoformat() + "Z",
        "action": "stop_show"
    })
    return "Show stopped. Thanks for coming to Improv Battle!"


class GameMasterAgent(Agent):
    def __init__(self):
        instructions = """You are the host of a TV improv show called 'Improv Battle'.
        Role: High-energy, witty, and clear about rules. Guide a single contestant through a series of short improv scenes.

        Behavioural rules:
        - Introduce the show and explain the rules at the start.
        - Present clear scenario prompts (who you are, what's happening, what's the tension).
        - Prompt the player to improvise and listen for "End scene" or accept their performance.
        - After each scene, react in a varied, realistic way (supportive, neutral, mildly critical).
        - Run the configured number of rounds, then summarize the player's style.
        - Keep turns short and TTS-friendly.
        
        Use the provided tools: start_show, next_scenario, record_performance, summarize_show, stop_show."""
        
        super().__init__(
            instructions=instructions,
            tools=[start_show, next_scenario, record_performance, summarize_show, stop_show],
        )


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {"room": ctx.room.name}
    logger.info("🎭 STARTING VOICE IMPROV HOST — Improv Battle")

    userdata = Userdata()

    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=google.LLM(model="gemini-2.5-flash"),
        tts=murf.TTS(
            voice="en-US-marcus",
            style="Conversational",
            text_pacing=True,
        ),
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata.get("vad"),
        userdata=userdata,
    )

    async def save_on_disconnect():
        if userdata.improv_state.get("rounds"):
            filename = save_session_data(userdata)
            logger.info(f"Session ended. Data saved to {filename}")
        else:
            logger.info("Session ended. No rounds to save.")
    
    ctx.add_shutdown_callback(save_on_disconnect)

    await session.start(
        agent=GameMasterAgent(),
        room=ctx.room,
        room_input_options=RoomInputOptions(noise_cancellation=noise_cancellation.BVC()),
    )

    await ctx.connect()


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))