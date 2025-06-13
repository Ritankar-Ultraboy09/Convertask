import json

def extract_sections(text):
    try:
        sections = json.loads(text)
    except json.JSONDecodeError as e:
        print("Json parsing is failed", str(e))
        return{
            "summary": "[Parse Error]",
            "speaker_minutes": "[Parse Error]",
            "actions": "[Parse Error]",
            "decisions": "[Parse Error]",
            "tasks": "[Parse Error]",
            "followups": "[Parse Error]",
            "deadlines": "[Parse Error]",
            "prompt_based": "[Parse Error]"
        }
    expected_keys = [
        "summary", "speaker_minutes", "actions", "decisions", 
        "tasks", "followups", "deadlines", "prompt_based"
    ]
    for key in expected_keys:
         if key not in sections:
             sections[key] = "[None]"

    return sections