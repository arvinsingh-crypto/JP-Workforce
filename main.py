import os
import streamlit as st
from crewai import Agent, Task, Crew, Process, LLM

# --- 1. Streamlit Web Interface Setup ---
st.set_page_config(page_title="Jom-Plan AI Workforce", page_icon="🇲🇾")
st.title("🚀 Jom-Plan AI C-Suite")
st.markdown("Welcome to your cloud-based automated workforce.")

# --- 2. Secure API Key Input ---
api_key = st.text_input("Enter your Gemini API Key to wake up the team:", type="password")

if api_key:
    os.environ["GEMINI_API_KEY"] = api_key
    
    # Configure the Brains (using Gemini 3.1 Pro & Gemini 3 Flash)
    pro_llm = LLM(model="gemini/gemini-3.1-pro-preview", api_key=api_key)
    flash_llm = LLM(model="gemini/gemini-3-flash-preview", api_key=api_key)

    # --- 3. Define the Workforce ---
    ceo = Agent(
        role="Chief Executive Officer",
        goal="Coordinate the team and write professional shareholder updates.",
        backstory="You are the visionary CEO of Jom-Plan, ensuring all departments align.",
        llm=pro_llm,
        verbose=True
    )

    engineer = Agent(
        role="Lead App Engineer",
        goal="Analyze app feedback and propose robust technical fixes.",
        backstory="You are a brilliant software engineer based in Kuala Lumpur specializing in app stability.",
        llm=pro_llm,
        verbose=True
    )

    marketer = Agent(
        role="Sales & Marketing Director",
        goal="Create localized Malaysian marketing campaigns.",
        backstory="You are a creative marketing genius who deeply understands Malaysian culture.",
        llm=flash_llm,
        verbose=True
    )

    # --- 4. Define the Work ---
    engineering_task = Task(
        description="Review this simulated feedback: 'App crashes when syncing with Google Calendar during Hari Raya.' Propose a technical fix.",
        expected_output="A brief technical report detailing the bug cause and solution.",
        agent=engineer
    )

    marketing_task = Task(
        description="Draft a 3-day social media campaign for Jom-Plan leading up to Hari Raya focusing on 'Balik Kampung' prep.",
        expected_output="A 3-day social media content schedule tailored to Malaysians.",
        agent=marketer
    )

    ceo_task = Task(
        description="Review the engineer's report and the marketer's campaign. Draft a concise email to Jom-Plan's shareholders summarizing these updates.",
        expected_output="A formal email addressed to Jom-Plan Shareholders.",
        agent=ceo
    )

    # --- 5. The Magic Button ---
    st.markdown("---")
    if st.button("Run Jom-Plan Board Meeting"):
        with st.spinner("The Jom-Plan team is currently working... please wait."):
            
            # Assemble and run the crew
            jom_plan_crew = Crew(
                agents=[engineer, marketer, ceo],
                tasks=[engineering_task, marketing_task, ceo_task],
                process=Process.sequential
            )
            
            result = jom_plan_crew.kickoff()
            
            # Display the final output on the web page
            st.success("Meeting Complete!")
            st.subheader("Final Shareholder Report from the CEO:")
            st.write(result.raw)
else:
    st.info("Waiting for API key to initialize the workforce...")