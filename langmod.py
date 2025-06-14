import requests
import json
import os
import re

def ModelAi(transcript_path, user_prompt=None, interaction_type="Meeting"):
    # Read transcript text
    if os.path.isfile(transcript_path):
        with open(transcript_path, "r", encoding="utf-8") as f:
            text = f.read()
    else:
        text = transcript_path

    # Default prompts
    default_prompts = {
        "Meeting": (
            "You are an expert assistant that extracts structured meeting insights from messy transcripts.\n"
            "Your job is to return a **JSON object only** with:\n"
            "- summary\n"
            "- speaker_minutes (tagged lines)\n"
            "- actions (numbered list)\n"
            "- decisions (brief descriptions)\n"
            "- tasks (clearly defined)\n"
            "- followups (pending topics)\n"
            "- deadlines (with dates if mentioned)\n"
            "- prompt_based (answer the user prompt if present)\n\n"
            "Return 'null' for any section that can't be extracted.\n"
            "Here is an example output format:\n"
            "{\n"
            "  \"summary\": \"...\",\n"
            "  \"speaker_minutes\": \"...\",\n"
            "  \"actions\": \"...\",\n"
            "  \"decisions\": \"...\",\n"
            "  \"tasks\": \"...\",\n"
            "  \"followups\": \"...\",\n"
            "  \"deadlines\": \"...\",\n"
            "  \"prompt_based\": \"...\"\n"
            "}\n"
            "⚠️ Output ONLY the JSON (no markdown, code blocks, or explanations)."
        ),
        "Sales Call": "Summarize the key points and commitments from the sales conversation as JSON.",
        "Brainstorming Session": "Group all proposed ideas into categories and summarize them in JSON.",
        "Review": "Extract all feedback and action items from the review session as a structured JSON object."
    }

    default_prompt = default_prompts.get(interaction_type, "")
    final_prompt = default_prompt
    if user_prompt:
        final_prompt += f"\n\nUser question:\n{user_prompt}"
    full_prompt = f"{final_prompt}\n\n{text}"

    try:
        print("🧠 Sending request to Ollama...")
        response = requests.post(
            "http://localhost:11434/api/generate",
            headers={"Content-Type": "application/json"},
            data=json.dumps({
                "model": "mistral:7b-instruct-q4_0",
                "prompt": full_prompt,
                "stream": False,
                "options": {
                    "temperature": 0,
                    "seed": 42,
                    "num_predict": 2048,
                    "repeat_penalty": 1.1
                }
            })
        )

        print(f"📥 Ollama responded with status: {response.status_code}")
        response.raise_for_status()

        raw_output = response.json().get("response", "")
        if not raw_output:
            raise ValueError("Empty response from Ollama.")

        print("🧾 Raw model output preview:")
        print(repr(raw_output[:1000]))

        # Clean and extract JSON content
        cleaned = raw_output.strip()

        if "```" in cleaned:
            cleaned = re.sub(r"```json|```", "", cleaned).strip()

        # Fallback to regex for robustness
        json_match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if json_match:
            cleaned = json_match.group(0).strip()

        # Fix Python-style None
        cleaned = cleaned.replace(": None", ": null")

        # Validate JSON
        parsed_json = json.loads(cleaned)  # Will raise error if malformed

        # Save cleaned output
        modelread_path = transcript_path.replace(".txt", "_ModelReady.txt")
        with open(modelread_path, "w", encoding="utf-8") as f:
            f.write(cleaned)

        print("📤 JSON cleaned and saved.")
        return cleaned, modelread_path, final_prompt

    except Exception as e:
        print(f"🔥 Error in ModelAi: {e}")
        return json.dumps({"summary": "Model failed to respond properly."}), None, final_prompt
