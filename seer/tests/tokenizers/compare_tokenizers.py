"""Compare tokenizers on Macedonian news text. Prototype, not a unit test.

Run: pip install -r requirements.txt && python compare_tokenizers.py
"""

from typing import Callable

SAMPLES = {
    "abbrev-date-url": (
        "Владата на РСМ денеска (14.11.2026) усвои буџет од 5,2 милијарди евра, изјави премиерот д-р Петров. "
        "„Ова е историски ден“, рече тој за МИА. Повеќе на www.mia.mk и т.н."
    ),
    "abbrev-percent": "Проф. Ристовски од ул. „Македонија“ бр. 12 изјави дека инфлацијата е 3,5% во 2025 г.",
    "social-mixed-script": "Министерот објави на X (поранешен Twitter): „Нема поскапување!“ #буџет2026 @vlada_mk",
    "dash-time-ellipsis": "Патот Скопје–Тетово ќе биде затворен од 22:00 до 06:00 ч., соопшти АМСМ...",
    "mk-letters": "Ѓорѓи и Ќирил ги посетија Ѕвездата, Љубојно и Њујорк, а потоа џипот застана.",
}

SUBWORD_MODELS = [
    "FacebookAI/xlm-roberta-base",
    "intfloat/multilingual-e5-base",
    "google-bert/bert-base-multilingual-cased",
]


def word_tokenizers() -> dict[str, Callable[[str], list[str]]]:
    import spacy
    from reldi_tokeniser import run

    nlp = spacy.blank("mk")

    def reldi(text: str) -> list[str]:
        lines = run(text, "mk").splitlines()
        return [ln.split("\t")[1] for ln in lines if "\t" in ln and not ln.startswith("#")]

    return {"spacy-mk": lambda t: [tok.text for tok in nlp(t)], "reldi-mk": reldi}


def main() -> None:
    import tiktoken
    from transformers import AutoTokenizer

    words = {k: len(v.split()) for k, v in SAMPLES.items()}
    total_words = sum(words.values())

    print("## Word tokenizers (review splits by hand)\n")
    for name, tokenize in word_tokenizers().items():
        for key, text in SAMPLES.items():
            print(f"[{name}] {key}: {tokenize(text)}")
        print()

    print("## Subword tokenizers\n")
    print(f"{'tokenizer':45} {'tokens':>7} {'unk':>5} {'tok/word':>9}")
    for model in SUBWORD_MODELS:
        tk = AutoTokenizer.from_pretrained(model)
        toks = [t for text in SAMPLES.values() for t in tk.tokenize(text)]
        unk = sum(t == tk.unk_token for t in toks)
        print(f"{model:45} {len(toks):>7} {unk:>5} {len(toks) / total_words:>9.2f}")
    for enc_name in ["cl100k_base", "o200k_base"]:
        enc = tiktoken.get_encoding(enc_name)
        n = sum(len(enc.encode(text)) for text in SAMPLES.values())
        print(f"{'tiktoken ' + enc_name:45} {n:>7} {'-':>5} {n / total_words:>9.2f}")
    print(f"\n{len(SAMPLES)} samples, {total_words} whitespace words")


if __name__ == "__main__":
    main()
