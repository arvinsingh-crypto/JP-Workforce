import os
import pandas as pd
from crewai import Agent, Task, Crew, Process, LLM

# 1. Securely fetch the API key from GitHub's hidden environment variables
api_key = os.environ.get("GEMINI_API_KEY")

google_sheet_url = "https://docs.google.com/spreadsheets/d/1WctigP3KR7NB7rGQJ3RtZNAJCcvWeeYsBLd52Osfirg/export?format=csv&gid=0"

print("🤖 Waking up the Jom-Plan Autonomous Worker...")

# 2. Fetch the data
try:
    print("📥 Downloading latest data from Google Sheets...")
    df = pd.read_csv(google_sheet_url).tail(50)
    feedback_data = df.to_dict(orient='records')
except Exception as e:
    print(f"❌ Failed to read data: {e}")
    exit(1) # Stop the script if data fails

# 3. Configure the Brain
pro_llm = LLM(model="gemini/gemini-3.1-pro-preview", api_key=api_key)

# 4. Define Workforce (With Replit context)
engineer = Agent(
    role="Lead Systems Engineer",
    goal="Analyze raw user feedback data, identify the most critical systemic issues, and propose Replit-compatible technical roadmaps.",
    backstory="You are a senior technical architect for Jom-Plan. Crucially, you know that the entire Jom-Plan application is built, hosted, and deployed natively on Replit using Python. When you propose technical fixes, you must provide solutions, code snippets, and terminal commands that are specifically designed to be executed within the Replit cloud IDE environment.",
    llm=pro_llm
)

ceo = Agent(
    role="Chief Executive Officer",
    goal="Translate technical realities into strategic shareholder recommendations.",
    backstory="You are the visionary CEO of Jom-Plan. You know the tech stack is hosted on Replit, which allows for rapid, agile deployment. You take technical reports from your engineer and decide which fixes make the most business sense to present to the board of directors.",
    llm=pro_llm
)

# 5. Define Tasks
engineering_task = Task(
    description=f"Analyze the following live dataset of Jom-Plan user feedback:\n\n{feedback_data}\n\nCategorize the feedback to find the top systemic issue. Provide a step-by-step technical execution plan for it, formatted for a Replit environment.",
    expected_output="A structured Consolidated Technical Review with proposed Replit-specific technical solutions.",
    agent=engineer
)

ceo_task = Task(
    description="Read the Engineer's Consolidated Technical Review. Draft a formal memorandum to the Jom-Plan Shareholders recommending which of the engineer's fixes we should prioritize investing in.",
    expected_output="A formal, professional Shareholder Memorandum.",
    agent=ceo
)

# 6. Run the Crew
print("🧠 The C-Suite is analyzing the data...")
jom_plan_crew = Crew(agents=[engineer, ceo], tasks=[engineering_task, ceo_task], process=Process.sequential)
result = jom_plan_crew.kickoff()

# 7. Output the result to the server logs
print("\n==============================================")
print("📊 FINAL CEO SHAREHOLDER REPORT:")
print("==============================================")
print(result.raw)
print("\n✅ Process Complete!")
