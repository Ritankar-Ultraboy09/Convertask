import torch
import torchaudio
import os
from pydub import AudioSegment
from faster_whisper import WhisperModel
import concurrent.futures
import tempfile



AudioSegment.converter = r"C:\ffmpeg\ffmpeg-7.1.1-essentials_build\bin\ffmpeg.exe"
print(AudioSegment.converter)




def preprocess_file(filepath):
    try:
        audio = AudioSegment.from_file(filepath)
        audio = audio.set_frame_rate(16000).set_channels(1)

        base = os.path.splitext(os.path.basename(filepath))[0]
        wav_path = os.path.join("uploads", f"{base}.wav")
        mp3_path = os.path.join("uploads", f"{base}.mp3")


        audio.export(wav_path, format="wav")
        audio.export(mp3_path, format="mp3")

        print(f"Processed and saved as {wav_path} and {mp3_path}")
        return wav_path, mp3_path

    except Exception as e:
        print(f"[ERROR in preprocess_file]: {e}")
        return None
    
def chunk_audio(waveform, sample_rate, chunk_duration_sec=60):
    chunk_size = sample_rate * chunk_duration_sec
    if waveform.size(1) == 0:
        print("[Warning] Empty waveform passed to chunk_audio.")
        return []
    chunks = [waveform[:, i:i + chunk_size] for i in range(0, waveform.size(1), chunk_size)]
    print(f"chunking into {len(chunks)} chunks.")
    return chunks
    

def transcribe_chunk(chunk_waveform, sample_rate, model, idx):
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_audio:
            temp_path = temp_audio.name
        torchaudio.save(temp_path, chunk_waveform, sample_rate)

        segments, _ = model.transcribe(
            temp_path, beam_size=5, vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500)
        )
        transcript = "".join([seg.text.strip() for seg in segments])
        print(f"t_chunk{idx}")
        return transcript
    except Exception as e:
        print(f"[Error t_chunk{idx}]: {e}")
        return ""
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception as cleanup_e:
                print(f"[Cleanup Error t_chunk{idx}]: {cleanup_e}")



def transcribe_audio(wav_path):
    try: 
        if not os.path.exists(wav_path):
            print(f"[Error] File not found: {wav_path}", flush=True)
            raise FileNotFoundError(f"{wav_path} not found!")
        
        file_size = os.path.getsize(wav_path)
        print(f"[DEBUG] Processing file: {wav_path} (Size: {file_size/1024/1024:.2f} MB)", flush=True)
        
        model_name = "large-v3"
        USE_GPU = torch.cuda.is_available()
        DEVICE = "cuda" if USE_GPU else "cpu"
        compute_type = "float16" if USE_GPU else "int8"

        model = WhisperModel(model_name, device=DEVICE, compute_type = compute_type)

        waveform, sample_rate = torchaudio.load(wav_path)
        chunks = chunk_audio(waveform, sample_rate)

        transcripts = []
        for i, chunk in enumerate(chunks):
            transcript = transcribe_chunk(chunk, sample_rate, model, i)
            transcripts.append(transcript)
        
        full_transcript = " ".join([t.strip() for t in transcripts if t.strip()])
        if not full_transcript:
            print("[Error] No speech detected in any chunk. Empty transcript.")
            return None, None
        
        output_path = str(wav_path).replace(".wav", "_transcript.txt")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(full_transcript)

        print(f"\nTranscript saved to: {output_path}")
        print(f"[DEBUG] Returning transcript of length: {len(full_transcript)}")
        return full_transcript, output_path
    
    except Exception as e:
        print(f"[Error in transcribe_audio]:{e}")
        return None, None

def process_and_transcribe(file_path):
    try:
  
        wav_mp3 = preprocess_file(file_path)
        if not wav_mp3:
            print(f"[BG ERROR] Preprocessing failed for {file_path}")
            return

        wav_path, mp3_path = wav_mp3


        transcript, transcript_path = transcribe_audio(wav_path)
        print(f"[DEBUG] transcript type: {type(transcript)}, length: {len(transcript) if transcript else 'None'}")
        print(f"[DEBUG] transcript_path: {transcript_path}")

        print(f"[DEBUG] Transcript length after transcribe_audio: {len(transcript) if transcript else 'None'}")
        if not transcript:
            print(f"[BG ERROR] Transcription failed for {wav_path}")
            return
        
    except Exception as e:
        print(f"[BG ERROR] Unhandled exception in process_and_transcribe: {e}")
        import traceback
        traceback.print_exc()