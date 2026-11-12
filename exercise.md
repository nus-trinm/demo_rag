# RAG Assignment: NUSAskify - Internal Policy Q&A

## Goal

Build a small RAG application named NUSAskify: Upload policy documents â†’ Select documents â†’ Ask a question â†’ Get an answer with the source chunks.

After this assignment, learners can:

- Draw the semantic search flow and point out one failure mode of similarity.
- Design a basic RAG system with citations that can answer "not enough information".
- Tell whether an error comes from retrieval or generation.

## Setup

- **Tech stack:** your choice. Use any language, framework, database or vector store, as long as the vector store can filter by metadata (tenant, validity dates, document). State your choices in the README.
- **Models:** any embedding model and any chat model, either local (e.g. [Ollama](https://docs.ollama.com/quickstart)) or a cloud API. If you use a cloud API, use non-sensitive documents only.
- **Documents:** upload company policy documents or write 4-6 documents yourself, for example: remote work, annual leave, travel expenses. The set must include:
  - a document with an expired old version and a current version
  - a document that belongs to another tenant (company or department)
  - a question worded differently from the document, for example asking about "working from home" when the document says "remote work"

```
Web UI  â‡„  Backend API  â‡„  Database / vector store
                â‡…
     Embedding model + chat model
```

## Step 1. Design the data model

Use at least 3 tables (or collections). Add your own fields, keys and indexes.

| Table | Purpose | Suggested fields |
|---|---|---|
| `documents` | One uploaded file (one version) | `id`, `tenant_id`, `title`, `version`, `valid_from`, `valid_to`, `status`, â€¦ |
| `chunks` | Chunks with their vectors | `id`, `document_id`, `chunk_index`, `content`, `embedding`, â€¦ |
| `query_logs` | Each question, kept for debugging | `id`, `question`, `retrieved_chunk_ids`, `answer`, `created_at`, â€¦ |

Note: the vector dimension must match the embedding model's dimension.

## Step 2. Ingestion: parse â†’ chunk â†’ embed â†’ index

The ingestion pipeline must:

1. **Parse** uploaded files into text. Supporting every file type is not required, but PDF and DOCX are a must. Reject other file types with a clear error message.
2. **Chunk** the text with **semantic chunking**: split where the meaning changes, that is, where the similarity between adjacent sentences or paragraphs drops sharply. Use a library or build your own:
   1. Split the text into small pieces (sentences or paragraphs).
   2. Embed each piece.
   3. Compute the cosine similarity between each piece and the next one.
   4. Go through the pieces in order: if the similarity is high, add the piece to the current chunk; if it is low, or the chunk is already too long, start a new chunk.
3. **Embed** each chunk.
4. **Index** each chunk with its vector and metadata.

Also implement a simple structure-based chunking (by paragraph or heading) and compare retrieval results with semantic chunking in your report.

Notes:

- Questions and chunks must use the same embedding model.
- When a new version is uploaded, mark the old version as expired or delete its chunks.
- Reject documents that lack required metadata (tenant, validity dates); do not index them.

## Step 3. Build the API with docs

Read the tenant from the `X-Tenant-Id` header to simulate a multi-tenant system. The API must support the following endpoints:

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/documents` | Upload a file + metadata â†’ run ingestion |
| GET | `/api/documents` | List the tenant's documents |
| GET | `/api/documents/:id/chunks` | Show a document's chunks (debug) |
| DELETE | `/api/documents/:id` | Delete a document and its chunks |
| POST | `/api/search` | Semantic search only (no LLM): `{ question, document_ids, top_k }` â†’ chunks with scores |
| POST | `/api/ask` | Q&A: `{ question, document_ids }` â†’ `{ status, answer, citations, chunks }` |

**`/api/ask` flow:** identify the tenant â†’ filter (tenant, selected documents, still valid) **inside the retrieval query, before top-k** â†’ embed the question â†’ top-k â†’ if scores are poor, return "not enough information" â†’ LLM answers with citations, making sure every citation points to a retrieved chunk.

**API docs:** provide interactive API documentation that can be opened in a browser (e.g. OpenAPI / Swagger UI).

## Step 4. Web frontend

Any frontend framework. Main parts:

- Tenant selector (dropdown, sent as a header)
- Upload form
- Document list with checkboxes to choose the search scope
- Question input + submit button
- Answer panel + list of retrieved chunks

## Step 5. Required features

1. Upload a document with metadata.
2. Select one or more documents, then submit a question.
3. Show the answer with citations.
4. Show the retrieved chunks: document, version, score, content.
5. When there is not enough information, say so clearly instead of making up an answer.

## Step 6. Test cases

| # | Scenario | Expected |
|---|---|---|
| TC1 | Question worded differently from the document | Correct chunk retrieved; correct answer with a citation |
| TC2 | Call `/api/search` with the TC1 question | Record the top 3 chunks with scores; explain why semantic search finds the chunk when the words don't match |
| TC3 | Question not covered by any document | Return "not enough information"; no made-up answer |
| TC4 | Expired version and current version both uploaded | Only the current version is used |
| TC5 | Switch to another tenant | No chunks from the other tenant |
| TC6 | Select only document A, ask about document B | No chunks from B |
| TC7 | Check citations | Every citation points to a retrieved chunk that actually supports the claim |
| TC8 | Failure mode of similarity | A case where the "most similar" chunk is not the right answer |

## Deliverables

- **Code:** a repo with backend & frontend.
- **Report in the README:** chosen tech stack, flow diagram, database diagram with fields, semantic vs. structure-based chunking comparison, test results for TC1â€“TC8, instructions to run the app.

| Criterion | Points |
|---|---|
| Database + ingestion | 25 |
| API + docs | 25 |
| Frontend | 20 |
| Test cases + diagnosis | 30 |

## Appendix: references (optional)

Examples libraries and tools for NodeJS and Python - You may use any other tools. Read their documentation for usage and implement the RAG app.

| Task | Node.js | Python |
|---|---|---|
| Upload file | [multer](https://github.com/expressjs/multer): `multer().single('file')` â†’ `req.file.buffer` | [FastAPI](https://fastapi.tiangolo.com/tutorial/request-files/): `file: UploadFile = File(...)`, `await file.read()` |
| Read PDF | [pdf-parse](https://github.com/mehmet-kozan/pdf-parse): `new PDFParse({ data }).getText()` â†’ `.text` | [pypdf](https://pypdf.readthedocs.io): `PdfReader(f).pages` â†’ `page.extract_text()` |
| Read DOCX | [mammoth](https://github.com/mwilliamson/mammoth.js): `mammoth.extractRawText({ buffer })` â†’ `.value` | [python-docx](https://python-docx.readthedocs.io): `Document(f).paragraphs` â†’ `p.text` |
| Semantic chunking | [@chonkiejs/core](https://github.com/feyninc/chonkiejs/tree/main/packages/core): `SemanticChunker.create({ embeddings, threshold, chunkSize })` â†’ `chunker.chunk(text)`<br>[semantic-chunking](https://github.com/jparkerweb/semantic-chunking): `chunkit(documents, { embedCallback, similarityThreshold, maxTokenSize })` | [LangChain SemanticChunker](https://github.com/langchain-ai/langchain-experimental/blob/main/libs/experimental/langchain_experimental/text_splitter.py): `SemanticChunker(embeddings, breakpoint_threshold_type="percentile")` â†’ `.split_text(text)`<br>[LlamaIndex](https://developers.llamaindex.ai/python/examples/node_parsers/semantic_chunking/): `SemanticSplitterNodeParser(buffer_size, breakpoint_percentile_threshold, embed_model)` â†’ `.get_nodes_from_documents(docs)`<br>[Chonkie](https://docs.chonkie.ai/oss/chunkers/semantic-chunker): `SemanticChunker(embedding_model, threshold, chunk_size)` â†’ `.chunk(text)` |
| Structure-based chunking | [LangChain](https://docs.langchain.com/oss/javascript/integrations/splitters/recursive_text_splitter): `new RecursiveCharacterTextSplitter({ chunkSize, chunkOverlap })` â†’ `.splitText(text)` | [LangChain](https://docs.langchain.com/oss/python/integrations/splitters/recursive_text_splitter): `RecursiveCharacterTextSplitter(chunk_size, chunk_overlap)` â†’ `.split_text(text)` |
| Embedding + chat (local) | [ollama-js](https://github.com/ollama/ollama-js): `ollama.embed({ model, input })` â†’ `.embeddings`, `ollama.chat({ model, messages })` â†’ `.message.content` | [ollama-python](https://github.com/ollama/ollama-python): `ollama.embed(model=, input=)["embeddings"]`, `ollama.chat(model=, messages=)["message"]["content"]` |
| API docs | [swagger-jsdoc](https://github.com/Surnet/swagger-jsdoc) + [swagger-ui-express](https://github.com/scottie1984/swagger-ui-express): `swaggerJSDoc({ definition, apis })`, `app.use('/api-docs', swaggerUi.serve, swaggerUi.setup(spec))` | [FastAPI](https://fastapi.tiangolo.com/tutorial/metadata/): docs generated automatically at `/docs` |

**Vector store:** [PostgreSQL](https://www.postgresql.org) with the [pgvector](https://github.com/pgvector/pgvector) extension, or a vector database such as [Chroma](https://docs.trychroma.com), [Qdrant](https://qdrant.tech/documentation/), [Weaviate](https://docs.weaviate.io/weaviate), [Milvus](https://github.com/milvus-io/milvus) or [Pinecone](https://docs.pinecone.io) (cloud). Choose one that supports metadata filtering.

**Example local models:** `qwen3-embedding:0.6b` (embedding), `qwen3:4b-instruct` (chat).