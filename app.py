from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from preprocess import preprocess_file, transcribe_audio
from langmod import ModelAi
from notion_integration import PushTasktoNotion
from meeting_parse import extract_sections
from datetime import datetime
import os
import uuid
from waitress import serve
import tempfile

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024
app.config['SQLALCHEMY_DATABASE_URI'] = "postgresql+psycopg2://aifyuser:user1@localhost:5432/aifydb"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)

class AUDIOFILE(db.Model):
    __tablename__ = "audiofile"
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(10000), nullable=False)
    mimetype = db.Column(db.String(500))
    transcript_path = db.Column(db.String(1000))  
    modelread = db.Column(db.Text)
    processed = db.Column(db.Boolean, default=False)
    error = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

@app.route("/")
def index():
    return render_template("index.html")

@app.route('/upload', methods=['POST'])
def upload():
    print("[ROUTE] /upload triggered")
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files['file']
    if not file or file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    try:
        ext = os.path.splitext(file.filename)[1]
        filename = f"record-{uuid.uuid4().hex}{ext}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)

        
        wav_mp3 = preprocess_file(file_path)
        if not wav_mp3:
            print("[ERROR] Preprocessing failed")
            return jsonify({"error": "Preprocessing failed."}), 500
        wav_path, mp3_path = wav_mp3

       
        transcript, transcript_path = transcribe_audio(wav_path)
        assert transcript is not None, "[ASSERT FAILED] transcript is None"
        assert isinstance(transcript, str), "[ASSERT FAILED] transcript is not a string"
        print(f"[ASSERT PASSED] transcript length: {len(transcript)}")
        transcript_path = os.path.normpath(transcript_path)

        print(f"[DEBUG] Received transcript of length {len(transcript) if transcript else 0}")
        print(f"[DEBUG] Transcript path: {transcript_path}")

       # ✅ Step 3: Retry BEFORE checking transcript existence
        import time
        for attempt in range(5):
            if os.path.isfile(transcript_path):
                print(f"[DEBUG] Transcript file found on attempt {attempt+1}")
                break
            print(f"[RETRY] Waiting for transcript file (attempt {attempt+1})")
            time.sleep(0.2)
        else:
            print("[ERROR] Transcript file not found after retries")
            return jsonify({"error": "Transcript file not found after retries."}), 500

        # ✅ Step 4: Validate transcript content AFTER ensuring file exists
        # if not transcript:
        #     print("[ERROR] Transcript content is empty")
        #     return jsonify({"error": "Empty transcript."}), 500

        # Step 5: Save to DB
        try:
            new_file = AUDIOFILE(
                filename=filename,
                mimetype=file.mimetype,
                transcript_path=transcript_path,
                processed=True,
            )
            db.session.add(new_file)
            db.session.commit()
            print(f"[DB COMMIT] Transcript saved in DB for file ID: {new_file.id}, filename: {filename}")
        except Exception as db_err:
            print(f"[DB ERROR] {db_err}")
            return jsonify({"error": "DB commit failed", "message": str(db_err)}), 500

        return jsonify({
            "success": True,
            "message": "File processed",
            "filename": filename,
            "transcript_path": transcript_path,
            "file_id": new_file.id
        }), 200

    except Exception as e:
        print(f"[FATAL ERROR] {e}")
        return jsonify({"error": True, "message": str(e)}), 500
    


@app.route('/submit', methods=['POST'])
def submit():
    interaction_type = request.form.get("type")
    user_prompt = request.form.get("prompt", "").strip()
    latest_file = AUDIOFILE.query.order_by(AUDIOFILE.id.desc()).first()

    if not latest_file or not latest_file.transcript_path or not os.path.isfile(latest_file.transcript_path):
        return "No valid transcript found", 400

    try:
        result_text, _, _ = ModelAi(latest_file.transcript_path, user_prompt, interaction_type)
        latest_file.modelread = result_text
        db.session.commit()

        sections = extract_sections(result_text)
        return render_template("meeting.html", **sections)

    except Exception as e:
        return f"Failed to generate output: {str(e)}", 500

@app.route('/push', methods=['POST'])
def push_to_notion():
    try:
        last_file = AUDIOFILE.query.filter(
            AUDIOFILE.modelread.isnot(None),
            AUDIOFILE.modelread != ""
        ).order_by(AUDIOFILE.id.desc()).first()

        if not last_file:
            return jsonify({"error": True, "message": "No valid processed file found"}), 400

        with tempfile.NamedTemporaryFile(mode='w+', encoding='utf-8', suffix='.txt', delete=False) as tmp:
            tmp.write(last_file.modelread)
            tmp_path = tmp.name

        results = PushTasktoNotion(tmp_path)
        os.unlink(tmp_path)

        return jsonify({
            "success": True,
            "message": "Tasks pushed to Notion!",
            "results": results,
            "file_id": last_file.id
        })
    except Exception as e:
        return jsonify({"error": True, "message": str(e)}), 500

@app.teardown_appcontext
def shutdown_session(exception=None):
    db.session.remove()

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    serve(app, host="0.0.0.0", port=5000)