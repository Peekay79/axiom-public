import torch


def generate_response(model, tokenizer, data, max_new_tokens=512):
    # Validate message structure
    messages = data.get("messages")
    if not isinstance(messages, list):
        raise ValueError("Input 'messages' must be a list of message dictionaries.")

    # Build prompt from chat messages
    try:
        prompt = (
            "\n".join(
                f"{m.get('role', 'user')}: {m.get('content', '')}" for m in messages
            )
            + "\nassistant:"
        )
    except Exception as e:
        raise ValueError(f"Failed to parse 'messages': {e}")

    print(f"[🗣️ PROMPT]\n{prompt}")

    # Tokenize prompt
    input_ids = tokenizer(prompt, return_tensors="pt").input_ids
    attention_mask = torch.ones_like(input_ids)

    # Move tensors to model device
    device = next(iter(model.parameters())).device
    input_ids = input_ids.to(device)
    attention_mask = attention_mask.to(device)

    assert input_ids.device == attention_mask.device

    # Run generation
    with torch.no_grad():
        output = model.generate(
            input_ids=input_ids,
            attention_mask=attention_mask,
            pad_token_id=tokenizer.eos_token_id,
            max_new_tokens=max_new_tokens,
            temperature=0.7,
            top_p=0.95,
            do_sample=True,
        )

    # Decode response from model output
    response_text = tokenizer.decode(
        output[0][input_ids.shape[-1] :], skip_special_tokens=True
    )
    print(f"[💬 RESPONSE]\n{response_text}\n")

    return {
        "id": "chatcmpl-001",
        "object": "chat.completion",
        "model": model.name_or_path,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": response_text},
                "finish_reason": "stop",
            }
        ],
    }
