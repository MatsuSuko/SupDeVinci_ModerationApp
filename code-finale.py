import cv2
import boto3
import os
import mimetypes
import time
from dotenv import load_dotenv


# 📌 Charger les variables d'environnement
load_dotenv()



# 📌 Configuration AWS
AWS_REGION = "us-east-1"
BUCKET_NAME = "tp-eval1"
S3_IMAGE_KEY = "uploaded_images/frame.jpg"



# 📌 Configuration du fichier
FILE_PATH = "./assets/selfie_with_kanye-west.png"
FRAME_IMAGE_PATH = "frame.jpg"
AUDIO_PATH = "audio.mp3"
SUBTITLES_PATH = "subtitles.srt"



# 📌 Initialisation des clients AWS
session = boto3.Session(
    aws_access_key_id=os.getenv("ACCESS_KEY"),
    aws_secret_access_key=os.getenv("SECRET_KEY"),
    region_name=AWS_REGION
)
rekognition = session.client("rekognition")
s3 = session.client("s3")
transcribe = session.client("transcribe")



# 📌 Vérifier si un fichier est une image ou une vidéo
def check_filetype(file_path):
    """Détermine si le fichier est une image ou une vidéo."""
    mime_type, _ = mimetypes.guess_type(file_path)
    
    if mime_type:
        if mime_type.startswith("image"):
            return "image"
        elif mime_type.startswith("video"):
            return "video"
    return None



# 📌 Extraire une image depuis une vidéo 🎥
def extract_frame(video_path, output_image, time_sec=2):
    """Extrait une image d'une vidéo MP4 à un temps donné."""
    print(f"🔹 Extraction d'une frame depuis la vidéo {video_path}...")

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print("❌ Erreur : Impossible d'ouvrir la vidéo.")
        return False

    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_number = int(fps * time_sec)

    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
    ret, frame = cap.read()
    
    if ret:
        cv2.imwrite(output_image, frame)
        print(f"✅ Image extraite : {output_image}")
        cap.release()
        return True
    else:
        print("❌ Erreur : Impossible d'extraire une image.")
        cap.release()
        return False



# 📌 Modération d'image, Détection de Célébrités et Génération de Hashtags 🚨
def analyze_image(image_path):
    """Analyse une image pour détecter du contenu inapproprié, identifier des célébrités et générer des hashtags."""
    print("🔹 Analyse de l'image avec AWS Rekognition...")

    try:
        s3.upload_file(image_path, BUCKET_NAME, S3_IMAGE_KEY)
        print(f"✅ Image uploadée : s3://{BUCKET_NAME}/{S3_IMAGE_KEY}")
    except Exception as e:
        print(f"❌ Erreur d'upload : {e}")
        return False


    # 🔍 Détection des labels (objets)
    response = rekognition.detect_labels(
        Image={"S3Object": {"Bucket": BUCKET_NAME, "Name": S3_IMAGE_KEY}},
        MaxLabels=10,  
        MinConfidence=50  
    )

    labels = response.get("Labels", [])
    print("\n📊 Statistiques de Reconnaissance AWS Rekognition :")
    print(f"✅ Nombre total de labels détectés : {len(labels)}\n")

    sorted_labels = sorted(labels, key=lambda x: x["Confidence"], reverse=True)
    hashtags = [f"#{label['Name'].replace(' ', '')}" for label in sorted_labels]  

    for label in sorted_labels:
        print(f"🔹 {label['Name']} ({label['Confidence']:.2f}%)")


    # 🔍 Détection de contenu inapproprié
    moderation_response = rekognition.detect_moderation_labels(
        Image={"S3Object": {"Bucket": BUCKET_NAME, "Name": S3_IMAGE_KEY}}
    )

    moderation_labels = moderation_response.get("ModerationLabels", [])

    print("\n🚨 Résultat de la Modération :")
    if not moderation_labels:
        print("✅ Aucun contenu inapproprié détecté.")
        print(f"🎯 Hashtags suggérés : {' '.join(hashtags)}")
    else:
        print("❌ Contenu inapproprié détecté :")
        for label in moderation_labels:
            print(f" - {label['Name']} ({label['Confidence']:.2f}%)")
        print("⛔ NE PASSE PAS ⛔")
        return False  


    # 🔍 Détection des célébrités 👨‍🎤👩‍🎤
    celebrity_response = rekognition.recognize_celebrities(
        Image={"S3Object": {"Bucket": BUCKET_NAME, "Name": S3_IMAGE_KEY}}
    )

    celebrities = celebrity_response.get("CelebrityFaces", [])

    print("\n🌟 Reconnaissance de célébrités :")
    if celebrities:
        for celeb in celebrities:
            print(f"✨ {celeb['Name']} détecté(e) avec {celeb['MatchConfidence']:.2f}% de confiance.")
    else:
        print("🔍 Aucune célébrité détectée.")

    return True  



# 📌 Générer des sous-titres avec AWS Transcribe 🎤
def generate_subtitles(video_path):
    """Convertit l'audio d'une vidéo en sous-titres grâce à AWS Transcribe."""
    print("🔹 Extraction de l'audio...")
    
    os.system(f"ffmpeg -i {video_path} -q:a 0 -map a {AUDIO_PATH} -y")


    # 📤 Uploader l'audio sur S3
    audio_s3_key = "audio/audio.mp3"
    try:
        s3.upload_file(AUDIO_PATH, BUCKET_NAME, audio_s3_key)
        print(f"✅ Audio uploadé : s3://{BUCKET_NAME}/{audio_s3_key}")
    except Exception as e:
        print(f"❌ Erreur d'upload de l'audio : {e}")
        return False


    # 🎤 Lancer la transcription
    job_name = f"TranscriptionJob-{int(time.time())}"
    transcribe.start_transcription_job(
        TranscriptionJobName=job_name,
        Media={"MediaFileUri": f"s3://{BUCKET_NAME}/{audio_s3_key}"},
        MediaFormat="mp3",
        LanguageCode="fr-FR"
    )

    print("⏳ Transcription en cours...")
    while True:
        status = transcribe.get_transcription_job(TranscriptionJobName=job_name)
        if status["TranscriptionJob"]["TranscriptionJobStatus"] in ["COMPLETED", "FAILED"]:
            break
        print("🔄 En attente de la transcription...")
        time.sleep(5)

    if status["TranscriptionJob"]["TranscriptionJobStatus"] == "COMPLETED":
        transcript_url = status["TranscriptionJob"]["Transcript"]["TranscriptFileUri"]
        print(f"✅ Transcription terminée ! Résultat ici : {transcript_url}")
    else:
        print("❌ Erreur dans la transcription.")



# 📌 Programme Principal
if __name__ == "__main__":
    file_type = check_filetype(FILE_PATH)

    if file_type == "image":
        print("🖼️ C'est une image, début de l'analyse...")
        analyze_image(FILE_PATH)
    
    elif file_type == "video":
        print(f"🎥 Fichier vidéo détecté : {FILE_PATH} ! Extraction d’une image...")
        if extract_frame(FILE_PATH, FRAME_IMAGE_PATH):
            if analyze_image(FRAME_IMAGE_PATH):  
                generate_subtitles(FILE_PATH)

    else:
        print("❌ Type de fichier non reconnu.")
