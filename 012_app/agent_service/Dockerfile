# Dockerfile
FROM python:3.12-slim

WORKDIR /code

COPY requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

COPY fastapi_app.py /code/fastapi_app.py
COPY main_portfolio_agent.py /code/main_portfolio_agent.py
COPY consult_market_trading_specialist.py /code/consult_market_trading_specialist.py
COPY consult_portfolio_analyst.py /code/consult_portfolio_analyst.py
COPY consult_concepts_specialist.py /code/consult_concepts_specialist.py
COPY data/chroma_mpt_deck_vectorstore /code/data/chroma_mpt_deck_vectorstore

CMD ["fastapi","run", "fastapi_app.py"]