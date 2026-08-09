# build_concepts_vectorstore.py


from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document



import json


CORPUS_PATH = "data/mpt_deck_content.json"


def load_corpus() -> list[dict]:
    with open(CORPUS_PATH) as f:
        return json.load(f)


def build_documents(corpus: list[dict]) -> list:
    """
    Build a list of Document objects from the corpus.
    """
    docs = [Document(
            page_content = ' '.join(entry['text']) + ' ' + str(entry['notes']) + ' ' + ' '.join(entry['image_descriptions']),
            metadata = {'slide': entry['slide'], 
                        'title': entry['title'],
                        'section': entry['section'],}
        ) 
        for entry in corpus
        ]

    return docs


def main():
    """
    TODO: load_corpus() -> build_documents() -> HuggingFaceEmbeddings("all-MiniLM-L6-v2")
    (same model 003 used) -> Chroma.from_documents(...), same shape as 003's cell 18/32.
    Give it a real collection_name (not 003's placeholder "tech_facts") and persist it
    somewhere on disk so consult_concepts_specialist can load the same collection later
    instead of re-embedding every run.
    """
    content = load_corpus()
    docs = build_documents(content)

    hf_embeddings = HuggingFaceEmbeddings(model_name='all-MiniLM-L6-v2')

    # Build vectorstore
    vectorstore = Chroma.from_documents(
        documents=docs,
        embedding = hf_embeddings,
        collection_name = 'slide_data',
        ids = [f'doc_{i}' for i in range(len(content))],
        persist_directory = 'data/chroma_mpt_deck_vectorstore'
        )


if __name__ == "__main__":
    main()
    
