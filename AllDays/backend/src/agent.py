import logging
import json
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    JobProcess,
    MetricsCollectedEvent,
    RoomInputOptions,
    WorkerOptions,
    cli,
    metrics,
    tokenize,
    function_tool,
    RunContext
)
from livekit.plugins import murf, silero, google, deepgram, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("agent")

load_dotenv(".env.local")

# Path to wellness log file
WELLNESS_LOG_PATH = Path(__file__).parent.parent / "wellness_log.json"


# Helper functions for JSON persistence
def load_wellness_log():
    """Load wellness log from JSON file."""
    if WELLNESS_LOG_PATH.exists():
        try:
            with open(WELLNESS_LOG_PATH, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            logger.warning("Invalid JSON in wellness log, starting fresh")
            return {"check_ins": []}
    return {"check_ins": []}


def save_wellness_log(data):
    """Save wellness log to JSON file."""
    with open(WELLNESS_LOG_PATH, 'w') as f:
        json.dump(data, f, indent=2)


class Assistant(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions="""You are a supportive voice-based wellness companion. The user talks to you through voice.

                Your job is to:

                Have friendly daily check-ins about their mood, energy, and overall wellbeing

                Ask them about their plans or goals for the day (1–3 simple intentions)

                Give practical, realistic, and easy-to-follow suggestions

                Stay away from medical advice or diagnosis — you’re here to support, not act as a clinician

                End each check-in with a short summary of what they shared and confirm it with them

                Your style should be:

                Warm, understanding, and non-judgmental

                Short and straightforward responses

                No fancy formatting or emojis

                Encourage small, doable steps rather than big overwhelming targets

                When you start talking, check for past entries using the get_previous_checkins tool.
                If there are earlier check-ins, mention them naturally (for example: “Last time you said your energy was low. How are you feeling today?”).
            """,
        )

    @function_tool
    async def get_previous_checkins(self, context: RunContext, limit: int = 3):
        """Retrieve previous wellness check-ins to reference past conversations.
        
        Use this tool at the start of a conversation to personalize the check-in based on previous sessions.
        
        Args:
            limit: Maximum number of previous check-ins to retrieve (default: 3)
        """
        logger.info(f"Retrieving last {limit} check-ins")
        
        data = load_wellness_log()
        check_ins = data.get("check_ins", [])
        
        if not check_ins:
            return "No previous check-ins found. This appears to be the first session."
        
        # Get the most recent check-ins
        recent = check_ins[-limit:]
        recent.reverse()  # Most recent first
        
        summary = f"Found {len(recent)} previous check-in(s):\n"
        for i, entry in enumerate(recent, 1):
            summary += f"\n{i}. Date: {entry.get('date')}\n"
            summary += f"   Mood: {entry.get('mood', 'N/A')}\n"
            summary += f"   Objectives: {', '.join(entry.get('objectives', []))}\n"
            if entry.get('summary'):
                summary += f"   Summary: {entry.get('summary')}\n"
        
        return summary
    
    @function_tool
    async def save_wellness_checkin(self, context: RunContext, mood: str, objectives: list[str], summary: str = ""):
        """Save the current wellness check-in data to persistent storage.
        
        Call this tool after completing a check-in conversation with the user.
        
        Args:
            mood: User's self-reported mood or energy level (text description)
            objectives: List of 1-3 intentions or goals the user stated for the day
            summary: Optional brief summary sentence of the check-in
        """
        logger.info(f"Saving check-in: mood={mood}, objectives={objectives}")
        
        data = load_wellness_log()
        
        # Create new check-in entry
        entry = {
            "date": datetime.now().isoformat(),
            "mood": mood,
            "objectives": objectives,
        }
        
        if summary:
            entry["summary"] = summary
        
        # Add to check-ins list
        data["check_ins"].append(entry)
        
        # Save to file
        save_wellness_log(data)
        
        return f"Check-in saved successfully! Recorded mood: {mood}, and {len(objectives)} objective(s)."


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


async def entrypoint(ctx: JobContext):
    # Logging setup
    # Add any other context you want in all log entries here
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    # Set up a voice AI pipeline using OpenAI, Cartesia, AssemblyAI, and the LiveKit turn detector
    session = AgentSession(
        
        stt=deepgram.STT(model="nova-2"),
        llm=google.LLM(
                model="gemini-2.5-flash",
            ),
        # Text-to-speech (TTS) is your agent's voice, turning the LLM's text into speech that the user can hear
        # See all available models as well as voice selections at https://docs.livekit.io/agents/models/tts/
        tts=murf.TTS(
                voice="en-US-matthew", 
                style="Conversation",
                tokenizer=tokenize.basic.SentenceTokenizer(min_sentence_len=2),
                text_pacing=True
            ),
        # VAD and turn detection are used to determine when the user is speaking and when the agent should respond
        # See more at https://docs.livekit.io/agents/build/turns
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        # allow the LLM to generate a response while waiting for the end of turn
        # See more at https://docs.livekit.io/agents/build/audio/#preemptive-generation
        preemptive_generation=True,
    )

    # For more information, see https://docs.livekit.io/agents/build/metrics/
    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Usage: {summary}")

    ctx.add_shutdown_callback(log_usage)


    # Start the session, which initializes the voice pipeline and warms up the models
    await session.start(
        agent=Assistant(),
        room=ctx.room,
      
    )

    # Join the room and connect to the user
    await ctx.connect()


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))