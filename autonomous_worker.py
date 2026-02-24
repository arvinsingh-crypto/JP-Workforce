import os
import pandas as pd
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from crewai import Agent, Task, Crew, Process, LLM

# 1. Securely fetch ALL keys from GitHub Secrets
api_key = os.environ.get("GEMINI_API_KEY")
sender_email = os.environ.get("SENDER_EMAIL")
sender_password = os.environ.get("SENDER_PASSWORD")
receiver_email = os.environ.get("RECEIVER_EMAIL")

google_sheet_url = "https://docs.google.com/spreadsheets/d/1WctigP3KR7NB7rGQJ3RtZNAJCcvWeeYsBLd52Osfirg/export?format=csv&gid=0"

print("🤖 Waking up the Jom-Plan Autonomous Worker...")

# 2. Fetch and Segment the data
try:
    print("📥 Downloading data from Google Sheets...")
    
    # ADDED header=1 to skip the instruction row and read the true column names
    df = pd.read_csv(google_sheet_url, header=1)
    
    # Drop any completely empty rows that might cause errors
    df = df.dropna(how='all')
    
    # Standardize the timestamps
    df['Timestamp'] = pd.to_datetime(df['Timestamp'], dayfirst=True, errors='coerce')
    
    # DATASET A: All-Time Historical Data (Capped at 1000 rows to ensure fast processing)
    all_time_data = df.tail(1000).to_dict(orient='records')
    
    # DATASET B: Last 7 Days Data
    seven_days_ago = pd.Timestamp.now() - pd.Timedelta(days=7)
    recent_df = df[df['Timestamp'] >= seven_days_ago]
    recent_data = recent_df.to_dict(orient='records')
    
    # Safety Catch
    if recent_df.empty:
        print("🛑 No new user feedback in the last 7 days. Exiting to save resources.")
        exit(0)
        
    print(f"✅ Loaded {len(recent_data)} new entries for this week, and {len(all_time_data)} historical entries.")
    
except Exception as e:
    print(f"❌ Failed to read data: {e}")
    exit(1)

# 3. Configure the Brain
pro_llm = LLM(model="gemini/gemini-3.1-pro-preview", api_key=api_key)

# 4. Define Workforce
engineer = Agent(
    role="Lead Full-Stack TypeScript Engineer",
    goal="Identify all critical app bugs from the feedback, explain their technical root causes, and write the exact TypeScript/React/Express architectural fixes.",
    backstory="""You are the Lead Full-Stack Engineer for JomPlan.
    CRITICAL ARCHITECTURE RULES:
    - Full-stack TypeScript web app.
    - Frontend: React 18, Vite, Tailwind CSS, shadcn/ui, Wouter routing.
    - Backend: Express API with Drizzle ORM on PostgreSQL (Neon-backed).
    - Auth: Replit OIDC.
    - AI Pipeline: User message -> GPT-4o-mini intent extraction -> Google Places API discovery -> Haversine distance filtering (1.5km walking / 8km default) -> top 5 places injected into GPT prompt -> structured JSON itinerary response.
    You write deployable TypeScript code, database schemas, and architectural solutions that perfectly fit this exact stack. You handle multi-file refactors with consistency.""",
    llm=pro_llm
)

ceo = Agent(
    role="Operations Director & CEO",
    goal="Analyze business trends, provide comprehensive 'Session Plan' Replit prompts for all critical issues, and offer proactive product suggestions.",
    backstory="You are a strategic CEO. You analyze user chat logs to identify all major friction points and proactive feature opportunities. You take the Engineer's fixes and translate them into highly specific 'Session Plan' prompts designed specifically for the Replit AI agent. You know Replit responds best to specific scopes, file references, and strict acceptance criteria.",
    llm=pro_llm
)

# 5. Define Tasks
engineering_task = Task(
    description=f"""Review the RECENT 7-day feedback:\n{recent_data}\n\nAnd the HISTORICAL context:\n{all_time_data}\n
1. Identify ALL critical bugs or systemic friction points currently affecting users.
2. For EACH issue, write a detailed technical summary of the root cause based on our React/Express/PostgreSQL/Google Places architecture.
3. For EACH issue, write the exact TypeScript code, Drizzle ORM schema changes, or UI component logic needed to fix it.
NOTE: Output strictly in HTML (using <h2>, <h3>, <p>, <b>, and <pre> tags). DO NOT use Markdown.""",
    expected_output="An HTML-formatted technical report detailing the root causes and raw TypeScript code fixes for ALL identified critical issues.",
    agent=engineer
)

ceo_task = Task(
    description=f"""You have three jobs.

First, analyze the data for business intelligence:
HISTORICAL DATA:\n{all_time_data}
RECENT DATA:\n{recent_data}

Second, read the Engineer's technical fixes for ALL critical issues.
Third, identify proactive feature suggestions based on user desires.

Draft an email to the Human Founder.
RULES:
1. Output strictly in valid HTML format (use <h2>, <h3>, <ul>, <li>, <b>, <pre> tags). DO NOT use Markdown asterisks.
2. Section 1: <h2>📈 Growth & Usage Trends</h2>. Compare recent 7-day data against historical data.
3. Section 2: <h2>🗺️ Location & Market Trends</h2>. Note any new locations trending.
4. Section 3: <h2>⚠️ Critical Friction Points</h2>. Detail ALL top issues based on recent chat logs.
5. Section 4: <h2>🛠️ Replit Session Plans (Action Required)</h2>. For EACH bug identified by the Engineer, write a highly specific "Session Plan" prompt for the Replit AI. Each prompt must include:
   - Specific scope (what to change and where)
   - Acceptance criteria ("when X happens, Y should be the result")
   - Constraints ("keep backward compatible", "don't break existing UI").
   Place EACH Session Plan prompt inside its own <pre style='background-color: #eee; padding: 10px; white-space: pre-wrap; font-family: monospace; margin-bottom: 15px;'> tag so the founder can copy and paste them sequentially.
6. Section 5: <h2>💡 Proactive Product Suggestions</h2>. Based on the user data, suggest 2-3 new features, data pipeline improvements, or UX enhancements the team should build next to delight users.
""",
    expected_output="An HTML email containing business trends, multiple detailed Replit Session Plan prompts for all bugs, and proactive product suggestions.",
    agent=ceo
)

# 6. Run the Crew
print("🧠 The C-Suite is analyzing the data...")
jom_plan_crew = Crew(agents=[engineer, ceo], tasks=[engineering_task, ceo_task], process=Process.sequential)
result = jom_plan_crew.kickoff()

# --- NEW: STEP 7. THE EMAIL SENDER ---
print("📧 Drafting and sending the email to the Founder...")

try:
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    import smtplib

    # Construct the email structure
    msg = MIMEMultipart()
    
    # HARDCODE THE ALIAS HERE (This is what the recipient sees)
    msg['From'] = "Jom-Plan CEO <jomplanCEO@outsourcee.co>" 
    msg['To'] = receiver_email
    msg['Subject'] = "🚀 Jom-Plan Operations Brief: Critical Fixes"

    # Grab the Engineer's isolated report to put in the appendix
    engineer_report = engineering_task.output.raw

    # Construct the beautifully formatted HTML email body
    body = f"""
    <html>
      <body style="font-family: Arial, sans-serif; color: #333; line-height: 1.6; max-width: 800px; margin: auto;">
        
        <h1 style="color: #0056b3; border-bottom: 2px solid #0056b3; padding-bottom: 10px;">Jom-Plan Operations Brief</h1>
        {result.raw}
        
        <br><br>
        
        <div style="background-color: #f8f9fa; border-left: 4px solid #6c757d; padding: 20px; margin-top: 30px;">
            <h3 style="color: #495057; margin-top: 0;">🔬 Technical Appendix: Engineering Deep-Dive</h3>
            <p style="font-size: 0.9em; color: #666;">The following is the raw, detailed diagnostic report provided by the Lead Systems Engineer for your review:</p>
            <div style="font-size: 0.95em;">
                {engineer_report}
            </div>
        </div>
        
      </body>
    </html>
    """
    
    # Attach the HTML body (Notice it says 'html' now, not 'plain')
    msg.attach(MIMEText(body, 'html'))

    # Connect to Gmail's server and send
    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    
    # Login using your MAIN account (arvin.singh@...)
    server.login(sender_email, sender_password) 
    text = msg.as_string()
    
    # Send the email disguised as the ALIAS
    server.sendmail("jomplanCEO@outsourcee.co", receiver_email, text) 
    server.quit()
    
    print("✅ HTML Email successfully sent to inbox!")

except Exception as e:
    print(f"❌ Failed to send email. Error: {e}")

print("\n✅ Process Complete!")
