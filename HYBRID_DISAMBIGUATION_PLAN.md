# HybridSenseResolver: A Multi-Stage Disambiguation Engine

## Introduction
This document outlines a robust, multi-stage hybrid architecture for Word Sense Disambiguation (WSD) designed to enhance the existing `disambiguator.py` module. The motivation behind this approach is to move beyond reliance on a single model or source, embracing a "best-of-breed" philosophy where specialized modules are employed for tasks they excel at, ensuring higher accuracy, efficiency, and resilience. This strategy directly addresses the need for a system that leverages varied strengths, provides robust fallbacks, and integrates seamlessly into the existing pipeline without extensive overhauls.

## Core Principles
*   **"Best at doing what they do":** Each stage of the pipeline utilizes the most appropriate tool or model for a specific sub-task within WSD.
*   **Resilience and Non-Dependence:** The architecture avoids single points of failure by combining multiple scorers and implementing layered fallbacks.
*   **Efficiency:** Prioritizes faster, simpler methods for common cases and reserves more complex, resource-intensive models for genuine ambiguities.
*   **Graceful Degradation:** Ensures the system remains functional even when certain components or external APIs encounter issues.

## Overall Architecture & Flow Diagram
The HybridSenseResolver processes an ambiguous word and its context through a series of cascaded stages. The process aims to resolve the word sense at the earliest possible stage with high confidence, moving to more complex methods only if necessary.

```
+---------------------+
|     User Query      |
|    (Ambiguous Word) |
+----------+----------+
           |
           v
+---------------------+    (High confidence, fast)
|      Stage 1:       |---------------------------> RESOLVED SENSE
| Deterministic Cache |
|   (Custom Mappings, |
|    Static Dicts,    |
|   Monosemous Words) |
+----------+----------+
           |
           v
+---------------------+    (Gather candidates)
|      Stage 2:       |<--------------------------+
| Knowledge-Graph     |                           |
|   Fusion Engine     |                           |
| (WordNet, Wikidata, |                           |
|     ConceptNet)     |                           |
+----------+----------+                           |
           |                                     (Confident Score)
           v                                          |
+---------------------+                           +---+---+
|      Stage 3:       |    (Score candidates)     |   |   |
|  Specialized Sense  |--------------------------->   |   |
|   Ranker (SenseBERT)|                           |   |   |
| (Gloss-Transformer) |                           |   |   |
+----------+----------+                           |   |   |
           |                                     (Low Confidence)
           v                                          |
+---------------------+    (Last resort expert)  +-------+
|      Stage 4:       |---------------------------> RESOLVED SENSE
|   LLM Fallback      |
|  (gpt-4o-mini,      |
|    Llama-2-7B)      |
+----------+----------+
           |
           v
+---------------------+
|  Final Fallback:    |---------------------------> ORIGINAL TERM (Tagged as unresolved)
| Graceful Degradation|
+---------------------+
```

---

## Detailed Stages of the Hybrid Disambiguation Engine

### Stage 1: The Deterministic Resolver (The "No-Brainer" Cache)
This is the first line of defense, designed for speed and accuracy on unambiguous or pre-defined terms.

*   **Role:** To resolve highly frequent, unambiguous, or manually curated terms without any AI processing. It's the fastest and most deterministic stage.
*   **Components:**
    1.  **Custom Mappings Database (`custom_mappings` table):**
        *   **How it works:** This is a high-priority, "ground truth" lookup. It stores explicit synonym mappings or specific sense resolutions for problematic words (`{concept_id_a, concept_id_b, relation_type: 'synonym'}`).
        *   **Strength:** Provides instant, guaranteed resolution for domain-specific jargon or known inconsistencies, overriding any automated process.
    2.  **Static Dictionaries:**
        *   **How it works:** Applies rules from files like `abbreviations.py` and `mwe_reductions.py` to standardize input terms.
        *   **Strength:** Local, instantaneous, and deterministic normalization.
    3.  **Monosemous Word Cache:**
        *   **How it works:** Checks if the ambiguous word has only one known sense in a lexical database (e.g., WordNet). If it does, that sense is immediately returned.
        *   **Strength:** Eliminates unnecessary processing for words that are not truly ambiguous in context.

*   **Flow:** If a resolution is found here, the process **terminates immediately** with high confidence.

### Stage 2: The Knowledge-Graph Fusion Engine (Structured & Fast)
If Stage 1 cannot provide an answer, Stage 2 collects all plausible candidate senses from multiple structured knowledge sources.

*   **Role:** To gather comprehensive potential meanings (senses) and their relationships from diverse, structured databases. It acts as the "candidate sense generator."
*   **Components:**
    1.  **WordNet (via NLTK):**
        *   **Strength:** Excellent for lexical relations, synonyms, hypernyms (IsA hierarchy). Local, fast, and rich in common-language senses.
    2.  **Wikidata (API/Cached):**
        *   **Strength:** Ideal for entity linking, proper nouns, and providing structured descriptions for item types (e.g., "iPhone 15" is an instance of "smartphone"). Can leverage local dumps or aggressive caching for speed.
    3.  **ConceptNet (API):**
        *   **Strength:** Useful for common-sense relationships and broader semantic links that might not be explicitly in WordNet or Wikidata.
*   **Hybrid Logic:** This stage operates by querying these sources in parallel or a quick sequence, collecting *all* plausible candidate senses, their glosses, aliases, and hierarchical paths. It does **not** perform disambiguation itself but prepares a rich set of candidates for the next stage.
*   **Flow:** All gathered `CandidateSense` objects (each with its original word, gloss, source, aliases, and relevant hierarchies) are passed to Stage 3 for scoring.

### Stage 3: The Specialized Sense Ranker (The "SenseBERT" AI Model)
This stage applies deep learning to score and rank the candidate senses from Stage 2. This is where the nuanced contextual understanding happens.

*   **Role:** To accurately score the semantic relevance between the query context and each candidate sense's gloss, picking the most appropriate meaning.
*   **Components (Multi-Model Scoring Ensemble):**
    1.  **Gloss-Transformer Scorer (Primary):**
        *   **Model:** A fine-tuned BERT-like model (e.g., `DistilBERT-base-uncased` or `bert-base-uncased`), often referred to as "SenseBERT" or "GlossBERT".
        *   **How it works:** Reframes WSD as a sentence-pair classification task. For each candidate sense, it forms the input: `[CLS] user's query context [SEP] gloss of candidate sense [SEP]`. The model outputs a score indicating the contextual fit.
        *   **Strength:** Excels at deep contextual semantic matching, capturing nuances that embeddings alone cannot. Highly accurate for distinguishing senses like "bank (river)" vs. "bank (financial)."
    2.  **Embedding Similarity Scorer (Secondary):**
        *   **Model:** Your existing `sentence-transformers.all-MiniLM-L6-v2`.
        *   **How it works:** Computes the cosine similarity between the embedding of the query sentence and the embedding of the candidate gloss.
        *   **Strength:** Lightweight and efficient. Provides a robust baseline for broad semantic alignment, especially useful for short or less structured glosses.
    3.  **Knowledge-Based Scorer (Tertiary):**
        *   **Model:** Rule-based logic leveraging NLTK's WordNet.
        *   **How it works:** Computes structural relationships (e.g., `wordnet.path_similarity()`) between the ambiguous word's synsets and other key terms in the context. Can also check for explicit antonyms or shared hypernyms within a certain depth.
        *   **Strength:** Provides symbolic support and grounds neural predictions in structured knowledge, addressing cases where gloss text might be sparse or neural models miss explicit graph-based relations.

*   **Ensemble Combination:**
    *   **How it works:** Scores from each of the three scorers are normalized (e.g., to a 0-1 range) and combined using a weighted average (e.g., `0.5 * TransformerScore + 0.3 * EmbeddingScore + 0.2 * KnowledgeScore`). These weights are crucial and would be empirically tuned during validation.
    *   **Strength:** Ensures robustness. If one scorer performs poorly on a specific type of ambiguity, others compensate, preventing single-point reliance.

*   **Confidence Threshold:** After combined scoring, if the highest-scoring sense's confidence (its score margin over the second-best) is above a pre-defined threshold (e.g., 0.1-0.2, empirically tuned), the process **terminates here**.

### Stage 4: The LLM Fallback (The "Safety Net")
This is the last resort, invoked only for highly challenging, low-confidence ambiguities.

*   **Role:** To leverage the expansive world knowledge and reasoning capabilities of a large language model for disambiguating truly difficult or novel cases.
*   **Model:** A powerful but cost-effective API-accessible LLM (e.g., `gpt-4o-mini`, `Llama-2-7B-chat-hf` via API or local deployment).
*   **How it works (Prompt Engineering):**
    1.  If the confidence from Stage 3 is too low, a structured prompt is constructed including the user's full query and the top N candidate glosses from Stage 2.
    2.  The LLM is asked to choose the best definition and, optionally, provide a brief reasoning.
    3.  **Prompt Example:**
        ```
        Given the sentence: "[user_query]", which definition best describes the word '[ambiguous_word]'?
        1. [Gloss of Candidate Sense 1]
        2. [Gloss of Candidate Sense 2]
        3. [Gloss of Candidate Sense 3]

        Respond with only the number of the best definition, followed by a brief justification.
        ```
*   **Strength:** Provides a human-like reasoning capability for edge cases, minimizing unresolved ambiguities.

---

## Fallback System: Graceful Degradation Strategy

A critical aspect of this hybrid design is its ability to handle failures without crashing the entire system.

1.  **Component-Level Failure:**
    *   **API Timeouts/Errors (Wikidata, ConceptNet, LLM):** Each external API call will have robust error handling (try-except blocks, timeouts). If an API fails, that specific component's contribution to scoring is marked as zero, and the system proceeds with available information from other sources/stages.
    *   **Model Loading Failure (SenseBERT):** If the SenseBERT model fails to load at startup, it can be bypassed for Stage 3, and the system can proceed directly to Stage 4 (LLM fallback) or even Stage 5 (final fallback), albeit with reduced accuracy.

2.  **Confidence-Based Progression:** The cascaded nature means that if a stage produces a low-confidence result (or no result), the system automatically moves to the next, more powerful stage.

3.  **Final Fallback: Return Original Term:** If, after all stages (including the LLM fallback), a confident disambiguation cannot be achieved (e.g., LLM returns an unparseable response), the system will:
    *   Log a warning about the unresolved term.
    *   Return the original, un-disambiguated term (e.g., "bank") along with a flag indicating `resolved: false`.
    *   This ensures that the downstream matching engine can still attempt a simple string match, preventing a complete system crash and offering some functionality.

---

## Implementation & Integration Plan

Integrating this architecture into your existing `disambiguator.py` module will involve the following steps:

1.  **Model Selection and Setup:**
    *   **Primary Scorer (SenseBERT):** Choose `DistilBERT-base-uncased` as the base model.
    *   **Secondary Scorer:** Reuse your existing `sentence-transformers.all-MiniLM-L6-v2`.
    *   **Tertiary Scorer:** Utilize NLTK's WordNet for path similarity and other graph-based features.
    *   **Fallback LLM:** Identify a suitable local or API-based LLM (e.g., `gpt-4o-mini` via OpenAI API, or a locally run Llama model via `transformers` pipeline).

2.  **Fine-Tuning (for Primary Scorer):**
    *   **Dataset:** Fine-tune `DistilBERT` on the SemCor dataset (annotated with WordNet senses). This will teach the model to correctly score `(context, gloss)` pairs.
    *   **Task:** Binary classification where positive examples are `(sentence, correct_gloss)` and negative examples are `(sentence, incorrect_gloss)`.
    *   **Hardware:** This is a one-time process, typically requiring a GPU (can be done on cloud platforms or services like Google Colab).

3.  **Integration into `disambiguator.py`:**
    *   **Startup:** Load all models and NLTK resources once on application startup.
    *   **Modify `disambiguate(term, context)` function:**
        1.  **Stage 1 Logic:** Implement the Custom Mappings DB lookup, static dict applications, and monosemous word check. Return early if resolved.
        2.  **Stage 2 Logic:** Gather `CandidateSense` objects from WordNet, Wikidata, and ConceptNet.
        3.  **Stage 3 Logic:**
            *   For each `CandidateSense`, prepare inputs for all three scorers (Gloss-Transformer, Embedding, Knowledge-Based).
            *   Run all scorers in batch where possible to get individual scores.
            *   Normalize and combine scores using your weighted ensemble strategy.
            *   Apply the confidence threshold. If a clear winner emerges, return it.
        4.  **Stage 4 Logic:** If confidence is low, invoke the LLM fallback. Construct the prompt with the query and top candidate senses. Parse the LLM's response to select the final sense.
        5.  **Final Fallback:** If all else fails, return the original term, marked as unresolved.

4.  **Testing & Tuning:**
    *   **Validation Set:** Use a dedicated validation set (ideally from your project's historical queries/failures) to tune ensemble weights, confidence thresholds, and evaluate overall system performance.
    *   **Metrics:** Monitor resolution accuracy, latency, and the frequency of LLM fallback invocation.
    *   **Continuous Improvement:** Log unresolved terms or low-confidence resolutions to identify areas for future custom mappings or fine-tuning data.

---

## Why This is the Smartest Hybrid Approach for You

*   **Best-of-Breed Specialization:** Each component excels where others might lack. Transformers provide deep contextual understanding, embeddings offer efficient broad alignment, and symbolic methods ground the system in structured knowledge.
*   **Robust and Non-Dependent:** Eliminates single points of failure. If one scorer underperforms (e.g., on noisy glosses), others compensate. The explicit fallback mechanisms ensure the system can always produce a result.
*   **Efficient Scaling:** The core inferencing models (DistilBERT, Sentence-Transformers) are lightweight and can run efficiently, often on CPU. The expensive LLM is invoked rarely, only for genuine ambiguities, balancing performance and cost.
*   **Deep Integration with Existing Pipeline:** This architecture slots directly into your `disambiguator.py` by enhancing the sense scoring mechanism, preserving your existing sense-gathering logic.
*   **Extensible and Future-Proof:** You can easily add more specialized scorers (e.g., for domain-specific contexts), refine existing ones, or update the LLM fallback as new models become available, without redesigning the entire system.

This HybridSenseResolver represents a sophisticated solution that balances cutting-edge AI with practical engineering principles, ensuring your disambiguation is accurate, efficient, and exceptionally reliable.
