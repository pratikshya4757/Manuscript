"""Simple Streamlit frontend for the Manuscript OCR & Translation backend.

Run the FastAPI backend first (python run.py), then in a second terminal:
    streamlit run streamlit_app.py

This is a thin UI over the API — it does no OCR/translation itself, it just
uploads the image and target language to the backend and renders the JSON
response.
"""
import requests
import streamlit as st

BACKEND_URL_DEFAULT = "http://127.0.0.1:8000"

TARGET_LANGUAGES = {
    "English": "en",
    "French": "fr",
    "German": "de",
    "Spanish": "es",
    "Hindi": "hi",
    "Odia": "or",
    "Telugu": "te",
    "Bengali": "bn",
    "Tamil": "ta",
    "Kannada": "kn",
    "Malayalam": "ml",
    "Marathi": "mr",
    "Gujarati": "gu",
    "Punjabi": "pa",
    "Urdu": "ur",
    "Arabic": "ar",
    "Sanskrit": "sa",
}

# OCR needs to know the manuscript's script ahead of time (EasyOCR loads a
# distinct model per script). Odia isn't listed — EasyOCR has no Odia OCR
# model, so an Odia-script manuscript image can't be read yet (Odia still
# works fine as a translation target for text extracted from other scripts).
SOURCE_SCRIPTS = {
    "Auto (English)": "auto",
    "Hindi": "hi",
    "Marathi": "mr",
    "Sanskrit": "sa",
    "Telugu": "te",
    "Tamil": "ta",
    "Kannada": "kn",
    "Bengali": "bn",
    "Urdu": "ur",
    "Arabic": "ar",
}

st.set_page_config(page_title="Manuscript OCR & Translation", page_icon="📜", layout="wide")

st.title("📜 Manuscript OCR & Translation")
st.caption("Upload a historical manuscript image, pick a target language, and see the OCR + translation result.")

with st.sidebar:
    st.header("Settings")
    backend_url = st.text_input("Backend URL", value=BACKEND_URL_DEFAULT)
    st.markdown("Make sure the FastAPI backend is running:")
    st.code("python run.py", language="bash")

col_input, col_output = st.columns([1, 1.4], gap="large")

with col_input:
    st.subheader("1. Input")
    uploaded_file = st.file_uploader(
        "Manuscript image", type=["jpg", "jpeg", "png", "webp"]
    )
    if uploaded_file is not None:
        st.image(uploaded_file, caption="Preview", use_container_width=True)

    source_script_label = st.selectbox(
        "Manuscript script (helps OCR read it correctly)", list(SOURCE_SCRIPTS.keys())
    )
    source_script_code = SOURCE_SCRIPTS[source_script_label]

    target_language_label = st.selectbox("Target language", list(TARGET_LANGUAGES.keys()))
    target_language_code = TARGET_LANGUAGES[target_language_label]

    process_clicked = st.button("Process manuscript", type="primary", disabled=uploaded_file is None)

with col_output:
    st.subheader("2. Result")

    if process_clicked and uploaded_file is not None:
        with st.spinner("Processing — first run per language pair downloads models, this can take a few minutes..."):
            try:
                files = {"image": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
                data = {"target_language": target_language_code, "source_script": source_script_code}
                response = requests.post(
                    f"{backend_url.rstrip('/')}/api/v1/manuscript/process",
                    files=files,
                    data=data,
                    timeout=600,
                )
            except requests.exceptions.ConnectionError:
                st.error(f"Could not connect to the backend at {backend_url}. Is it running (`python run.py`)?")
                st.stop()
            except requests.exceptions.Timeout:
                st.error("Request timed out. Model loading can be slow on first run — try again.")
                st.stop()

        if response.status_code != 200:
            try:
                detail = response.json().get("detail", response.text)
            except ValueError:
                detail = response.text
            st.error(f"Backend returned {response.status_code}: {detail}")
            st.stop()

        result = response.json()

        if result.get("needs_review"):
            st.warning("⚠️ This result needs manual review (low confidence or empty/short OCR output).")

        if result.get("warnings"):
            with st.expander(f"Warnings ({len(result['warnings'])})", expanded=True):
                for w in result["warnings"]:
                    st.write(f"- {w}")

        lang_col, target_col, conf_col = st.columns(3)
        with lang_col:
            dl = result["detected_language"]
            st.metric("Detected language", f"{dl['language']} ({dl['language_code']})")
        with target_col:
            tl = result["target_language"]
            st.metric("Target language", f"{tl['language']} ({tl['language_code']})")
        with conf_col:
            st.metric("OCR confidence", f"{result['ocr']['confidence']:.0%}")

        st.markdown("**Language detection confidence:** " + f"{dl['confidence']:.0%}")

        tab_ocr, tab_translation, tab_lines, tab_meta = st.tabs(
            ["OCR text", "Translation", "Per-line detail", "Processing info"]
        )

        with tab_ocr:
            st.text_area("Raw OCR text", result["ocr"]["raw_text"], height=200)
            st.text_area("Cleaned OCR text", result["ocr"]["cleaned_text"], height=200)

        with tab_translation:
            tr = result["translation"]
            if not tr.get("reliable", True):
                st.warning("Translation reliability is reduced — verify against the source manuscript.")
            st.text_area("Translated text", tr["text"], height=250)
            st.caption(f"Provider: {tr['provider']} | {tr['source_language']} → {tr['target_language']}")

        with tab_lines:
            lines = result["ocr"]["lines"]
            if lines:
                st.dataframe(
                    [{"text": l["text"], "confidence": round(l["confidence"], 3)} for l in lines],
                    use_container_width=True,
                )
            else:
                st.info("No individual lines detected.")

        with tab_meta:
            proc = result["processing"]
            st.write(f"**Request ID:** `{result['request_id']}`")
            st.write(f"**OCR engine:** {proc['ocr_engine']}")
            st.write(f"**Translation provider:** {proc['translation_provider']}")
            st.write(f"**Processing time:** {proc['processing_time_ms']} ms")
            st.write(f"**Preprocessing applied:** {', '.join(proc['preprocessing_applied']) or 'none'}")

    elif uploaded_file is None:
        st.info("Upload a manuscript image on the left to get started.")
