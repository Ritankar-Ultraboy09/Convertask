import requests
import re
from datetime import datetime, timedelta
import time

REQUEST_DELAY = 0.3  

def PushTasktoNotion(modelread_path):
    NOTION_TOKEN = "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"
    DATABASE_ID = "1fbed913d3ae809bac31e2c2d65b2093"

    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28"
    }

    
    results = {
        "action_items": 0,
        "decision_items": 0,
        "followups": 0,
        "errors": 0,
        "error": None
    }

    try:
        with open(modelread_path, "r", encoding="utf-8") as f:
            content = f.read().strip()
    except Exception as e:
        error_msg = f"❌ Failed to read file: {str(e)}"
        print(error_msg)
        results["error"] = error_msg
        results["errors"] += 1
        return results

    if not content:
        error_msg = "❌ Empty content in file"
        print(error_msg)
        results["error"] = error_msg
        results["errors"] += 1
        return results

   
    required_sections = [
        "Action Items:",
        "Decisions:",
        "Follow-up Steps:",
        "Speaker Identification:"
    ]
    missing_sections = [s for s in required_sections if s not in content]
    
    if missing_sections:
        error_msg = f"❌ Missing required sections: {', '.join(missing_sections)}"
        print(error_msg)
        results["error"] = error_msg
        results["errors"] += len(missing_sections)
        return results

    
    def extract_items(section_name, content):
        try:
            section = content.split(section_name)[1]
            
            stop_keywords = [s for s in required_sections if s != section_name]
            for keyword in stop_keywords:
                if keyword in section:
                    section = section.split(keyword)[0]
          
            return re.findall(r'\d+\.\s+(.*)', section.strip())
        except IndexError:
            return []

    def extract_speaker(content):
        match = re.search(r"Speaker Identification:\s*(.+)", content)
        return match.group(1).strip() if match else "Unknown"

    try:
        speaker = extract_speaker(content)
        print(f"🔊 Extracted speaker: {speaker}")
    except Exception as e:
        speaker = "Unknown"
        print(f"⚠️ Speaker extraction failed: {str(e)}")

    
    sections = {
        "action_items": extract_items("Action Items:", content),
        "decision_items": extract_items("Decisions:", content),
        "followups": extract_items("Follow-up Steps:", content)
    }

    print(f"📋 Extraction results - "
          f"Actions: {len(sections['action_items'])}, "
          f"Decisions: {len(sections['decision_items'])}, "
          f"Follow-ups: {len(sections['followups'])}")

    
    def upload_to_notion(task, item_type, speaker, deadline=None):
        if not task.strip():
            print("⚠️ Empty task skipped")
            return False

        properties = {
            "Name": {"title": [{"text": {"content": task}}]},
            "Type": {"select": {"name": item_type}},
            "Status": {"status": {"name": "Not started"}},
            "Speaker": {"rich_text": [{"text": {"content": speaker}}]},
            "From": {"rich_text": [{"text": {"content": "Summary"}}]},
        }

        if deadline:
            properties["Deadline"] = {"date": {"start": deadline}}

        payload = {
            "parent": {"database_id": DATABASE_ID},
            "properties": properties
        }

        try:
            response = requests.post(
                "https://api.notion.com/v1/pages",
                headers=headers,
                json=payload,
                timeout=10
            )
            response.raise_for_status()
            print(f"✅ Successfully added: {task}")
            return True
        except requests.exceptions.RequestException as e:
            print(f"❌ Failed to add: {task}")
            print(f"Error: {str(e)}")
            if hasattr(e, 'response') and e.response:
                print(f"Response: {e.response.status_code} - {e.response.text}")
            return False

    def estimate_deadline(task_text):
        """Improved deadline estimation"""
        task_lower = task_text.lower()
        match = re.search(
            r'\b(by|before|on)\s+(tomorrow|\d{1,2}(?:st|nd|rd|th)?|\d{1,2}/\d{1,2}(?:/\d{2,4})?)',
            task_lower
        )
        
        if "tomorrow" in task_lower:
            return (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        elif match:
            date_part = match.group(2)
            if '/' in date_part:
                month, day = date_part.split('/')[:2]
                current_year = datetime.now().year
                return f"{current_year}-{month.zfill(2)}-{day.zfill(2)}"
            return (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")
        return None

    
    for task in sections["action_items"]:
        try:
            deadline = estimate_deadline(task)
            if upload_to_notion(task, "Action", speaker, deadline):
                results["action_items"] += 1
            else:
                results["errors"] += 1
            time.sleep(REQUEST_DELAY)
        except Exception as e:
            print(f"❌ Error processing action item: {task}\n{str(e)}")
            results["errors"] += 1

    for task in sections["decision_items"]:
        try:
            if upload_to_notion(task, "Decision", speaker):
                results["decision_items"] += 1
            else:
                results["errors"] += 1
            time.sleep(REQUEST_DELAY)
        except Exception as e:
            print(f"❌ Error processing decision: {task}\n{str(e)}")
            results["errors"] += 1

    for task in sections["followups"]:
        try:
            deadline = estimate_deadline(task)
            if upload_to_notion(task, "Follow-up", speaker, deadline):
                results["followups"] += 1
            else:
                results["errors"] += 1
            time.sleep(REQUEST_DELAY)
        except Exception as e:
            print(f"❌ Error processing follow-up: {task}\n{str(e)}")
            results["errors"] += 1

    print(f"✅ Final push results: {results}")
    return results