from gtts import gTTS
import random
import os
import ffmpeg
from faster_whisper import WhisperModel

# Constantes
TEMP_AUDIO_FILE = "audio.mp3"
VIDEO_DATABASE = "./bases"
SRT_FILE = "sub.srt"
FINAL_VIDEO_FILE = "final.mp4"

def generateAudio(filename, text, lang='fr', tld='com'):
    """
    Convertir le texte en audio avec gTTS et sauvegarder dans filename.
    """
    tts = gTTS(text=text, lang=lang, tld=tld)
    tts.save(filename)
    print("[LOG] Audio sauvegardé dans", filename)

def getRandomVideo(folder):
    """
    Sélectionner une vidéo aléatoire dans le dossier donné.
    """
    videoFiles = [f for f in os.listdir(folder) if f.endswith(('.mp4', '.avi', '.mov'))]
    if not videoFiles:
        raise FileNotFoundError("Aucun fichier vidéo trouvé dans le dossier VIDEO_DATABASE.")
    selected_video = os.path.join(folder, random.choice(videoFiles))
    print("[LOG] Vidéo sélectionnée :", selected_video)
    return selected_video

def generateSubtitles(audioPath, maxWordsPerSegment=5):
    """
    Transcrire l'audio et segmenter le texte en sous-titres.
    """
    model = WhisperModel("small", compute_type="float32")
    segments, info = model.transcribe(audioPath)
    language = info.language
    print("[LOG] Langue de la transcription :", language)
    
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
    
    print("[LOG] Segments générés :")
    for subStart, subEnd, subText in newSegments:
        print(f"\t[{subStart:.2f}s -> {subEnd:.2f}s] {subText}")
        
    return language, newSegments

def formatTime(seconds):
    """
    Convertir des secondes en format SRT : HH:MM:SS,mmm.
    """
    millisec = int((seconds % 1) * 1000)
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    sec = int(seconds % 60)
    return f"{hours:02}:{minutes:02}:{sec:02},{millisec:03}"

def generateSubtitleFile(file, segments):
    """
    Générer un fichier SRT à partir des segments de sous-titres.
    """
    text = ""
    for index, segment in enumerate(segments):
        segmentStart = formatTime(segment[0])
        segmentEnd = formatTime(segment[1])
        text += f"{index + 1}\n{segmentStart} --> {segmentEnd}\n{segment[2]}\n\n"

    with open(file, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"[LOG] Fichier SRT généré : {file}")

def createFinalClip(inputFile, audioFile, subtitleFile, outputFile):
    """
    Créer la vidéo finale en une seule passe FFmpeg :
      - Extrait un clip aléatoire de la vidéo de la durée de l'audio.
      - Applique un crop pour obtenir un format portrait (9:16).
      - Intègre l'audio.
      - Ajoute les sous-titres via le filtre 'subtitles'.
    """
    # Récupérer la durée de la vidéo
    probeVideo = ffmpeg.probe(inputFile)
    videoStream = next((stream for stream in probeVideo["streams"] if stream["codec_type"] == "video"), None)
    videoDuration = float(videoStream["duration"]) if videoStream else 0

    # Récupérer la durée de l'audio
    probeAudio = ffmpeg.probe(audioFile)
    audioStream = next((stream for stream in probeAudio["streams"] if stream["codec_type"] == "audio"), None)
    audioDuration = float(audioStream["duration"]) if audioStream else 0

    if videoDuration < audioDuration:
        raise ValueError("La vidéo doit être au moins aussi longue que l'audio.")

    # Déterminer un point de départ aléatoire dans la vidéo
    startTime = random.uniform(0, videoDuration - audioDuration)

    # Charger la vidéo en extrayant le clip de la durée de l'audio
    video = ffmpeg.input(inputFile, ss=startTime, t=audioDuration)
    # Appliquer le crop en mode portrait (9:16)
    video = video.filter("crop", "in_h*9/16", "in_h", "(in_w-out_w)/2", 0)
    # Ajouter directement les sous-titres
    video = video.filter("subtitles", subtitleFile)

    # Charger l'audio
    audio = ffmpeg.input(audioFile)

    # Générer la vidéo finale en une seule passe
    (
        ffmpeg
        .output(video, audio, outputFile, vcodec="libx264", acodec="aac", video_bitrate="5000k", preset="slow", crf=18)
        .run(overwrite_output=True, quiet=True, capture_stdout=True, capture_stderr=True)
    )
    print(f"[LOG] Vidéo finale créée : {outputFile}")

def generate(text):
    """
    Pipeline complet :
      1. Génération de l'audio.
      2. Transcription et génération des sous-titres.
      3. Création de la vidéo finale (clip aléatoire, audio, sous-titres) en une seule passe FFmpeg.
      4. Nettoyage des fichiers temporaires.
    """
    # 1. Générer l'audio
    generateAudio(TEMP_AUDIO_FILE, text)
    
    # 2. Transcrire l'audio et générer le fichier SRT
    language, segments = generateSubtitles(TEMP_AUDIO_FILE)
    generateSubtitleFile(SRT_FILE, segments)
    
    # 3. Sélectionner une vidéo aléatoire et créer la vidéo finale en une seule passe
    videoFile = getRandomVideo(VIDEO_DATABASE)
    createFinalClip(videoFile, TEMP_AUDIO_FILE, SRT_FILE, FINAL_VIDEO_FILE)
    
    # 4. Supprimer les fichiers temporaires
    os.remove(TEMP_AUDIO_FILE)
    os.remove(SRT_FILE)
    print("[LOG] Fichiers temporaires supprimés.")

if __name__ == "__main__":
    text = (
        "On sait depuis longtemps que travailler avec du texte lisible et contenant du sens est source de distractions, "
        "et empêche de se concentrer sur la mise en page elle-même. L'avantage du Lorem Ipsum sur un texte générique "
        "comme 'Du texte. Du texte. Du texte.' est qu'il possède une distribution de lettres plus ou moins normale, "
        "et en tout cas comparable avec celle du français standard. "
    )
    generate(text)
