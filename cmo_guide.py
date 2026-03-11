import os
import json
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from crewai import Agent, Task, Crew, Process, LLM
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# Fetch Secrets
api_key = os.environ.get("GEMINI_API_KEY")
sender_email = os.environ.get("SENDER_EMAIL")
sender_password = os.environ.get("SENDER_PASSWORD")
receiver_email = os.environ.get("RECEIVER_EMAIL")

# 1. Authenticate the CMO Robot
try:
    print("🔐 Authenticating JomPlan CMO with Google Cloud...")
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    # NOTE: Using the new CMO-specific secret here!
    creds_dict = json.loads(os.environ.get("CMO_GOOGLE_CREDENTIALS_JSON"))
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
except Exception as e:
    print(f"❌ Authentication Failed: {e}")
    exit(1)

# 2. Fetch Both Datasets Securely
try:
    print("📥 Downloading secure data for CMO...")
    
    # --- A. JOMPLAN USER DATA ---
    jomplan_sheet_id = "1WctigP3KR7NB7rGQJ3RtZNAJCcvWeeYsBLd52Osfirg" 
    jp_sheet = client.open_by_key(jomplan_sheet_id).sheet1
    jp_data = jp_sheet.get_all_records(head=2)
    df_users = pd.DataFrame(jp_data)
    df_users.columns = df_users.columns.str.strip()
    df_users['Timestamp'] = pd.to_datetime(df_users['Timestamp'], dayfirst=True, errors='coerce')
    recent_users = df_users[df_users['Timestamp'] >= (pd.Timestamp.now() - pd.Timedelta(days=7))].to_dict(orient='records')
    
    # --- B. MARKETING TRACKER DATA ---
    marketing_sheet_id = "1RNbPf4BLNmwq3p2lBYu7EaOTeK5VDGLECm-9GRWBy1E"
    mkt_sheet = client.open_by_key(marketing_sheet_id).sheet1
    mkt_data = mkt_sheet.get_all_records(head=1) 
    df_tracker = pd.DataFrame(mkt_data)
    tracker_data = df_tracker.tail(20).to_dict(orient='records')
    
except Exception as e:
    print(f"❌ Failed to read secure data: {e}")
    exit(1)

# 3. Configure the Brain
pro_llm = LLM(model="gemini/gemini-3.1-pro-preview", api_key=api_key)

# 4. Define Workforce
cmo = Agent(
    role="Chief Marketing Officer & Beginner Marketing Coach",
    goal="Guide a founder from zero marketing experience to a fully operational social media engine, adapting based on their progress in the tracker.",
    backstory="""You are the CMO of Jom-Plan, but you specialize in teaching non-marketers. Your job is twofold:
    1. Accountability Coach: Read the Marketing Tracker. You must assess the human's stage. If they are just starting, you act as a 101 guide, teaching them the absolute basics of setting up pages step-by-step.
    2. Strategist: Once the tracker shows their foundational setup is 'Done', you shift to data-driven content strategy, analyzing user trends to suggest specific posts.
    Always explain the 'why' and the 'how' in simple, transferable terms without jargon.""",
    llm=pro_llm
)

# 5. Define Tasks
marketing_task = Task(
    description=f"""Review the Human's recent marketing progress:\n{tracker_data}\n
    Review the recent Jom-Plan user trends:\n{recent_users}\n
    
    Write a twice-a-week sync email to the human founder.
    RULES:
    1. Output strictly in HTML (use <h2>, <h3>, <ul>, <li>, <b>). DO NOT use markdown.
    2. Section 1: <h2>📊 Accountability Review</h2>. Address the human. Acknowledge what they completed and respond to their 'Human Notes'.
    3. EVALUATE THEIR STAGE:
       - If the tracker is empty, OR if foundational tasks (like creating an IG/TikTok account, writing a bio, or linking a website) are NOT marked 'Done', proceed to PHASE 1.
       - If foundational tasks ARE marked 'Done', proceed to PHASE 2.
    4. Section 2: <h2>🎯 The Next 3 Steps</h2>.
       - IF PHASE 1 (Foundations): Ignore the user data trends for now. Assign 3 basic setup tasks (e.g., Task 1: Create an Instagram Professional Account. Task 2: Write a High-Converting Bio. Task 3: Set up a Link in Bio). For each task, break down the exact step-by-step instructions on *how* to do it, and explain *why* it matters.
       - IF PHASE 2 (Content Execution): Analyze the user trends. Give a brief summary of the insights, then assign 3 specific social media posts (Platform, Vibe/Visual, Caption, Hashtags).
    5. Section 3: <h2>📝 Tracker Update Reminder</h2>. Remind the human to copy these 3 tasks into their Google Sheet Tracker and update the status when done.""",
    expected_output="An HTML email containing an accountability review, and either foundational setup guides (if beginning) or data-driven content tasks (if foundations are done).",
    agent=cmo
)

# 6. Run the Crew
jom_plan_crew = Crew(agents=[cmo], tasks=[marketing_task], process=Process.sequential)
result = jom_plan_crew.kickoff()

# 7. Send the Email
try:
    msg = MIMEMultipart()
    msg['From'] = f"Jom-Plan CMO <{sender_email}>" 
    msg['To'] = receiver_email
    msg['Subject'] = "📈 Your Jom-Plan Marketing Sync & Next Steps"

    body = f"""
    <html>
      <body style="font-family: Arial, sans-serif; color: #333; max-width: 800px; margin: auto;">
        <h1 style="color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px;">CMO Strategy Sync</h1>
        {result.raw}
      </body>
    </html>
    """
    msg.attach(MIMEText(body, 'html'))

    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    server.login(sender_email, sender_password) 
    server.sendmail(sender_email, receiver_email, msg.as_string()) 
    server.quit()
    print("✅ CMO Sync Email sent!")
except Exception as e:
    print(f"❌ Failed to send email: {e}")
