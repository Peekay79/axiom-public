# utils/streaming.py

import time
from threading import Thread

import torch
from flask import Response
from transformers import TextIteratorStreamer


def stream_chat_response(model, tokenizer, messages, max_new_tokens=512):
    prompt = (
        "\n".join(f"{m['role']}: {m['content']}" for m in messages) + "\nassistant:"
    )
    print(f"[🗣️ STREAMING PROMPT]\n{prompt}")

    input_ids = tokenizer(prompt, return_tensors="pt").input_ids
    attention_mask = torch.ones_like(input_ids)

    device = next(iter(model.hf_device_map.values()))
    input_ids = input_ids.to(device)
    attention_mask = attention_mask.to(device)

    streamer = TextIteratorStreamer(
        tokenizer, skip_prompt=True, skip_special_tokens=True
    )

    generate_kwargs = {
        "input_ids": input_ids,
        "attention_mask": attention_mask,
        "max_new_tokens": max_new_tokens,
        "temperature": 0.7,
        "top_p": 0.95,
        "do_sample": True,
        "streamer": streamer,
        "pad_token_id": tokenizer.eos_token_id,
    }

    def background_generate():
        with torch.no_grad():
            model.generate(**generate_kwargs)

    thread = Thread(target=background_generate)
    thread.start()

    def event_stream():
        try:
            for new_text in streamer:
                yield f"data: {new_text}\n\n"
                time.sleep(0.02)  # Control stream pace (tune if needed)
            yield "event: done\ndata: [DONE]\n\n"
        except GeneratorExit:
            print("[⛔️ Client Disconnected]")
        except Exception as e:
            yield f"event: error\ndata: {str(e)}\n\n"

    return Response(event_stream(), content_type="text/event-stream")
