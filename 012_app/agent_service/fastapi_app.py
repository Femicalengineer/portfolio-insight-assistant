import os
import getpass
import uuid
from fastapi import FastAPI
from pydantic import BaseModel, Field
import main_portfolio_agent
import asyncio

if not os.environ.get("ANTHROPIC_API_KEY"):
    os.environ["ANTHROPIC_API_KEY"] = getpass.getpass("Enter your Anthropic API Key: ")

main_agent = main_portfolio_agent.build_main_agent()

app = FastAPI()

class ChatRequest(BaseModel):
    message: str
    thread_id: str = Field(default='default')

class ChatResponse(BaseModel):
    reply: str

@app.post("/chat", response_model = ChatResponse)
def chat(request: ChatRequest):
    config = {'configurable':{'thread_id':request.thread_id}}
    result =  asyncio.run(main_agent.ainvoke({'messages':[{'role':'user', 'content':request.message}]}, config=config))
    return ChatResponse(reply=result['messages'][-1].content)

@app.get("/health")
def health():
    return {'status':'healthy'}