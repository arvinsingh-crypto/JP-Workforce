import os
import json
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from crewai import Agent, Task, Crew, Process, LLM
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# Fetch Secrets from GitHub
api_key = os.environ.get("GEMINI_API_KEY")
sender_email = os.environ.get("SENDER_EMAIL")
sender_password = os.environ.get("SENDER_PASSWORD")
receiver_email = os.environ.get("RECEIVER_EMAIL")

# 1. Authenticate the Robot Employee
try:
    print("🔐 Authenticating with Google Cloud...")
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = json.loads(os.environ.get("GOOGLE_CREDENTIALS_JSON"))
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
except Exception as e:
    print(f"❌ Authentication Failed: {e}")
    exit(1)

# 2. Fetch Data Securely
try:
    print("📥 Downloading SECURE data from Google Sheets...")
    
    # PUT YOUR EXACT SPREADSHEET ID HERE
    jomplan_sheet_id = "1WctigP3KR7NB7rGQJ3RtZNAJCcvWeeYsBLd52Osfirg" 
    
    # Open the sheet and grab the data (head=2 skips row 1 instructions)
    sheet = client.open_by_key(jomplan_sheet_id).sheet1
    data = sheet.get_all_records(head=2)
    
    # Convert to Pandas DataFrame
    df = pd.DataFrame(data)
    
    # SAFETY NET: This removes any accidental blank spaces in your Google Sheet column headers
    df.columns = df.columns.str.strip()
    
    # Standardize timestamps
    df['Timestamp'] = pd.to_datetime(df['Timestamp'], dayfirst=True, errors='coerce')
    
    # DATASET A: All-Time Historical Data
    all_time_data = df.tail(1000).to_dict(orient='records')
    
    # DATASET B: Last 7 Days Data
    seven_days_ago = pd.Timestamp.now() - pd.Timedelta(days=7)
    recent_df = df[df['Timestamp'] >= seven_days_ago]
    recent_data = recent_df.to_dict(orient='records')
    
    if recent_df.empty:
        print("🛑 No new user feedback in the last 7 days. Exiting to save resources.")
        exit(0)
        
    print(f"✅ Securely loaded {len(recent_data)} new entries.")
    
except Exception as e:
    print(f"❌ Failed to read secure data: {e}")
    print(f"🔍 DEBUG - The columns Python sees are: {df.columns.tolist() if 'df' in locals() else 'None'}")
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
Your job is to identify critical bugs and prevent repeating past advice.
1. Cross-reference the data. Isolate issues that are BRAND NEW (only in the last 7 days) versus PERSISTENT (occurring in both historical and recent data).
2. For BRAND NEW issues, provide the standard technical root cause and the best TypeScript/Node.js code fix.
3. For PERSISTENT issues, explicitly state that this is a recurring problem. Assume your previous standard recommendations (e.g., basic Haversine filtering, standard intent extraction) have either failed or are insufficient. You MUST brainstorm and provide a completely NEW, advanced, or alternative architectural approach to solve it.
NOTE: Output strictly in HTML (using <h2>, <h3>, <p>, <b>, and <pre> tags). Categorize your report clearly into "Brand New Issues" and "Persistent Issues". DO NOT use Markdown.""",
    expected_output="An HTML technical report categorizing bugs into New vs. Persistent, providing standard fixes for new bugs and advanced/alternative fixes for recurring ones.",
    agent=engineer
)

ceo_task = Task(
    description=f"""You have three jobs.

First, analyze the data for business intelligence:
HISTORICAL DATA:\n{all_time_data}
RECENT DATA:\n{recent_data}

Second, read the Engineer's technical report. Pay special attention to their categorization of "Brand New" vs "Persistent" issues.
Third, identify proactive feature suggestions based on user desires.

Draft an email to the Human Founder.
RULES:
1. Output strictly in valid HTML format (use <h2>, <h3>, <ul>, <li>, <b>, <pre> tags). DO NOT use Markdown asterisks.
2. Section 1: <h2>📈 Growth & Usage Trends</h2>. Compare recent 7-day data against historical data.
3. Section 2: <h2>🗺️ Location & Market Trends</h2>. Note any new locations trending.
4. Section 3: <h2>⚠️ Critical Friction Points (Timeline Analysis)</h2>. Detail the top issues based on the Engineer's report. You MUST clearly highlight if an issue is a "New Fire" from this week, or a "Persistent Issue" that is still happening despite past efforts. 
5. Section 4: <h2>🛠️ Replit Session Plans (Action Required)</h2>. For EACH bug, write a highly specific "Session Plan" prompt for the Replit AI. For "Persistent Issues," ensure the Session Plan explicitly commands the Replit AI to try the Engineer's *new, alternative* solution rather than the standard fix. Place each prompt inside a <pre style='background-color: #eee; padding: 10px; white-space: pre-wrap; font-family: monospace; margin-bottom: 15px;'> tag.
6. Section 5: <h2>💡 Proactive Product Suggestions</h2>. Based on the user data, suggest 2-3 new features or UX enhancements to build next.
""",
    expected_output="An HTML email containing business trends, a timeline-aware friction analysis, Replit Session Plans (with alternative solutions for recurring bugs), and proactive product suggestions.",
    agent=ceo
)

# 6. Run the Crew
print("🧠 The C-Suite is analyzing the data...")
jom_plan_crew = Crew(agents=[engineer, ceo], tasks=[engineering_task, ceo_task], process=Process.sequential)
result = jom_plan_crew.kickoff()

# 7. Send the Email
try:
    # Look at the list, but ONLY grab the first email address (index 0)
    primary_email = receiver_email.split(',')[0].strip()
    
    msg = MIMEMultipart()
    msg['From'] = f"Jom-Plan AI C-Suite <{sender_email}>" 
    
    # Send it strictly to you
    msg['To'] = primary_email 
    msg['Subject'] = "⚙️ Jom-Plan Weekly Engineering & Executive Report"

    body = f"""
    <html>
      <body style="font-family: Arial, sans-serif; color: #333; max-width: 800px; margin: auto;">
        <h1 style="color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px;">Executive Summary</h1>
        {result.raw}
      </body>
    </html>
    """
    msg.attach(MIMEText(body, 'html'))

    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    server.login(sender_email, sender_password) 
    
    # Tell the server to email ONLY the primary founder
    server.sendmail(sender_email, primary_email, msg.as_string()) 
    server.quit()
    print(f"✅ Executive Report sent successfully ONLY to: {primary_email}")
except Exception as e:
    print(f"❌ Failed to send email: {e}")
