import mimetypes
import boto3
import os
import subprocess
import time
import requests
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()

# Configuration AWS
AWS_REGION = os.getenv("REGION", "us-east-1")
BUCKET_NAME = "tp-eval"  # <-- Mettez votre bucket S3 ici

# Initialiser session & clients
session = boto3.Session(
    aws_access_key_id=os.getenv("ACCESS_KEY"),
    aws_secret_access_key=os.getenv("SECRET_KEY"),
    region_name=AWS_REGION
)

rekognition = session.client("rekognition")
s3 = session.client("s3")
transcribe = session.client("transcribe")


def check_filetype(file_path):
    """
    Détermine si un fichier est une image ou une vidéo.
    Retourne 'image' si c'est une image,
    'video' si c'est une vidéo,
    sinon None.
    """
    mime_type, _ = mimetypes.guess_type(file_path)
    if mime_type:
        if mime_type.startswith("image"):
            return "image"
        elif mime_type.startswith("video"):
            return "video"
    return None


def extract_snapshot_with_ffmpeg(video_path, snapshot_path, time_sec=1):
    """
    Extrait une image d'une vidéo (snapshot) à time_sec (en secondes)
    en utilisant ffmpeg via subprocess.
    """
    try:
        # Commande ffmpeg :
        #  -ss {time_sec} : aller à la position time_sec
        #  -frames:v 1 : extraire 1 frame
        #  -y : overwrite du fichier de sortie
        command = [
            "ffmpeg",
            "-i", video_path,
            "-ss", str(time_sec),
            "-frames:v", "1",
            snapshot_path,
            "-y"
        ]
        subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except Exception as e:
        print(f"❌ Erreur lors de l'extraction du snapshot via ffmpeg : {e}")
        return False


def transcribe_video_s3(s3_bucket, s3_key, language_code="fr-FR"):
    """
    Lance une transcription AWS Transcribe asynchrone sur une vidéo
    stockée dans un bucket S3, attend la fin du job, et renvoie le texte transcrit.
    
    Paramètres :
    - s3_bucket : nom du bucket
    - s3_key : chemin/nom du fichier dans le bucket
    - language_code : code langue ("fr-FR", "en-US", etc.)
    
    Retourne : une chaîne de caractères (transcription) ou None en cas d'erreur.
    """

    # On crée un nom de job unique (par ex : "transcribe_{timestamp}")
    job_name = f"transcribe_{int(time.time())}"

    # Récupérer l'extension du fichier pour déterminer le format
    media_format = s3_key.split(".")[-1].lower()
    if media_format not in ["mp4", "mov", "avi"]:
        # Forcer un format par défaut si besoin
        media_format = "mp4"

    try:
        response = transcribe.start_transcription_job(
            TranscriptionJobName=job_name,
            LanguageCode=language_code,
            MediaFormat=media_format,
            Media={
                "MediaFileUri": f"s3://{s3_bucket}/{s3_key}"
            }
            # IMPORTANT : on n'utilise pas OutputBucketName=None
            # Sans OutputBucketName, AWS Transcribe stocke le résultat dans son propre bucket
        )
    except Exception as e:
        print(f"❌ Erreur lors du start_transcription_job : {e}")
        return None

    # Attendre la fin du job
    while True:
        job_status_resp = transcribe.get_transcription_job(TranscriptionJobName=job_name)
        status = job_status_resp["TranscriptionJob"]["TranscriptionJobStatus"]
        if status in ["COMPLETED", "FAILED"]:
            break
        time.sleep(5)

    if status == "FAILED":
        print("❌ Job de transcription échoué.")
        return None

    # Récupération du TranscriptFileUri
    transcript_file_uri = job_status_resp["TranscriptionJob"]["Transcript"]["TranscriptFileUri"]
    # Télécharger le fichier JSON de la transcription
    try:
        r = requests.get(transcript_file_uri)
        r.raise_for_status()
        transcript_json = r.json()
        # On suppose qu'il y a au moins un résultat
        transcript_text = transcript_json["results"]["transcripts"][0]["transcript"]
        return transcript_text
    except Exception as e:
        print(f"❌ Erreur lors de la récupération du JSON de transcription : {e}")
        return None


def moderate_and_generate_hashtags(file_path):
    """
    Analyse un fichier (image ou vidéo) pour détecter du contenu inapproprié,
    génère des hashtags, et si c'est une vidéo safe => transcrit l'audio.
    
    Retourne (is_safe, hashtags, file_type, transcription).
      - is_safe (bool)
      - hashtags (list de strings)
      - file_type ("image" ou "video" ou None)
      - transcription (str ou None)
    """
    file_type = check_filetype(file_path)
    if file_type not in ["image", "video"]:
        print("❌ Type de fichier non reconnu ou non pris en charge.")
        return False, [], None, None

    if file_type == "image":
        # -----------------------------------------
        # Analyse IMAGE (labels + modération)
        # -----------------------------------------
        print("🔹 Analyse de l'image avec AWS Rekognition...")

        image_key = f"uploaded_images/{os.path.basename(file_path)}"
        try:
            s3.upload_file(file_path, BUCKET_NAME, image_key)
            print(f"✅ Image uploadée : s3://{BUCKET_NAME}/{image_key}")
        except Exception as e:
            print(f"❌ Erreur d'upload : {e}")
            return False, [], file_type, None

        # Détection des labels
        response_labels = rekognition.detect_labels(
            Image={"S3Object": {"Bucket": BUCKET_NAME, "Name": image_key}},
            MaxLabels=10,
            MinConfidence=50
        )
        labels = response_labels.get("Labels", [])
        sorted_labels = sorted(labels, key=lambda x: x["Confidence"], reverse=True)
        hashtags = [f"#{label['Name'].replace(' ', '')}" for label in sorted_labels]

        # Détection de contenu inapproprié
        response_moderation = rekognition.detect_moderation_labels(
            Image={"S3Object": {"Bucket": BUCKET_NAME, "Name": image_key}}
        )
        moderation_labels = response_moderation.get("ModerationLabels", [])

        if moderation_labels:
            print("❌ Contenu inapproprié détecté :")
            for m in moderation_labels:
                print(f"- {m['Name']} ({m['Confidence']:.2f}%)")
            print("⛔ IMAGE REFUSÉE ⛔")
            return False, [], file_type, None
        else:
            print("✅ Aucune modération négative. IMAGE OK.")
            return True, hashtags, file_type, None

    else:
        # -----------------------------------------
        # Analyse VIDÉO (1 snapshot + modération)
        # -----------------------------------------
        print("🔹 Analyse d'une vidéo via une snapshot extraite avec ffmpeg...")

        # 1) Upload de la vidéo sur S3
        video_key = f"uploaded_videos/{os.path.basename(file_path)}"
        try:
            s3.upload_file(file_path, BUCKET_NAME, video_key)
            print(f"✅ Vidéo uploadée : s3://{BUCKET_NAME}/{video_key}")
        except Exception as e:
            print(f"❌ Erreur d'upload de la vidéo : {e}")
            return False, [], file_type, None

        # 2) Extraire une image depuis la vidéo
        snapshot_path = f"snapshot_{os.path.splitext(os.path.basename(file_path))[0]}.jpg"
        success_snapshot = extract_snapshot_with_ffmpeg(file_path, snapshot_path, time_sec=1)
        if not success_snapshot:
            print("❌ Échec de l'extraction de la snapshot vidéo.")
            return False, [], file_type, None

        # 3) Upload de la snapshot sur S3
        snapshot_key = f"uploaded_images/{os.path.basename(snapshot_path)}"
        try:
            s3.upload_file(snapshot_path, BUCKET_NAME, snapshot_key)
            print(f"✅ Snapshot uploadée : s3://{BUCKET_NAME}/{snapshot_key}")
        except Exception as e:
            print(f"❌ Erreur d'upload de la snapshot : {e}")
            os.remove(snapshot_path)
            return False, [], file_type, None

        # 4) Détection des labels via la snapshot
        response_labels = rekognition.detect_labels(
            Image={"S3Object": {"Bucket": BUCKET_NAME, "Name": snapshot_key}},
            MaxLabels=10,
            MinConfidence=50
        )
        labels = response_labels.get("Labels", [])
        sorted_labels = sorted(labels, key=lambda x: x["Confidence"], reverse=True)
        hashtags = [f"#{label['Name'].replace(' ', '')}" for label in sorted_labels]

        # 5) Détection du contenu inapproprié
        response_moderation = rekognition.detect_moderation_labels(
            Image={"S3Object": {"Bucket": BUCKET_NAME, "Name": snapshot_key}}
        )
        moderation_labels = response_moderation.get("ModerationLabels", [])

        # Nettoyage snapshot local
        os.remove(snapshot_path)

        if moderation_labels:
            print("❌ Contenu inapproprié détecté dans la snapshot :")
            for m in moderation_labels:
                print(f"- {m['Name']} ({m['Confidence']:.2f}%)")
            print("⛔ VIDÉO REFUSÉE ⛔")
            return False, [], file_type, None
        else:
            print("✅ Aucune modération négative. VIDÉO OK.")

            # 6) TRANSCRIPTION de la vidéo en français (ou toute autre langue) 
            print("🔹 Lancement de la transcription audio (AWS Transcribe, FR)...")
            transcription_text = transcribe_video_s3(BUCKET_NAME, video_key, language_code="fr-FR")
            if transcription_text:
                print("✅ Transcription réussie.")
            else:
                print("❌ Échec ou absence de transcription.")

            return True, hashtags, file_type, transcription_text
