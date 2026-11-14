# Tokenizer research: Macedonian

2026-11-14 · Prototype: [`tests/tokenizers/compare_tokenizers.py`](../tests/tokenizers/compare_tokenizers.py)

## Answer

Yes, both word and subword tokenizers handle Macedonian and run locally. Subword tokenizers need a one-time download from Hugging Face.

- **Word level:** ReLDI (`reldi-tokeniser`, `lang="mk"`). It made 1 error on our samples, against 3 for spaCy.
- **Subword:** XLM-R SentencePiece. It produced 0 unknown tokens at 2.00 tokens per word, the best of the five tested.

## Why we need one

An embedding model brings its own tokenizer, so a word tokenizer is only needed for:

- a TF-IDF/BM25 clustering baseline
- near-duplicate detection (shingles)
- keywords and tags
- sentence splitting for extractive summaries

Subword token counts matter for API cost and for model input limits.

## Method

We wrote 5 news-style sentences by hand (78 words). Together they cover:

- abbreviations: `д-р`, `т.н.`, `Проф.`, `ул.`, `бр.`, `г.`, `ч.`
- dates, decimal commas, `%` and times
- Macedonian quotes `„“`, an en dash and an ellipsis
- a URL, a hashtag, an @mention and mixed Latin and Cyrillic script
- every Macedonian-specific letter: `ѓ ќ ѕ љ њ џ`

We reviewed word tokenizer output by hand. Subword tokenizers were scored on tokens per word and unknown tokens.

Five sentences can rule a tokenizer out but can't pick one. The final choice needs real articles.

## Results: word tokenizers

| Case | spaCy `blank("mk")` | ReLDI `mk` |
| --- | --- | --- |
| `т.н.` | correct | **wrong**: `т.` `н` `.` |
| `Проф.` (capitalised) | **wrong**: `Проф` `.` | correct |
| `ч.` | **wrong**: `ч` `.` | correct |
| `):` | **wrong**: kept as one token | correct |
| `#буџет2026` | split: `#` `буџет2026` | kept whole |
| `д-р`, `ул.`, `бр.`, `г.`, dates, `5,2`, `3,5%`, `22:00`, URL, `@vlada_mk`, `ѓ ќ ѕ љ њ џ` | correct | correct |
| **Errors** | **3** | **1** |

The hashtag split isn't counted as an error. Which behaviour is better depends on how we use hashtags.

- **spaCy:** comes with 810 stopwords and a rule-based Macedonian lemmatizer. The lemmatizer needs `spacy-lookups-data` and hasn't been tested.
- **ReLDI:** comes with a 134-line Macedonian abbreviation file and splits sentences. It's built by CLARIN.SI. That it's the tokenizer behind CLASSLA is unverified.

An earlier single-sentence test favoured spaCy. The wider sample set reversed that.

## Results: subword tokenizers

| Tokenizer | Tokens | Unknown | Tokens per word |
| --- | --- | --- | --- |
| `FacebookAI/xlm-roberta-base` | 156 | 0 | 2.00 |
| `intfloat/multilingual-e5-base` | 156 | 0 | 2.00 |
| `google-bert/bert-base-multilingual-cased` | 206 | 4 | 2.64 |
| tiktoken `o200k_base` | 225 | n/a | 2.88 |
| tiktoken `cl100k_base` | 305 | n/a | 3.91 |

- multilingual-e5 uses the same vocabulary as XLM-R, so any e5-based embedding model inherits these numbers.
- mBERT's 4 unknown tokens are the closing quote `“` and the en dash `–`. The punctuation is lost but no words are.
- Tokens per word multiply per-token cost. On Macedonian, `cl100k_base` costs about 2× what XLM-R does.

## Recommendation

- **Word level:** use ReLDI tokens with spaCy's stopword list. Add one rule that merges `т.` `н` `.` back into `т.н.`.
- **Subword:** use the XLM-R tokenizer for token counting and for any e5 or XLM-R based model.

## Next

1. **Lemmatization matters more than tokenization.** Macedonian attaches the definite article to the word (`влада` → `владата`, `премиер` → `премиерот`), so without lemmas TF-IDF treats them as different words. Next we test spaCy `mk` lemmas, CLASSLA `mk` and a simple suffix stemmer.
2. Re-run on 300 or more real articles once ingest exists, and record error rates.
3. Measure throughput in articles per second. It hasn't been measured yet.

## Reproduce

```bash
cd seer/tests/tokenizers
python -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python compare_tokenizers.py
```

## Sources

- spaCy 3.8.18, `spacy/lang/mk`: https://github.com/explosion/spaCy/tree/master/spacy/lang/mk
- reldi-tokeniser 1.0.3: https://pypi.org/project/reldi-tokeniser/
- XLM-R: https://huggingface.co/FacebookAI/xlm-roberta-base
- multilingual-e5: https://huggingface.co/intfloat/multilingual-e5-base
- mBERT: https://huggingface.co/google-bert/bert-base-multilingual-cased
- tiktoken 0.14.0: https://pypi.org/project/tiktoken/

## Assumptions

- The hand-written samples are representative of real news text. This needs checking on real articles.
- Hashtag splitting is treated as neutral, not as an error.
