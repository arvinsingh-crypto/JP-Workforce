import os
import json
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

# 1. Authenticate the Sales Robot
try:
    print("🔐 Authenticating Sales Ops with Google Cloud...")
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = json.loads(os.environ.get("SALES_GOOGLE_CREDENTIALS_JSON"))
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
except Exception as e:
    print(f"❌ Authentication Failed: {e}")
    exit(1)

# 2. Connect to the Sales CRM
sales_sheet_id = "1J0Xy0tBC0-Tp7o-PAQL5F5eMdaAqSjcYQzA0jR2yrus"
sheet = client.open_by_key(sales_sheet_id).sheet1
records = sheet.get_all_records()

pro_llm = LLM(model="gemini/gemini-3.1-pro-preview", api_key=api_key)

# 3. Define the Sales Agent
sales_rep = Agent(
    role="B2B Sales Operations Specialist",
    goal="Analyze prospective leads, extract key business value, and write highly personalized cold emails.",
    backstory="You are the elite Sales Ops Lead for Jom-Plan. You excel at looking at a company's basic information and figuring out exactly how Jom-Plan's services can provide them value. Your cold emails are punchy, polite, and strictly focused on solving the prospect's problems.",
    llm=pro_llm
)

processed_count = 0

# 4. Loop through the CRM and process "New" leads
print("🔍 Scanning CRM for New Leads...")
# Start at row 2 because row 1 is headers
for index, row in enumerate(records, start=2):
    if row.get('Status', '').strip().lower() == 'new':
        lead_name = row.get('Company / Lead Name', 'Unknown Company')
        context = row.get('Website or Context', 'No context provided')
        
        print(f"⚙️ Processing Lead: {lead_name}")
        
        # Create a specific task for this lead
        lead_task = Task(
            description=f"""Analyze the following lead:\nCompany: {lead_name}\nContext/Website: {context}\n
            1. Extract the key business details and figure out how Jom-Plan can partner with them or offer value.
            2. Draft a professional, personalized cold email to them.
            
            RULES:
            You MUST return your final output exactly in this format with the ||| separator:
            [Brief paragraph of extracted details and strategy]
            |||
            Subject: [Your Subject Line]
            Hi [Name or Team],
            [Body of email]
            Best,
            Jom-Plan Team""",
            expected_output="A two-part response separated perfectly by |||",
            agent=sales_rep
        )
        
        # Run the crew for this single lead
        crew = Crew(agents=[sales_rep], tasks=[lead_task], process=Process.sequential)
        result = crew.kickoff()
        
        # Split the output and update the Google Sheet
        try:
            output_parts = result.raw.split('|||')
            extracted_details = output_parts[0].strip() if len(output_parts) > 0 else "Failed to extract."
            drafted_email = output_parts[1].strip() if len(output_parts) > 1 else result.raw
            
            # Update Column C (Status), D (Details), E (Email)
            sheet.update_cell(index, 3, "Drafted")
            sheet.update_cell(index, 4, extracted_details)
            sheet.update_cell(index, 5, drafted_email)
            print(f"✅ Successfully drafted email for {lead_name} and updated CRM.")
            processed_count += 1
        except Exception as e:
            print(f"⚠️ Failed to update row for {lead_name}: {e}")

# 5. Notify the Founder
if processed_count > 0:
    try:
        primary_email = receiver_email.split(',')[0].strip()
        msg = MIMEMultipart()
        msg['From'] = f"Jom-Plan Sales Ops <{sender_email}>" 
        msg['To'] = primary_email 
        msg['Subject'] = f"✅ Sales Ops: {processed_count} New Leads Drafted"

        body = f"""
        <html>
          <body style="font-family: Arial, sans-serif; color: #333;">
            <h2>Sales Operations Update</h2>
            <p>I have successfully researched and drafted highly personalized cold emails for <b>{processed_count}</b> new leads.</p>
            <p>Please review the <a href="https://docs.google.com/spreadsheets/d/{sales_sheet_id}/edit">Jom-Plan Sales CRM</a>. You can tweak the drafts in Column E and send them out!</p>
          </body>
        </html>
        """
        msg.attach(MIMEText(body, 'html'))
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password) 
        server.sendmail(sender_email, primary_email, msg.as_string()) 
        server.quit()
        print("📧 Notification email sent to founder.")
    except Exception as e:
        print(f"❌ Failed to send notification email: {e}")
else:
    print("No new leads to process today.")
