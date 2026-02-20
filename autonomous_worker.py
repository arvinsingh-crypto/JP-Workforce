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
    goal="Identify the single most critical app bug from the feedback, explain the technical root cause, and write the exact Replit Python code to fix it.",
    backstory="You are a senior Replit developer. You don't write generic advice; you write actual, deployable Python code. You focus on solving one critical problem at a time perfectly.",
    llm=pro_llm
)

ceo = Agent(
    role="Operations Director",
    goal="Translate the engineer's technical fix into a ready-to-use natural language prompt for the Replit AI Agent.",
    backstory="You are a ruthless, efficient Operations Director. You know the human founder is not a coder and relies entirely on the Replit AI Agent to build Jom-Plan. Instead of giving the founder raw Python code that they won't know how to use, your job is to write the exact, comprehensive instruction prompt the founder should copy and paste into the Replit AI chat to implement the Engineer's fix.",
    llm=pro_llm
)

# 5. Define Tasks
engineering_task = Task(
    description=f"Review this feedback:\n\n{feedback_data}\n\n1. Identify the ONE most critical bug.\n2. Write a detailed technical summary of WHY it is happening.\n3. Write the exact Python code or Replit bash commands needed to fix it. \nNOTE: Output strictly in HTML (using <p>, <b>, and <pre> tags). DO NOT use Markdown.",
    expected_output="An HTML-formatted technical report with the bug cause and the raw code block to fix it.",
    agent=engineer
)

ceo_task = Task(
    description="Read the Engineer's fix. Draft an email to the Human Founder.\nRULES:\n1. Output strictly in valid HTML format (use <h2>, <ul>, <li>, <b>, <pre> tags). DO NOT use Markdown asterisks.\n2. Section 1: <h2>Executive Summary</h2>. Exactly 3 bullet points explaining the bug and its business impact.\n3. Section 2: <h2>Replit AI Prompt</h2>. Write a highly specific, natural language prompt that the founder can copy and paste into their Replit AI chat. This prompt must instruct the Replit AI exactly what code to write and where to put it, based entirely on the Engineer's technical solution. Place this prompt inside a <pre style='background-color: #eee; padding: 10px; white-space: pre-wrap;'> tag so it is easy to copy.",
    expected_output="A short HTML email with a 3-bullet summary and a copy-pasteable prompt for the Replit AI Agent.",
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
