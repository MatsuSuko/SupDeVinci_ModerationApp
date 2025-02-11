import os
from dotenv import load_dotenv
import streamlit as st
from PIL import Image
import moderation

# Charger variables d'environnement
load_dotenv()

st.set_page_config(page_title="Content Moderator Pro", page_icon="🛡️", layout="wide")

st.title("🛡️ Content Moderator Pro")
st.markdown("""
Bienvenue dans **Content Moderator Pro** !  
Cette application utilise **AWS Rekognition** pour analyser **images** et **vidéos**  
afin de détecter d'éventuels contenus inappropriés. 

**Nouveauté** : si la vidéo est approuvée, on récupère également sa **transcription** via AWS Transcribe
en configurant la langue en français (**fr-FR**).
""")

# Barre latérale : Configuration AWS
st.sidebar.header("⚙️ Configuration AWS")

default_access_key = os.getenv("ACCESS_KEY", "")
default_secret_key = os.getenv("SECRET_KEY", "")
default_region = os.getenv("REGION", "us-east-1")

aws_access_key = st.sidebar.text_input("🔑 AWS Access Key", value=default_access_key, type="password")
aws_secret_key = st.sidebar.text_input("🔐 AWS Secret Key", value=default_secret_key, type="password")
aws_region = st.sidebar.selectbox("🌍 Région AWS", ["us-east-1", "eu-west-3", "ap-southeast-1"], index=0)

if st.sidebar.button("🔄 Charger credentials depuis .env"):
    if default_access_key and default_secret_key:
        st.sidebar.success("✅ Credentials chargés depuis .env")
    else:
        st.sidebar.error("⚠️ Aucun credentials trouvé dans .env")

if aws_access_key and aws_secret_key:
    os.environ["ACCESS_KEY"] = aws_access_key
    os.environ["SECRET_KEY"] = aws_secret_key
    os.environ["REGION"] = aws_region
else:
    st.sidebar.warning("⚠️ Les credentials AWS sont requis pour utiliser l'application.")

# Upload d'un fichier
uploaded_file = st.file_uploader(
    "📤 Téléchargez une image (.jpg, .png) ou une vidéo (.mp4, .mov, .avi) pour analyse",
    type=["jpg", "png", "jpeg", "mp4", "mov", "avi"]
)

if uploaded_file is not None:
    # Sauvegarde temporaire du fichier
    file_path = f"temp_{uploaded_file.name}"
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    st.write("🔍 Analyse en cours...")
    is_safe, hashtags, file_type, transcription = moderation.moderate_and_generate_hashtags(file_path)

    if is_safe:
        st.success("✅ Le contenu est approprié et peut être affiché.")
        st.write("📌 **Hashtags générés :**", ", ".join(hashtags))

        if file_type == "image":
            st.image(Image.open(file_path), caption="Image Analysée", use_container_width=True)
        elif file_type == "video":
            st.video(file_path)

            if transcription:
                st.write("---")
                st.subheader("📝 Transcription (FR)")
                st.write(transcription)
            else:
                st.info("Aucune transcription disponible ou erreur lors de la transcription.")
    else:
        if file_type == "image":
            st.error("🚨 Cette image contient du contenu inapproprié.")
        elif file_type == "video":
            st.error("🚨 Cette vidéo contient du contenu inapproprié.")
        else:
            st.error("🚨 Fichier non pris en charge ou erreur.")

    # Nettoyage local
    os.remove(file_path)
