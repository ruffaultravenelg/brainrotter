from gtts import gTTS
import random
import os
import ffmpeg
from faster_whisper import WhisperModel
import argparse

# Constants in camelCase
TEMP_AUDIO_FILE = "audio.mp3"
VIDEO_DATABASE = "./bases"
TEMP_SRT_FILE = "sub.srt"
FINAL_VIDEO_FILE = "final.mp4"

def generateAudio(fileName, text, lang="en", tld="com"):
    """
    Convert text to audio using gTTS and save it to fileName.
    """
    tts = gTTS(text=text, lang=lang, tld=tld)
    tts.save(fileName)
    print("[LOG] Audio saved to", fileName)

def getRandomVideo(folder):
    """
    Select a random video file from the given folder.
    """
    videoFiles = [f for f in os.listdir(folder) if f.endswith(('.mp4', '.avi', '.mov'))]
    if not videoFiles:
        raise FileNotFoundError("No video files found in the videoDatabase folder.")
    selectedVideo = os.path.join(folder, random.choice(videoFiles))
    print(f"[LOG] Video selected: \"{selectedVideo}\"")
    return selectedVideo

def generateSubtitles(audioPath, maxWordsPerSegment=5):
    """
    Transcribe the audio and split the text into subtitle segments.
    """
    model = WhisperModel("small", compute_type="float32")
    segments, info = model.transcribe(audioPath)
    language = info.language
    print("[LOG] Transcription language:", language)
    
    newSegments = []
    for segment in segments:
        words = segment.text.split()
        startTime = segment.start
        endTime = segment.end
        durationPerWord = (endTime - startTime) / len(words) if words else 0

        for i in range(0, len(words), maxWordsPerSegment):
            subText = " ".join(words[i:i + maxWordsPerSegment])
            subStart = startTime + i * durationPerWord
            subEnd = min(startTime + (i + maxWordsPerSegment) * durationPerWord, endTime)
            newSegments.append((subStart, subEnd, subText))
    
    print("[LOG] Generated subtitle segments:")
    for subStart, subEnd, subText in newSegments:
        print(f"\t[{subStart:.2f}s -> {subEnd:.2f}s] {subText}")
        
    return language, newSegments

def formatTime(seconds):
    """
    Convert seconds into SRT format (HH:MM:SS,mmm).
    """
    millisec = int((seconds % 1) * 1000)
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    sec = int(seconds % 60)
    return f"{hours:02}:{minutes:02}:{sec:02},{millisec:03}"

def generateSubtitleFile(fileName, segments):
    """
    Generate an SRT file from subtitle segments.
    """
    text = ""
    for index, segment in enumerate(segments):
        segmentStart = formatTime(segment[0])
        segmentEnd = formatTime(segment[1])
        text += f"{index + 1}\n{segmentStart} --> {segmentEnd}\n{segment[2]}\n\n"

    with open(fileName, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"[LOG] SRT file generated: {fileName}")

def createFinalClip(inputFile, audioFile, subtitleFile, outputFile):
    """
    Create the final video in a single ffmpeg pass:
      - Extract a random clip from the video matching the audio duration.
      - Apply a portrait crop (9:16).
      - Overlay subtitles.
      - Integrate the audio.
    """
    # Get video duration
    probeVideo = ffmpeg.probe(inputFile)
    videoStream = next((stream for stream in probeVideo["streams"] if stream["codec_type"] == "video"), None)
    videoDuration = float(videoStream["duration"]) if videoStream else 0

    # Get audio duration
    probeAudio = ffmpeg.probe(audioFile)
    audioStream = next((stream for stream in probeAudio["streams"] if stream["codec_type"] == "audio"), None)
    audioDuration = float(audioStream["duration"]) if audioStream else 0

    if videoDuration < audioDuration:
        raise ValueError("The video must be at least as long as the audio.")

    # Determine a random start time in the video
    startTime = random.uniform(0, videoDuration - audioDuration)

    # Load the video and extract a clip with the audio's duration
    video = ffmpeg.input(inputFile, ss=startTime, t=audioDuration)
    # Apply portrait crop (9:16)
    video = video.filter("crop", "in_h*9/16", "in_h", "(in_w-out_w)/2", 0)
    # Add subtitles directly
    video = video.filter("subtitles", subtitleFile)

    # Load the audio
    audio = ffmpeg.input(audioFile)

    # Generate the final video in a single pass
    (
        ffmpeg
        .output(video, audio, outputFile, vcodec="libx264", acodec="aac", video_bitrate="5000k", preset="slow", crf=18)
        .run(overwrite_output=True, quiet=True, capture_stdout=True, capture_stderr=True)
    )
    print(f"[LOG] Final video created: {outputFile}")

def generateVideo(text):
    """
    Complete pipeline:
      1. Generate audio.
      2. Transcribe and generate subtitles.
      3. Create the final video (random clip, audio, subtitles) in a single ffmpeg pass.
      4. Clean up temporary files.
    """
    # 1. Generate audio
    generateAudio(TEMP_AUDIO_FILE, text)
    
    # 2. Transcribe audio and generate SRT file
    language, segments = generateSubtitles(TEMP_AUDIO_FILE)
    generateSubtitleFile(TEMP_SRT_FILE, segments)
    
    # 3. Select a random video and create the final video
    videoFile = getRandomVideo(VIDEO_DATABASE)
    createFinalClip(videoFile, TEMP_AUDIO_FILE, TEMP_SRT_FILE, FINAL_VIDEO_FILE)
    
    # 4. Delete temporary files
    os.remove(TEMP_AUDIO_FILE)
    os.remove(TEMP_SRT_FILE)
    print("[LOG] Temporary files deleted.")

if __name__ == "__main__":
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="Brainrot video generator"
    )
    parser.add_argument("-o", "--output", type=str, help="Output video file name", default=FINAL_VIDEO_FILE)
    parser.add_argument("-s", "--script", type=str, help="Path to the script text file", default=None)
    parser.add_argument("-v", "--videos", type=str, help="Path to the folder containing video files", default=VIDEO_DATABASE)
    args = parser.parse_args()
    
    # Override the default values if provided via command-line.
    FINAL_VIDEO_FILE = args.output
    VIDEO_DATABASE = args.videos
    
    # Check if the script file is provided.
    if args.script is None:
        print("Please provide a script text file.")
        exit()
    
    # Read the script text from the file.
    with open(args.script, "r", encoding="utf-8") as f:
        scriptText = f.read()

    # Generate the video.
    generateVideo(scriptText)
