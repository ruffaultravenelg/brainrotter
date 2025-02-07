from gtts import gTTS
import random
import os
import ffmpeg
from faster_whisper import WhisperModel
import moviepy.editor as mpe
import argparse

# Constants in camelCase
TEMP_AUDIO_FILE = "audio.mp3"
VIDEO_DATABASE = "./bases"
TEMP_SRT_FILE = "sub.srt"
TEMP_VIDEO_FILE = "temp.mp4"
FINAL_VIDEO_FILE = "final.mp4"

def generateAudio(fileName, text, language="en", tld="com"):
    """
    Convert text to audio using gTTS and save it to fileName.
    """
    tts = gTTS(text=text, lang=language, tld=tld)
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

def generateSubtitles(audioPath, maxWordsPerSegment=5, language="fr"):
    """
    Transcribe the audio and split the text into subtitle segments.
    """
    model = WhisperModel("small", compute_type="float32")
    segments, info = model.transcribe(audioPath, language=language)
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

def generateClip(baseVideo, audioFile, subtitleFile, outputFile):
    """
    Génère un clip vidéo à partir de baseVideo dont la durée correspond à celle de audioFile.
    Le clip est rogné en format portrait (9:16) et les sous-titres sont ajoutés.
    Le fichier de sortie ne contient pas d'audio.
    """
    # Obtenir la durée du fichier audio
    probeAudio = ffmpeg.probe(audioFile)
    audioStream = next((stream for stream in probeAudio["streams"] if stream["codec_type"] == "audio"), None)
    if not audioStream:
        raise ValueError("Aucun flux audio trouvé dans le fichier audio.")
    audioDuration = float(audioStream["duration"])
    
    # Obtenir la durée de la vidéo de base
    probeVideo = ffmpeg.probe(baseVideo)
    videoStream = next((stream for stream in probeVideo["streams"] if stream["codec_type"] == "video"), None)
    if not videoStream:
        raise ValueError("Aucun flux vidéo trouvé dans la vidéo de base.")
    videoDuration = float(videoStream["duration"])
    
    if videoDuration < audioDuration:
        raise ValueError("La vidéo de base doit être au moins aussi longue que l'audio.")
    
    # Déterminer un point de départ aléatoire pour le clip
    startTime = random.uniform(0, videoDuration - audioDuration)
    
    # Extraire le clip de la vidéo de base avec la durée de l'audio
    video_clip = ffmpeg.input(baseVideo, ss=startTime, t=audioDuration)
    
    # Appliquer le rognage pour obtenir le format portrait (9:16)
    video_clip = video_clip.filter("crop", "in_h*9/16", "in_h", "(in_w-out_w)/2", 0)
    
    # Ajouter les sous-titres à partir du fichier de sous-titres
    video_clip = video_clip.filter("subtitles", subtitleFile)
    
    # Exporter la vidéo (sans audio)
    ffmpeg.output(
        video_clip, 
        outputFile, 
        vcodec="libx264", 
        video_bitrate="5000k", 
        preset="slow", 
        crf=18, 
        an=None  # Indique de ne pas inclure d'audio
    ).run(overwrite_output=True, quiet=True, capture_stderr=True, capture_stdout=True)  
    
    print(f"[LOG] Clip vidéo généré : {outputFile}")

def addAudio(baseVideo, audioFile, outputFile):
    """
    Ajoute la piste audio du fichier audioFile à la vidéo baseVideo.
    Le résultat final est enregistré dans outputFile.
    """
    my_clip = mpe.VideoFileClip(baseVideo, audio=False)
    audio_background = mpe.AudioFileClip(audioFile)
    final_clip = my_clip.set_audio(audio_background)
    final_clip.write_videofile(outputFile, verbose=False, logger=None)
    
    print(f"[LOG] Audio ajouté à la vidéo finale : {outputFile}")


def generateVideo(text, language):
    """
    Complete pipeline:
      1. Generate audio.
      2. Transcribe and generate subtitles.
      3. Create the final video (random clip, audio, subtitles) in a single ffmpeg pass.
      4. Clean up temporary files.
    """
    # 1. Generate audio
    generateAudio(TEMP_AUDIO_FILE, text, language=language)
    
    # 2. Transcribe audio and generate SRT file
    language, segments = generateSubtitles(TEMP_AUDIO_FILE, language=language)
    generateSubtitleFile(TEMP_SRT_FILE, segments)
    
    # 3. Select a random video and create the final video
    videoFile = getRandomVideo(VIDEO_DATABASE)

    # 4. Generate the clip with subtitles
    generateClip(videoFile, TEMP_AUDIO_FILE, TEMP_SRT_FILE, TEMP_VIDEO_FILE)
    
    # 5. Add audio to the clip
    addAudio(TEMP_VIDEO_FILE, TEMP_AUDIO_FILE, FINAL_VIDEO_FILE)

    # 6. Delete temporary files
    os.remove(TEMP_AUDIO_FILE)
    os.remove(TEMP_SRT_FILE)
    os.remove(TEMP_VIDEO_FILE)
    print("[LOG] Temporary files deleted.")

if __name__ == "__main__":
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="Brainrot video generator"
    )
    parser.add_argument("-o", "--output", type=str, help="Output video file name", default=FINAL_VIDEO_FILE)
    parser.add_argument("-s", "--script", type=str, help="Path to the script text file", default=None)
    parser.add_argument("-v", "--videos", type=str, help="Path to the folder containing video files", default=VIDEO_DATABASE)
    parser.add_argument("-l", "--language", type=str, help="Language used by the script (fr, en)", default="fr")
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
    print("[LOG] Script text loaded.")

    # Generate the video.
    generateVideo(scriptText, args.language)
