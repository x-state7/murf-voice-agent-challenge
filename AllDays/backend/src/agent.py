import logging
import os
import json
from datetime import datetime
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
from livekit.agents.llm import ChatMessage
from livekit.plugins import murf, silero, google, deepgram, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("zerodha-agent")
load_dotenv(".env.local")

# Create necessary directories
os.makedirs("company", exist_ok=True)
os.makedirs("user-database", exist_ok=True)

def load_zerodha_company_info():
    company_file = "company/zerodha_info.json"
    
    if not os.path.exists(company_file):
        zerodha_data = {
            "company": "Zerodha",
            "description": "Zerodha is India's largest stock brokerage platform, offering discount trading services for equity, derivatives, mutual funds and more.",
            "products": {
                "Daily Savings": "Not applicable; users invest instead",
                "Digital Gold": "Buy/sell digital gold via GoldRush partner",
                "zerodha App": "Kite app for trading and Coin app for mutual funds",
                "Auto-Save": "Automated SIPs available for mutual funds"
            },
            "pricing": {
                "Account Opening": "Free during offers; small charge otherwise",
                "Savings": "Mutual fund investing via Coin is free",
                "Digital Gold Purchase": "Standard partner fees apply",
                "Gold Storage": "Vaulting fees included in partner costs",
                "Withdrawal": "No charges for selling gold; trading brokerage applies"
            },
            "faq": [
                {
                    "question": "What is Zerodha?",
                    "answer": "Zerodha is India's leading discount broker offering low-cost trading and investment services."
                },
                {
                    "question": "How does Zerodha work?",
                    "answer": "Users open an account, add funds and trade using the Kite platform."
                },
                {
                    "question": "Is there any minimum amount to start?",
                    "answer": "No minimum amount required. Start with any value allowed by the market."
                },
                {
                    "question": "How much does Zerodha cost?",
                    "answer": "Equity delivery is free; intraday and F&O trades cost ₹20/order or 0.03%."
                },
                {
                    "question": "Is my money safe with Zerodha?",
                    "answer": "Yes, Zerodha is SEBI-registered and all securities are safely held in NSDL/CDSL."
                },
                {
                    "question": "Can I withdraw money anytime?",
                    "answer": "Yes, withdrawals can be initiated via Console and credited in standard timelines."
                },
                {
                    "question": "What is digital gold?",
                    "answer": "Digital gold is 24K gold stored in secure vaults, purchasable via Zerodha's GoldRush partner."
                },
                {
                    "question": "Do you have a mobile app?",
                    "answer": "Yes, Zerodha offers the Kite app for trading and Coin app for mutual funds."
                }
            ]
        }
        
        with open(company_file, 'w') as f:
            json.dump(zerodha_data, f, indent=2)
    
    with open(company_file, 'r') as f:
        return json.load(f)


def save_lead_info(lead_data):
    """Save lead information to user-database folder"""
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"user-database/lead_{timestamp}.json"
        
        with open(filename, 'w') as f:
            json.dump(lead_data, f, indent=2)
        
        logger.info(f"Lead saved to: {filename}")
        return filename
    except Exception as e:
        logger.error(f"Error saving lead: {e}")
        return None

class ZerodhaSDRAgent(Agent):
    def __init__(self):
        # Load company information from file
        self.company_info = load_zerodha_company_info()
        if not self.company_info:
            raise Exception("Failed to load company information")
            
        self.lead_data = {
            "name": "",
            "email": "",
            "phone": "",
            "company": "",
            "role": "",
            "saving_habits": "",
            "monthly_capacity": "",
            "saving_goal": "",
            "timeline": "",
            "conversation_summary": "",
            "timestamp": datetime.now().isoformat()
        }
        self.conversation_state = "greeting"
        self.lead_complete = False
        
        # SDR instructions - include initial greeting in instructions
        instructions  = """You are glass, a friendly and knowledgeable Sales Development Representative for Zerodha, India's leading discount brokerage platform.

        IMPORTANT: You MUST start the conversation with this exact greeting:
        "Hello! I'm glass, your Zerodha investment consultant. Welcome! I'm here to help you start your investing journey. What brings you here today?"

        After the greeting, follow this conversation flow:
        1. Understand their investment needs and goals
        2. Answer questions about Zerodha using ONLY the FAQ information provided
        3. Naturally collect lead information during the conversation
        4. End with a warm summary when they indicate they're done

        LEAD INFORMATION TO COLLECT (ask naturally during conversation):
        - Name
        - Email address  
        - Current investing habits (none/irregular/regular)
        - Monthly investing capacity
        - Primary investment goal (wealth creation/trading/mutual funds/other)
        - Timeline to start

        RULES:
        - Always be warm, encouraging, and patient
        - Only answer questions using the provided FAQ - never make up information
        - If you don't know something, be honest and offer to connect them with specialists
        - Keep responses conversational and friendly
        - End calls gracefully when user says goodbye or indicates they're done

        ABOUT ZERODHA:
        {company_description}

        FAQ FOR ANSWERS:
        {faq_data}
        """

        
        # Format instructions
        faq_text = "\n".join([f"Q: {item['question']}\nA: {item['answer']}" for item in self.company_info['faq']])
        formatted_instructions = instructions.format(
            company_description=self.company_info['description'],
            faq_data=faq_text
        )
        
        super().__init__(instructions=formatted_instructions)

    @function_tool
    async def update_lead_info(self, context: RunContext, field: str, value: str) -> str:
        """Update lead information with user-provided data"""
        valid_fields = ["name", "email", "phone", "company", "role", "saving_habits", "monthly_capacity", "saving_goal", "timeline"]
        
        if field not in valid_fields:
            return f"Invalid field. Please use one of: {', '.join(valid_fields)}"
        
        self.lead_data[field] = value
        logger.info(f"Updated lead field '{field}': {value}")
        
        return f"Thank you, I've noted that down."

    @function_tool
    async def search_faq(self, context: RunContext, question: str) -> str:
        """Search FAQ for relevant answers to user questions"""
        question_lower = question.lower()
        
        # Simple keyword matching
        for faq_item in self.company_info['faq']:
            faq_question_lower = faq_item['question'].lower()
            # Check for direct matches
            if any(keyword in question_lower for keyword in faq_question_lower.split()[:3]):
                return faq_item['answer']
        
        # Check common question patterns
        if "what is zerodha" in question_lower:
            return self.company_info['faq'][0]['answer']
        elif "how does" in question_lower and "work" in question_lower:
            return self.company_info['faq'][1]['answer']
        elif "minimum" in question_lower or "start" in question_lower:
            return self.company_info['faq'][2]['answer']
        elif "cost" in question_lower or "price" in question_lower or "free" in question_lower:
            return self.company_info['faq'][3]['answer']
        elif "safe" in question_lower or "secure" in question_lower:
            return self.company_info['faq'][4]['answer']
        elif "withdraw" in question_lower or "redeem" in question_lower:
            return self.company_info['faq'][5]['answer']
        elif "digital gold" in question_lower:
            return self.company_info['faq'][6]['answer']
        elif "app" in question_lower or "mobile" in question_lower:
            return self.company_info['faq'][7]['answer']
        
        return "That's a great question! I'd be happy to connect you with our specialist team who can provide more detailed information about that."

    @function_tool
    async def end_conversation(self, context: RunContext) -> str:
        """End the conversation and save lead information"""
        self.lead_complete = True
        
        # Create summary
        summary = f"Conversation about {self.lead_data['saving_goal'] or 'saving goals'}. Current habits: {self.lead_data['saving_habits'] or 'not specified'}. Timeline: {self.lead_data['timeline'] or 'not specified'}."
        self.lead_data["conversation_summary"] = summary
        
        # Save lead to database
        filename = save_lead_info(self.lead_data)
        
        return f"""Thank you for your time! Here's a quick summary:

{summary}

I'll make sure you receive all the information about starting your saving journey with zerodha. Have a wonderful day!"""

def prewarm(proc: JobProcess):
    """Preload models and company data"""
    logger.info("Prewarming agent...")
    proc.userdata["vad"] = silero.VAD.load()
    # Preload company data
    company_info = load_zerodha_company_info()
    if company_info:
        logger.info("Company data loaded successfully during prewarm")
    else:
        logger.error("Failed to load company data during prewarm")

async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {
        "room": ctx.room.name,
        "agent": "zerodha-sdr"
    }
    
    logger.info("Starting zerodha SDR agent session...")
    
    try:
        # Initialize zerodha SDR agent
        zerodha_agent = ZerodhaSDRAgent()
        logger.info("zerodha SDR agent initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize agent: {e}")
        return

    # Set up voice AI pipeline with Male voice
    session = AgentSession(
        stt=deepgram.STT(model="nova-2"),
        llm=google.LLM(
            model="gemini-2.0-flash",
        ),
        tts=murf.TTS(
            voice="en-US-matthew",  # male voice
            style="Conversation",
            tokenizer=tokenize.basic.SentenceTokenizer(min_sentence_len=2),
            text_pacing=True
        ),
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
    )

    # Add event listeners for debugging
    @session.on("user_speech")
    def on_user_speech(transcript: str):
        logger.info(f"User said: {transcript}")

    @session.on("agent_speech") 
    def on_agent_speech(transcript: str):
        logger.info(f"Agent responding: {transcript}")

    # Metrics collection
    usage_collector = metrics.UsageCollector()
    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)
    
    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Final usage summary: {summary}")
    ctx.add_shutdown_callback(log_usage)

    try:
        # Start the session
        await session.start(
            agent=zerodha_agent,
            room=ctx.room,
            room_input_options=RoomInputOptions(
                noise_cancellation=noise_cancellation.BVC(),
            ),
        )
        logger.info("Agent session started successfully")
        
        # Join the room and connect to the user
        await ctx.connect()
        logger.info("Connected to room successfully")
        
    except Exception as e:
        logger.error(f"Error during session: {e}")
        raise

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))