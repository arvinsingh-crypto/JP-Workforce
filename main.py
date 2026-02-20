import streamlit as st
import pandas as pd
from crewai import Agent, Task, Crew, Process, LLM
import os

# --- Streamlit UI Setup ---
st.set_page_config(page_title="Jom-Plan AI Workforce", page_icon="🇲🇾", layout="centered")
st.title("🚀 Jom-Plan Executive Dashboard")
st.markdown("This dashboard connects directly to the Jom-Plan Google Sheet database to generate consolidated technical and executive reviews.")

# Secure API Key Input
api_key = st.text_input("Enter your Gemini API Key:", type="password")

# Your specific Google Sheet URL (formatted for Pandas to read as a CSV)
google_sheet_url = "https://docs.google.com/spreadsheets/d/1WctigP3KR7NB7rGQJ3RtZNAJCcvWeeYsBLd52Osfirg/export?format=csv&gid=0"

st.markdown("---")

# --- The Execution Block ---
if st.button("Generate Consolidated Report"):
    if not api_key:
        st.warning("Please enter your Gemini API Key first.")
    else:
        with st.spinner("The C-Suite is securely downloading and analyzing the Jom-Plan Database..."):
            
            # 1. Fetch the data directly from your Google Sheet
            try:
                df = pd.read_csv(google_sheet_url)
                # Convert the spreadsheet into a text format the AI can read easily
                feedback_data = df.to_string(index=False)
            except Exception as e:
                st.error("❌ Could not read the Google Sheet. Please ensure the Share settings are set to 'Anyone with the link can view'.")
                st.stop()
            
            # 2. Configure the Brain (Using the powerful Gemini 3.1 Pro model)
            os.environ["GEMINI_API_KEY"] = api_key
            pro_llm = LLM(model="gemini/gemini-3.1-pro-preview", api_key=api_key)

            # 3. Define the Workforce
            engineer = Agent(
                role="Lead Systems Engineer",
                goal="Analyze raw user feedback data, identify the most critical systemic issues, and propose Replit-compatible technical roadmaps.",
                # NEW REPLIT-AWARE BACKSTORY:
                backstory="You are a senior technical architect for Jom-Plan. Crucially, you know that the entire Jom-Plan application is built, hosted, and deployed natively on Replit using Python. When you propose technical fixes, you must provide solutions, code snippets, and terminal commands that are specifically designed to be executed within the Replit cloud IDE environment.",
                llm=pro_llm,
                verbose=True
            )

            ceo = Agent(
                role="Chief Executive Officer",
                goal="Translate technical realities into strategic shareholder recommendations.",
                # NEW REPLIT-AWARE BACKSTORY:
                backstory="You are the visionary CEO of Jom-Plan. You know the tech stack is hosted on Replit, which allows for rapid, agile deployment. You take technical reports from your engineer and decide which fixes make the most business sense to present to the board of directors.",
                llm=pro_llm,
                verbose=True
            )

            # 4. Define the Consolidated Tasks
            engineering_task = Task(
                description=f"Analyze the following live dataset of Jom-Plan user feedback:\n\n{feedback_data}\n\nYour task:\n1. Categorize the feedback to find the top systemic issues or feature requests.\n2. Provide a step-by-step technical execution plan for the most critical issue.\n3. Write a 'Consolidated Technical Review' summarizing the overall health of the app based on this data.",
                expected_output="A structured Consolidated Technical Review with categorized bugs and proposed technical solutions.",
                agent=engineer
            )

            ceo_task = Task(
                description="Read the Engineer's Consolidated Technical Review. Draft a formal memorandum to the Jom-Plan Shareholders. In this memo, summarize the app's current technical health based on the data, and officially recommend which of the engineer's fixes we should prioritize investing in for the next development sprint. Justify your choices with business and user-retention logic.",
                expected_output="A formal, professional Shareholder Memorandum recommending specific technical fixes.",
                agent=ceo
            )

            # 5. Run the Crew
            jom_plan_crew = Crew(
                agents=[engineer, ceo], 
                tasks=[engineering_task, ceo_task], 
                process=Process.sequential # Engineer runs first, hands output to CEO
            )
            
            result = jom_plan_crew.kickoff()
            
            # 6. Display the Results
            st.success("✅ Analysis Complete!")
            st.markdown("### 📊 CEO's Shareholder Memorandum")
            st.write(result.raw)
            
            with st.expander("View the Engineer's Raw Technical Data"):
                st.write(engineering_task.output.raw)

