import os
import json
import asyncio
from dotenv import load_dotenv

from livekit import agents, api
from livekit.agents import Agent, AgentSession, JobContext, RunContext
from livekit.plugins import noise_cancellation, silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

# Assuming these are in your project (same as before)
from prompt import AGENT_INSTRUCTIONS, SESSION_INSTRUCTIONS

load_dotenv(".env.local")

class Assistant(Agent):
    def __init__(self):
        super().__init__(
            instructions=AGENT_INSTRUCTIONS,
        )

async def entrypoint(ctx: JobContext):
    await ctx.connect(auto_subscribe=agents.AutoSubscribe.AUDIO_ONLY)

    # Check if this job is for an outbound call
    metadata = ctx.job.metadata
    phone_number = None
    if metadata:
        try:
            data = json.loads(metadata)
            phone_number = data.get("phone_number")
        except json.JSONDecodeError:
            pass

    # Create the agent session (same as your original code)
    session = AgentSession(
        stt="deepgram/nova-3:en-US",
        llm="google/gemini-2.5-flash",
        tts="elevenlabs/eleven_flash_v2:iP95p4xoKVk53GoZ742B",
        vad=silero.VAD.load(),
        turn_detection=MultilingualModel(),
    )

    await session.start(
        room=ctx.room,
        agent=Assistant(),
        room_input_options=agents.RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )

    # Optional initial message for the session
    await session.generate_reply(instructions=SESSION_INSTRUCTIONS)

    # If this is an outbound call, dial the user
    if phone_number:
        # IMPORTANT: Replace with your actual outbound trunk ID
        # You can get it with: lk sip outbound-trunk list
        sip_trunk_id = os.getenv("SIP_OUTBOUND_TRUNK_ID")  # Put it in .env.local or hardcode for testing

        if not sip_trunk_id:
            print("Warning: SIP_OUTBOUND_TRUNK_ID not set, cannot make outbound call")
            return

        # Create SIP participant to dial out
        sip_api = api.SIPServiceAPI(url=os.getenv("LIVEKIT_URL"), api_key=os.getenv("LIVEKIT_API_KEY"), api_secret=os.getenv("LIVEKIT_API_SECRET"))

        await sip_api.create_sip_participant(
            room=ctx.room.name,
            sip_trunk_id=sip_trunk_id,
            sip_call_to=phone_number,  # e.g. "+12345678911"
            # Optional: customize caller ID if your trunk allows multiple numbers
            # sip_number="+YOUR_TWILIO_NUMBER",
            # display_name="My Company",
            # playback_silence_on_connect=True,  # Wait silently until answered
        )

        print(f"Outbound call initiated to {phone_number}")

    # For outbound calls, avoid sending an initial greeting automatically
    # The agent will wait for the human to speak first

if __name__ == "__main__":
    # Run the worker (same as before)
    agents.cli.run_app(
        agents.WorkerOptions(entrypoint_fnc=entrypoint)
    )