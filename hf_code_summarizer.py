# hf_code_summarizer.py
import ast

from transformers import pipeline

# Load the Hugging Face summarizer
summarizer = pipeline("summarization", model="facebook/bart-large-cnn", tokenizer="facebook/bart-large-cnn")

def extract_functions(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        source = f.read()

    node = ast.parse(source)
    functions = []

    for n in ast.walk(node):
        if isinstance(n, ast.FunctionDef):
            start_line = n.lineno - 1
            end_line = max([c.lineno for c in ast.walk(n) if hasattr(c, "lineno")])
            function_code = "\n".join(source.splitlines()[start_line:end_line])
            functions.append((n.name, function_code))

    return functions

def summarize_functions(file_path):
    results = []
    functions = extract_functions(file_path)

    for name, code in functions:
        if len(code.strip().split()) < 5:
            continue  # skip too short functions
        try:
            summary = summarizer(code, max_length=60, min_length=20, do_sample=False)[0]["summary_text"]
        except Exception as e:
            summary = f"Error during summarization: {str(e)}"
        results.append({"function": name, "summary": summary})

    return results
