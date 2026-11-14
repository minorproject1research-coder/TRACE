"""Merge the fine-tuned LoRA checkpoint into a standalone 16-bit model for vLLM.

Run once, with the same environment you already use for the Unsloth wrapper.
Input : CKPT_PATH (default /models/checkpoint-32538)
Output: /work/planner-merged  (about 18 GB)
"""
import os
from unsloth import FastModel
from dotenv import load_dotenv
load_dotenv()
ckpt = os.getenv("CKPT_PATH", "/models/checkpoint-32538")
out = os.getenv("OUT_DIR", "C:\\Users\\Lakshya\\OneDrive\\Documents\\query_generator\\work\\planner-merged")

model, tok = FastModel.from_pretrained(
    model_name=ckpt, max_seq_length=2048, load_in_4bit=True
)
model.save_pretrained_merged(out, tok, save_method="merged_16bit")
print("saved merged model to", out)