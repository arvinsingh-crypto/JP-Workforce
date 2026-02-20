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

# 2. Fetch the data
try:
    print("📥 Downloading latest data from Google Sheets...")
    df = pd.read_csv(google_sheet_url).tail(50)
    feedback_data = df.to_dict(orient='records')
except Exception as e:
    print(f"❌ Failed to read data: {e}")
    exit(1)

# 3. Configure the Brain
pro_llm = LLM(model="gemini/gemini-3.1-pro-preview", api_key=api_key)

# 4. Define Workforce
engineer = Agent(
    role="Lead Systems Engineer",
    goal="Analyze raw user feedback data, identify the most critical systemic issues, and propose Replit-compatible technical roadmaps.",
    backstory="You are a senior technical architect for Jom-Plan. You know the tech stack is hosted on Replit using Python.",
    llm=pro_llm
)

ceo = Agent(
    role="Chief Executive Officer",
    goal="Translate technical realities into strategic shareholder recommendations.",
    backstory="You are the visionary CEO of Jom-Plan. You take technical reports from your engineer and decide which fixes make the most business sense.",
    llm=pro_llm
)

# 5. Define Tasks
engineering_task = Task(
    description=f"Analyze this live dataset of Jom-Plan user feedback:\n\n{feedback_data}\n\nCategorize the feedback to find the top systemic issue. Provide a step-by-step technical execution plan for a Replit environment.",
    expected_output="A structured Consolidated Technical Review with proposed Replit-specific technical solutions.",
    agent=engineer
)

ceo_task = Task(
    description="Read the Engineer's Technical Review. Draft a formal memorandum to the Jom-Plan Shareholders recommending which fixes we should prioritize.",
    expected_output="A formal, professional Shareholder Memorandum.",
    agent=ceo
)

# 6. Run the Crew
print("🧠 The C-Suite is analyzing the data...")
jom_plan_crew = Crew(agents=[engineer, ceo], tasks=[engineering_task, ceo_task], process=Process.sequential)
result = jom_plan_crew.kickoff()

# --- NEW: STEP 7. THE EMAIL SENDER ---
print("📧 Drafting and sending the email to shareholders...")

try:
    # Construct the email structure
    msg = MIMEMultipart()
    
    # HARDCODE THE ALIAS HERE (This is what the recipient sees)
    msg['From'] = "Jom-Plan CEO <jomplanCEO@outsourcee.co>" 
    msg['To'] = receiver_email
    msg['Subject'] = "🚀 Jom-Plan Executive Update: Weekly Technical Report"

    # Attach the AI's raw output
    body = f"Please find the latest automated C-Suite report below:\n\n{result.raw}"
    msg.attach(MIMEText(body, 'plain'))

    # Connect to Gmail's server and send
    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    
    # 1. Login using your MAIN account (arvin.singh@...)
    server.login(sender_email, sender_password) 
    text = msg.as_string()
    
    # 2. Send the email disguised as the ALIAS
    server.sendmail("jomplanCEO@outsourcee.co", receiver_email, text) 
    server.quit()
    
    print("✅ Email successfully sent to inbox!")

except Exception as e:
    print(f"❌ Failed to send email. Error: {e}")

print("\n✅ Process Complete!")
