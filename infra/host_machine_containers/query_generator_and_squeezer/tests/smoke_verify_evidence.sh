#!/usr/bin/env bash
# Calls /verify_evidence on three known samples against the running wrapper and prints the raw replies.
# Usage:  API_KEY=your-key bash tests/smoke_verify_evidence.sh [base_url]     (default http://localhost:8000)
BASE="${1:-http://localhost:8000}"

call() {
  curl -s -X POST "$BASE/verify_evidence" \
    -H "x-api-key: $API_KEY" -H "Content-Type: application/json" -d "$1"
  echo; echo
}

echo "== (a) expected: quote_supports_claim no, final no"
call '{"aspect":"how memory cost is defined","claim":"Memory cost is expressed as the percentage of total model parameters that are trainable.","quote":"# Params (%)"}'

echo "== (b) expected: quote_supports_claim yes, answers_aspect yes, final yes"
call '{"aspect":"advantages of LoRA fine-tuning","claim":"LoRA introduces no additional inference latency because the adapted weight can be merged back into the original matrix.","quote":"LoRA and its related variants do not introduce any extra latency during the inference compared to the original model."}'

echo "== (c) expected: answers_aspect no or partial, final not yes"
call '{"aspect":"How does RAG enable fact-checking and verification of LLM outputs?","claim":"Introducing active retrieval (RAG) into visual language models provides external knowledge that helps alleviate hallucinations.","quote":"by studying the introduction of active retrieval to enhance large visual language models to alleviate hallucinations, LVLM can be enhanced with external knowledge [7]."}'
