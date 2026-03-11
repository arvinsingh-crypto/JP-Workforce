import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from crewai import Agent, Task, Crew, Process, LLM
from crewai_tools import SerperDevTool
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import pandas as pd

# Fetch Secrets
api_key = os.environ.get("GEMINI_API_KEY")
serper_key = os.environ.get("SERPER_API_KEY")
sender_email = os.environ.get("SENDER_EMAIL")
sender_password = os.environ.get("SENDER_PASSWORD")
receiver_email = os.environ.get("RECEIVER_EMAIL")

os.environ["SERPER_API_KEY"] = serper_key

# 1. Authenticate with Google Cloud
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
sales_sheet_id = "YOUR_SALES_SPREADSHEET_ID_HERE" 
sheet = client.open_by_key(sales_sheet_id).sheet1
records = sheet.get_all_records()

pro_llm = LLM(model="gemini/gemini-3.1-pro-preview", api_key=api_key)
search_tool = SerperDevTool()

# 3. Define the Dual-Engine Sales Team
prospector = Agent(
    role="Lead Generation Specialist",
    goal="Use Google Search to find highly relevant B2B business leads for Jom-Plan based on a broad target niche.",
    backstory="You are an expert at finding hidden gems on the internet. You search for actual, currently operating businesses, find their official websites, and summarize what they do.",
    tools=[search_tool],
    llm=pro_llm
)

sales_rep = Agent(
    role="B2B Sales Operations Specialist",
    goal="Research specific companies, assess their viability as a Jom-Plan partner, and write highly personalized cold emails.",
    backstory="You are the elite Sales Ops Lead for Jom-Plan. You deeply research a prospect before reaching out. You assess if they are a good fit (Viability), and your emails are punchy, polite, and strictly focused on solving their specific problems.",
    tools=[search_tool],
    llm=pro_llm
)

drafted_count = 0
found_leads_count = 0

print("🔍 Scanning CRM for Tasks...")

# 4. Loop through the CRM
for index, row in enumerate(records, start=2):
    status = str(row.get('Status', '')).strip().lower()
    lead_name = str(row.get('Lead Name or Niche', ''))
    context = str(row.get('Website or Context', ''))
    
    # --- ENGINE A: THE HUNTER (Prospecting for a niche) ---
    if status == 'prospect':
        print(f"🕵️‍♂️ Prospecting new leads for: {lead_name}")
        
        prospect_task = Task(
            description=f"""Search the web for 3 real businesses that match this niche: '{lead_name}' in the location/context: '{context}'.
            For each business, find their official website.
            RULES: You MUST format your exact output as 3 distinct lines, separated by a pipe (|), like this:
            [Company Name] | [Website URL] | [1-sentence description of what they do]""",
            expected_output="3 lines of text, each containing Company | URL | Description.",
            agent=prospector
        )
        
        crew = Crew(agents=[prospector], tasks=[prospect_task], process=Process.sequential)
        result = crew.kickoff()
        
        new_rows = []
        for line in result.raw.split('\n'):
            if '|' in line:
                parts = line.split('|')
                if len(parts) >= 2:
                    new_company = parts[0].strip()
                    new_context = parts[1].strip() + " - " + parts[2].strip() if len(parts) > 2 else parts[1].strip()
                    new_rows.append([new_company, new_context, "New", "", ""])
        
        if new_rows:
            sheet.append_rows(new_rows)
            sheet.update_cell(index, 3, "Prospecting Complete")
            found_leads_count += len(new_rows)
            print(f"✅ Found {len(new_rows)} new leads for {lead_name}!")

    # --- ENGINE B: THE SNIPER (Researching & Drafting a specific company) ---
    elif status == 'new':
        print(f"⚙️ Researching & Drafting Email for: {lead_name}")
        
        lead_task = Task(
            description=f"""Use Google Search to research this specific company: '{lead_name}' (Context/Website: {context}).
            1. Assess their Viability: Would they benefit from Jom-Plan (an app for personalized travel itineraries)? Why?
            2. Draft a professional, personalized cold email to them offering a partnership or software integration based on your research.
            
            RULES: Format exactly like this:
            Viability Assessment: [1 paragraph analyzing why they are a good/bad fit for Jom-Plan]
            |||
            Subject: [Your Subject Line]
            Hi [Name or Team],
            [Body of email tailored to your research]
            Best,
            Jom-Plan Team""",
            expected_output="Viability assessment and an email draft separated by |||",
            agent=sales_rep
        )
        
        crew = Crew(agents=[sales_rep], tasks=[lead_task], process=Process.sequential)
        result = crew.kickoff()
        
        try:
            output_parts = result.raw.split('|||')
            viability_details = output_parts[0].strip() if len(output_parts) > 0 else "Research failed."
            drafted_email = output_parts[1].strip() if len(output_parts) > 1 else result.raw
            
            sheet.update_cell(index, 3, "Drafted")
            sheet.update_cell(index, 4, viability_details)
            sheet.update_cell(index, 5, drafted_email)
            drafted_count += 1
            print(f"✅ Successfully researched and drafted email for {lead_name}.")
        except Exception as e:
            print(f"⚠️ Failed to update row for {lead_name}: {e}")

# 5. Notify the Founder
if drafted_count > 0 or found_leads_count > 0:
    try:
        primary_email = receiver_email.split(',')[0].strip()
        msg = MIMEMultipart()
        msg['From'] = f"Jom-Plan Sales Ops <{sender_email}>" 
        msg['To'] = primary_email 
        msg['Subject'] = f"✅ Sales Ops: {found_leads_count} Leads Found, {drafted_count} Drafted"

        body = f"""
        <html>
          <body style="font-family: Arial, sans-serif; color: #333;">
            <h2>Sales Operations Update</h2>
            <p>I scoured the web and found <b>{found_leads_count}</b> new target businesses.</p>
            <p>I also researched viability and drafted personalized cold emails for <b>{drafted_count}</b> specific leads.</p>
            <p>Please review your CRM and approve the drafts!</p>
          </body>
        </html>
        """
        msg.attach(MIMEText(body, 'html'))
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password) 
        server.sendmail(sender_email, primary_email, msg.as_string()) 
        server.quit()
    except Exception as e:
        print(f"❌ Failed to send notification email: {e}")
