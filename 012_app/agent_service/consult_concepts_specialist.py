# consult_concepts_specialist.py

import os
import getpass

from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document

from langchain_classic.retrievers.multi_query import MultiQueryRetriever
from langchain_core.prompts.prompt import PromptTemplate
from langchain_classic.chains.query_constructor.schema import AttributeInfo
from langchain_classic.retrievers.self_query.base import SelfQueryRetriever
from langchain_core.structured_query import (
    Comparator,
    Operator,
    Comparison,
    Operation,
    StructuredQuery,
    Visitor,
)
from langchain_anthropic.chat_models import ChatAnthropic
from langchain_core.tools import tool

from sentence_transformers import CrossEncoder
from langchain.agents import create_agent

def get_llm(temperature = 0.2, max_tokens = 500):
    """
    Helper function to create and return a ChatAnthropic LLM instance with specified parameters.
    """
    return ChatAnthropic(
        temperature=temperature,
        max_tokens=max_tokens,
        model="claude-haiku-4-5"
    )


if not os.environ.get("ANTHROPIC_API_KEY"):
    os.environ["ANTHROPIC_API_KEY"] = getpass.getpass("Enter your Anthropic API key: ")


import logging
logging.basicConfig()
logging.getLogger("langchain.retrievers.multi_query").setLevel(logging.INFO)



def load_vectorstore() -> Chroma:
    vectorstore = Chroma(
        collection_name='slide_data',
        persist_directory='data/chroma_mpt_deck_vectorstore',
        embedding_function=HuggingFaceEmbeddings(model_name='all-MiniLM-L6-v2')
    )
    return vectorstore




class SimpleChromaTranslator(Visitor):
    """Hand-written stand-in for langchain_community's ChromaTranslator --
    same Visitor interface SelfQueryRetriever expects, zero langchain_community
    dependency. Chroma's `where` filter syntax uses Mongo-style operator keys
    ($eq, $and, ...), which is all this class maps onto."""

    allowed_comparators = (
        Comparator.EQ, Comparator.NE, Comparator.GT, Comparator.GTE,
        Comparator.LT, Comparator.LTE, Comparator.IN, Comparator.NIN,
    )
    allowed_operators = (Operator.AND, Operator.OR)

    _op_map = {Operator.AND: "$and", Operator.OR: "$or"}
    _cmp_map = {
        Comparator.EQ: "$eq", Comparator.NE: "$ne", Comparator.GT: "$gt",
        Comparator.GTE: "$gte", Comparator.LT: "$lt", Comparator.LTE: "$lte",
        Comparator.IN: "$in", Comparator.NIN: "$nin",
    }

  
    def visit_operation(self, operation: Operation) -> dict:
        args = [arg.accept(self) for arg in operation.arguments]
        return {self._op_map[operation.operator]: args}

    def visit_comparison(self, comparison: Comparison) -> dict:
        return {comparison.attribute: {self._cmp_map[comparison.comparator]: int(comparison.value)}}

    def visit_structured_query(self, structured_query: StructuredQuery):
        if structured_query.filter is None:
            return structured_query.query, {}
        return structured_query.query, {"filter": structured_query.filter.accept(self)}

def build_self_query_retriever(vectorstore):
    metadata_field_info = [
        AttributeInfo(name="slide", description="The slide number of the presentation", type="integer"),
        AttributeInfo(name="title", description="The title of the slide", type="string"),
        AttributeInfo(name="section", description="The section of the presentation", type="string"),
    ]

    document_contents = 'Content of the document, including text, notes, and image descriptions.'

    self_query_retreiver = SelfQueryRetriever.from_llm(
        llm = get_llm(),
        vectorstore = vectorstore,
        document_contents = document_contents,
        metadata_field_info = metadata_field_info,
        structured_query_translator = SimpleChromaTranslator(),
        enable_limit = True,
    )

    return self_query_retreiver



def build_multi_query_retriever(self_query_retriever):
    multi_query_prompt = PromptTemplate(
        input_variables=["question"],
        template="""You are an AI language model assistant. Your task is to generate
        3 different versions of the given user question to retrieve relevant documents
        from a vector database. By generating multiple perspectives on the user
        question, your goal is to help the user overcome some of the limitations of
        distance-based similarity search.

        Respond with ONLY the 3 alternative questions, one per line. Do not include
        any headers, titles, numbering, bullet points, or any other text -- just the
        3 questions themselves, each on its own line.

        Original question: {question}""",
    )

    multiquery_retriever = MultiQueryRetriever.from_llm(
        retriever = self_query_retriever,
        llm = get_llm(),
        prompt = multi_query_prompt,
    )

    return multiquery_retriever


@tool(response_format='content_and_artifact')
def retrieve_results(query: str) -> str:
    '''Wrap self_query_retriever and multi_query_retriever in a tool for the agent to use.'''
    vectorstore = load_vectorstore()
    self_query_retriever = build_self_query_retriever(vectorstore=vectorstore)
    multi_query_retriever = build_multi_query_retriever(self_query_retriever=self_query_retriever)

    results = multi_query_retriever.invoke(query)

    reranker = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')

    pairs = [(query, d.page_content) for d in results]
    scores = reranker.predict(pairs)
    reranked_results = sorted(zip(results, scores), key=lambda pair: -pair[1])
    results = [d[0] for d in reranked_results]

    return ("\n\n".join(d.page_content for d in results), results)  



def main():
    agent = create_agent(
            model= 'claude-haiku-4-5',
            system_prompt = "You are a helpful assistant with access to a tool that will retrieve relevant documents from a presentation about investing based on the user's questions. Only answer using the documents returned from the tool, never answer using your own knowledge. Instead say that you dont have that information.",
            tools=[retrieve_results],
        )
    return agent


if __name__ == "__main__":
    agent = main()
    result = agent.invoke({"messages":[{"role": "user", "content": "What are the key takeaways from the presentation?"}]})
    for i in result['messages']:
        print(i.type)
        print(i.content)
        print('-'*6)
