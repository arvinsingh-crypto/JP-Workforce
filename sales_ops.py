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
sales_sheet_id = "1J0Xy0tBC0-Tp7o-PAQL5F5eMdaAqSjcYQzA0jR2yrus" 
sheet = client.open_by_key(sales_sheet_id).sheet1
records = sheet.get_all_records()

pro_llm = LLM(model="gemini/gemini-3.1-pro-preview", api_key=api_key)
search_tool = SerperDevTool()

# 3. Define the Level 2 Sales Team
prospector = Agent(
    role="Lead Generation Specialist",
    goal="Find actual, literal businesses that perfectly match the human's requested niche.",
    backstory="You are a ruthless, highly literal internet researcher. You never assume or guess. If asked for 'Hotels', you find literal buildings where people sleep.",
    tools=[search_tool],
    llm=pro_llm
)

sales_rep = Agent(
    role="Senior B2B Sales SDR",
    goal="Research companies, find the exact decision-maker (GM, Founder, Marketing Director), and write highly personalized cold emails to them.",
    backstory="You are an elite SDR. You know that emailing 'info@' is a waste of time. You scour the web to find the actual name and role of the person in charge before drafting your highly targeted pitch.",
    tools=[search_tool],
    llm=pro_llm
)

drafted_count = 0
found_leads_count = 0

print("🔍 Scanning CRM for Tasks...")

# 4. Loop through the CRM
for index, row in enumerate(records, start=2):
    status = str(row.get('Status', '')).strip().lower()
    
    # Safely check for the column name whether you used the slash or 'or'
    lead_name = str(row.get('Lead Name / Niche', row.get('Lead Name or Niche', ''))).strip()
    context = str(row.get('Website or Location/Context', '')).strip()
    
    # --- ENGINE A: THE HUNTER (Now doing 5 at a time) ---
    if status == 'prospect':
        print(f"🕵️‍♂️ Prospecting new leads for: {lead_name}")
        
        prospect_task = Task(
            description=f"""Search the web for 5 real businesses that perfectly match this literal description: '{lead_name}'. 
            Location/Context: '{context}'. 
            
            CRITICAL RULES:
            1. BE LITERAL: You MUST return exactly the niche requested.
            2. GEOGRAPHY: If the Location/Context is blank, default your search strictly to Malaysia.
            
            Format your exact output as 5 distinct lines, separated by a pipe (|), like this:
            [Company Name] | [Website URL] | [1-sentence description of what they do]""",
            expected_output="5 lines of text, each containing Company | URL | Description.",
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
                    # Append 7 columns worth of data so the sheet formatting stays clean
                    new_rows.append([new_company, new_context, "New", "", "", "", ""])
        
        if new_rows:
            sheet.append_rows(new_rows)
            sheet.update_cell(index, 3, "Prospecting Complete")
            found_leads_count += len(new_rows)
            print(f"✅ Found {len(new_rows)} new leads for {lead_name}!")

    # --- ENGINE B: THE SNIPER (Now hunting for specific humans) ---
    elif status == 'new':
        print(f"⚙️ Researching Decision Makers & Drafting for: {lead_name}")
        
        lead_task = Task(
            description=f"""Use Google Search to deeply research this specific company: '{lead_name}' (Context/Website: {context}).
            
            1. VIABILITY: Would they benefit from Jom-Plan (a personalized travel itinerary app)? Why?
            2. FIND THE HUMAN: Search the web, their "About Us" page, or LinkedIn to find the name of the General Manager, Marketing Director, or Founder.
            3. DRAFT EMAIL: Write a professional, personalized cold email addressed directly to that specific person.
            
            CRITICAL FORMATTING RULE: You MUST format your output exactly like this with the ||| separators:
            [1 paragraph viability assessment]
            |||
            [Name and Role of the decision maker you found. If none found, write "General Manager / Team"]
            |||
            [Email address or LinkedIn profile if found. If none found, write "Not found publicly"]
            |||
            Subject: [Your Subject Line]
            Hi [Name],
            [Body of email tailored to your research]
            Best,
            Jom-Plan Team""",
            expected_output="4 sections separated exactly by |||",
            agent=sales_rep
        )
        
        crew = Crew(agents=[sales_rep], tasks=[lead_task], process=Process.sequential)
        result = crew.kickoff()
        
        try:
            output_parts = result.raw.split('|||')
            viability_details = output_parts[0].strip() if len(output_parts) > 0 else "Research failed."
            contact_name = output_parts[1].strip() if len(output_parts) > 1 else "Not found."
            contact_info = output_parts[2].strip() if len(output_parts) > 2 else "Not found."
            drafted_email = output_parts[3].strip() if len(output_parts) > 3 else "Draft failed."
            
            sheet.update_cell(index, 3, "Drafted")
            sheet.update_cell(index, 4, viability_details)
            sheet.update_cell(index, 5, contact_name)
            sheet.update_cell(index, 6, contact_info)
            sheet.update_cell(index, 7, drafted_email)
            drafted_count += 1
            print(f"✅ Successfully researched humans and drafted email for {lead_name}.")
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
            <p>I also researched decision-makers and drafted highly targeted cold emails for <b>{drafted_count}</b> specific leads.</p>
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
