from gtts import gTTS
import random
import os
import ffmpeg
from faster_whisper import WhisperModel

# Constants
TEMP_AUDIO_FILE = "audio.mp3"
VIDEO_DATABASE = "./bases"
TEMP_VIDEO_FILE = "temp.mp4"
SRT_FILE = "sub.srt"
FINAL_VIDEO_FILE = "final.mp4"

def generateAudio(filename, text, lang='fr', tld='com'):
    """
    Convert text to speech and save it as an audio file.
    :param filename: Output audio file name.
    :param text: Text to convert into speech.
    :param lang: Language code for TTS.
    :param tld: Top-level domain for TTS voice selection.
    """
    tts = gTTS(text=text, lang=lang, tld=tld)
    tts.save(filename)
    print("[LOG] Audio saved as", filename)

def createRandomClip(inputFile, audioFile, outputFile):
    """
    Extract a random video clip and overlay an audio file using FFmpeg.
    The video is cropped to portrait mode (9:16) while maintaining quality.
    :param inputFile: Path to the source video file.
    :param audioFile: Path to the audio file.
    :param outputFile: Output video file name.
    """
    # Get the duration of the video with FFmpeg
    probeVideo = ffmpeg.probe(inputFile)
    videoStream = next((stream for stream in probeVideo["streams"] if stream["codec_type"] == "video"), None)
    videoDuration = float(videoStream["duration"]) if videoStream else 0

    # Get the duration of the audio with FFmpeg
    probeAudio = ffmpeg.probe(audioFile)
    audioStream = next((stream for stream in probeAudio["streams"] if stream["codec_type"] == "audio"), None)
    audioDuration = float(audioStream["duration"]) if audioStream else 0

    if videoDuration < audioDuration:
        raise ValueError("The video must be at least as long as the audio duration.")

    # Determine a random start point
    startTime = random.uniform(0, videoDuration - audioDuration)

    # Load the video and apply the 9:16 crop
    video = (
        ffmpeg
        .input(inputFile, ss=startTime, t=audioDuration)  # Random clip
        .filter("crop", "in_h*9/16", "in_h", "(in_w-out_w)/2", 0)  # Portrait mode crop
    )

    # Load the audio
    audio = ffmpeg.input(audioFile)

    # Merge the video and audio into the final output
    (
        ffmpeg
        .output(video, audio, outputFile, vcodec="libx264", acodec="aac", video_bitrate="5000k", preset="slow", crf=18)
        .run(overwrite_output=True, quiet=True, capture_stdout=True, capture_stderr=True)
    )

    print(f"[LOG] Successfully created a {audioDuration}-second random clip: {outputFile}")

def getRandomVideo(folder):
    """
    Select a random video file from a given folder.
    :param folder: Path to the folder containing video files.
    :return: Path to a randomly selected video file.
    """
    videoFiles = [f for f in os.listdir(folder) if f.endswith(('.mp4', '.avi', '.mov'))]
    if not videoFiles:
        raise FileNotFoundError("No video files found in the VIDEO_DATABASE folder.")
    return os.path.join(folder, random.choice(videoFiles))

def generateSubtitles(audioPath, maxWordsPerSegment=5):
    """
    Generate subtitles by transcribing an audio file.
    :param audioPath: Path to the audio file.
    :param maxWordsPerSegment: Maximum number of words per subtitle segment.
    :return: Language of transcription and segmented subtitles.
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

    print("[LOG] Segments:")
    for subStart, subEnd, subText in newSegments:
        print(f"\t[{subStart:.2f}s -> {subEnd:.2f}s] {subText}")
    
    return language, newSegments

def formatTime(seconds):
    """
    Convert seconds into SRT time format (HH:MM:SS,mmm).
    :param seconds: Time in seconds.
    :return: Formatted SRT timestamp.
    """
    millisec = int((seconds % 1) * 1000)
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    sec = int(seconds % 60)
    return f"{hours:02}:{minutes:02}:{sec:02},{millisec:03}"

def generateSubtitleFile(file, segments):
    """
    Create an SRT subtitle file from transcribed segments.
    :param file: Output subtitle file name.
    :param segments: List of subtitle segments.
    """
    text = ""
    for index, segment in enumerate(segments):
        segmentStart = formatTime(segment[0])
        segmentEnd = formatTime(segment[1])
        text += f"{index + 1}\n{segmentStart} --> {segmentEnd}\n{segment[2]}\n\n"

    with open(file, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"[LOG] SRT file generated: {file}")

def addSubtitleToVideo(inputVideo, outputVideo, subtitleFile):
    """
    Overlay subtitles onto a video using FFmpeg.
    :param inputVideo: Path to the input video file.
    :param outputVideo: Path to the output video file.
    :param subtitleFile: Path to the subtitle (SRT) file.
    """
    stream = ffmpeg.input(inputVideo)
    stream = ffmpeg.output(stream, outputVideo, vf=f"subtitles={subtitleFile}", vcodec="libx264")
    ffmpeg.run(stream, overwrite_output=True, quiet=True, capture_stdout=True, capture_stderr=True)

def generate(text):
    """
    Generate a final video with subtitles from input text.
    :param text: Input text to be converted into speech and embedded in the video.
    """
    generateAudio(TEMP_AUDIO_FILE, text)
    createRandomClip(getRandomVideo(VIDEO_DATABASE), TEMP_AUDIO_FILE, TEMP_VIDEO_FILE)
    language, segments = generateSubtitles(TEMP_AUDIO_FILE)
    generateSubtitleFile(SRT_FILE, segments)
    addSubtitleToVideo(TEMP_VIDEO_FILE, FINAL_VIDEO_FILE, SRT_FILE)
    os.remove(TEMP_AUDIO_FILE)
    os.remove(TEMP_VIDEO_FILE)
    os.remove(SRT_FILE)
    print("[LOG] Temporary files deleted.")


if __name__ == "__main__":
    text = "On sait depuis longtemps que travailler avec du texte lisible et contenant du sens est source de distractions, et empêche de se concentrer sur la mise en page elle-même. L'avantage du Lorem Ipsum sur un texte générique comme 'Du texte. Du texte. Du texte.' est qu'il possède une distribution de lettres plus ou moins normale, et en tout cas comparable avec celle du français standard. "
    generate(text)