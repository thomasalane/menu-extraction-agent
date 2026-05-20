from __future__ import annotations

import streamlit as st

from image_utils import (
    BLUR_THRESHOLD_ERROR,
    BLUR_THRESHOLD_WARNING,
    compute_blur_score,
    make_thumbnail,
    prepare_for_api,
    validate_image,
)


def render_upload_tab() -> None:
    st.header("Upload do Cardápio")

    uploaded = st.file_uploader(
        "Escolha uma imagem do cardápio",
        type=["jpg", "jpeg", "png", "webp"],
        help="Máximo 20MB. Formatos: JPEG, PNG, WEBP.",
    )

    if not uploaded:
        st.info("Faça o upload de uma imagem para começar.")
        return

    file_bytes = uploaded.read()

    valid, err = validate_image(file_bytes)
    if not valid:
        st.error(err)
        return

    blur_score = compute_blur_score(file_bytes)
    st.session_state.blur_score = blur_score
    st.session_state.uploaded_bytes = file_bytes
    st.session_state.uploaded_filename = uploaded.name

    col_img, col_info = st.columns([2, 1])
    with col_img:
        thumb = make_thumbnail(file_bytes, max_width=500)
        st.image(thumb, caption=uploaded.name, width="stretch")

    with col_info:
        st.metric("Blur Score", f"{blur_score:.1f}")
        if blur_score < BLUR_THRESHOLD_ERROR:
            st.error("Imagem muito borrada. Qualidade de extração será baixa.")
        elif blur_score < BLUR_THRESHOLD_WARNING:
            st.warning("Imagem pode estar borrada. Resultados podem ter baixa confiança.")
        else:
            st.success("Qualidade da imagem parece adequada.")

        st.metric("Tamanho", f"{len(file_bytes) / 1024:.1f} KB")

    proceed = True
    if blur_score < BLUR_THRESHOLD_ERROR:
        proceed = st.checkbox("Prosseguir mesmo com baixa qualidade de imagem")

    if not proceed:
        return

    if st.button("Extrair Dados do Cardápio", type="primary", use_container_width=True):
        _run_extraction(file_bytes, uploaded.name, blur_score)


def _run_extraction(file_bytes: bytes, filename: str, blur_score: float) -> None:
    from agent import extract_menu
    from schemas import MenuExtractionResult

    progress = st.progress(0, text="Preparando imagem...")
    try:
        api_bytes, media_type = prepare_for_api(file_bytes)
        progress.progress(25, text="Imagem preparada. Chamando API...")

        raw = extract_menu(api_bytes, media_type, filename, blur_score)
        progress.progress(75, text="Parseando resposta...")

        result = MenuExtractionResult.model_validate(raw)
        st.session_state.extraction_result = result
        st.session_state.edited_df = result.to_dataframe()

        progress.progress(100, text="Concluído!")

        if raw.get("_truncated"):
            st.warning(
                "Resposta truncada pelo limite de tokens. Apenas resultados parciais exibidos. "
                "Tente uma imagem de maior resolução ou recorte o cardápio em seções."
            )

        st.success(
            f"Extraídos **{result.metadata.total_items_extracted}** itens. "
            f"**{result.metadata.total_items_flagged}** sinalizados para revisão."
        )
        st.info("Acesse a aba **Resultados** para visualizar e editar os dados extraídos.")

    except ValueError as exc:
        st.error(f"Configuração inválida: {exc}")
        progress.empty()
    except Exception as exc:
        _handle_api_error(exc)
        progress.empty()


def _handle_api_error(exc: Exception) -> None:
    from google.genai import errors as genai_errors

    if isinstance(exc, genai_errors.ClientError):
        code = getattr(exc, "code", 0) or 0
        msg = str(exc).lower()
        if code == 429 or "quota" in msg or "rate" in msg:
            st.error("Cota do Gemini atingida. Aguarde 1 minuto e tente novamente.")
        elif code in (401, 403) or "permission" in msg or "api key" in msg:
            st.error("Chave inválida. Verifique GEMINI_API_KEY no arquivo .env.")
        elif code == 400:
            st.error("Imagem rejeitada pela API. Tente outro arquivo ou formato.")
        else:
            st.error(f"Erro da API ({code}): {exc}")
    elif isinstance(exc, genai_errors.ServerError):
        st.error("API indisponível após 3 tentativas. Verifique sua conexão.")
    elif isinstance(exc, ValueError):
        st.error(str(exc))
    else:
        st.error(f"Erro: {exc}")
        with st.expander("Detalhes"):
            st.exception(exc)
