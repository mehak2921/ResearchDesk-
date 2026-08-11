import sys
import io
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from dotenv import load_dotenv
from crewai import Agent, Task, Crew, LLM
from crewai_tools import SerperDevTool


import crewai.llms.cache as _crewai_cache
_crewai_cache.mark_cache_breakpoint = lambda msg: msg

load_dotenv()


llm = LLM(
    model="groq/llama-3.3-70b-versatile",
    temperature=0.01
)


search_tool = SerperDevTool()


researcher = Agent(
    role="Researcher",
    goal="Research the latest AI trends",
    backstory="You are an experienced AI researcher who provides accurate and concise information.",
    llm=llm,
    tools=[search_tool],
    verbose=True
)


writer = Agent(
    role="Tech Writer",
    goal="Write an engaging article based on the provided research",
    backstory="You are a skilled technology writer known for turning complex AI topics into easy-to-read articles.",
    llm=llm,
    verbose=True
)



research_task = Task(
    description="Find the latest AI trends in 2026.",
    expected_output="A concise report with the top AI trends.",
    agent=researcher
)


write_task = Task(
    description="Write an engaging blog post based on the researcher's report.",
    expected_output="A 4-paragraph blog post about the latest AI trends.",
    agent=writer,
    context=[research_task] # This creates the explicit dependency
)


crew = Crew(
    agents=[researcher, writer],
    tasks=[research_task, write_task],
    verbose=True
)

result = crew.kickoff()

print("\nFinal Output:\n")
print(result)