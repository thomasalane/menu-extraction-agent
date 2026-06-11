from __future__ import annotations

import streamlit as st

from image_utils import analyze_quality, make_thumbnail, prepare_for_api, validate_image


def render_upload_tab() -> None:
    st.header("Upload do Cardápio")

    uploaded_files = st.file_uploader(
        "Escolha uma ou mais imagens do cardápio",
        type=["jpg", "jpeg", "png", "webp"],
        accept_multiple_files=True,
        help="Máximo 20MB por arquivo. Formatos: JPEG, PNG, WEBP. "
        "Cardápios de várias páginas podem ser enviados juntos — os itens são consolidados.",
    )

    if not uploaded_files:
        st.info("Faça o upload de uma ou mais imagens para começar.")
        return

    # Valida e analisa qualidade de cada arquivo
    valid_files: list[tuple[str, bytes]] = []
    for uploaded in uploaded_files:
        file_bytes = uploaded.getvalue()
        valid, err = validate_image(file_bytes)
        if not valid:
            st.error(f"**{uploaded.name}**: {err}")
            continue
        valid_files.append((uploaded.name, file_bytes))

    if not valid_files:
        return

    st.session_state.uploaded_images = valid_files

    # Pré-visualização em grade + relatório de qualidade
    cols = st.columns(min(len(valid_files), 3))
    quality_issues: list[str] = []
    for i, (name, file_bytes) in enumerate(valid_files):
        report = analyze_quality(file_bytes)
        with cols[i % len(cols)]:
            thumb = make_thumbnail(file_bytes, max_width=500)
            status_icon = "✅" if report.ok else "⚠️"
            st.image(thumb, caption=f"{status_icon} {name}", width="stretch")
            st.caption(
                f"{report.width}×{report.height}px · {len(file_bytes) / 1024:.0f} KB"
            )
        for warning in report.warnings:
            quality_issues.append(f"**{name}**: {warning}")

    if quality_issues:
        with st.container(border=True):
            st.markdown("##### ⚠️ Avisos de qualidade")
            for issue in quality_issues:
                st.warning(issue)
            st.caption(
                "Você ainda pode extrair, mas os resultados podem vir com baixa "
                "confiança. Se possível, envie uma foto mais nítida e bem iluminada."
            )
    else:
        st.success("Verificação de qualidade: todas as imagens passaram. ✅")

    label = (
        "Extrair Dados do Cardápio"
        if len(valid_files) == 1
        else f"Extrair Dados de {len(valid_files)} Imagens"
    )
    if st.button(label, type="primary", use_container_width=True):
        _run_extraction(valid_files)


def _run_extraction(files: list[tuple[str, bytes]]) -> None:
    from agent import extract_menu
    from schemas import MenuExtractionResult

    results: list[MenuExtractionResult] = []
    truncated_files: list[str] = []
    failures: list[str] = []

    with st.status("Extraindo dados...", expanded=True) as status:
        for idx, (filename, file_bytes) in enumerate(files, start=1):
            prefix = f"[{idx}/{len(files)}] {filename}"
            st.write(f"{prefix} — preparando imagem...")
            try:
                api_bytes, _ = prepare_for_api(file_bytes)
                st.write(f"{prefix} — chamando a API...")
                raw = extract_menu(api_bytes, filename)
                result = MenuExtractionResult.model_validate(raw)
                for item in result.items:
                    item.source_image = filename
                results.append(result)
                if raw.get("_truncated"):
                    truncated_files.append(filename)
                st.write(f"{prefix} — ✅ {len(result.items)} itens extraídos.")
            except ValueError as exc:
                # Configuração inválida (ex.: API key ausente) — não adianta continuar
                status.update(label="Falha na extração", state="error")
                st.error(f"Configuração inválida: {exc}")
                return
            except Exception as exc:
                msg, fatal = _format_api_error(exc)
                failures.append(f"**{filename}**: {msg}")
                st.write(f"{prefix} — ❌ falhou.")
                if fatal:
                    break

        state = "complete" if results else "error"
        status.update(label="Extração concluída", state=state, expanded=False)

    for failure in failures:
        st.error(failure)

    if not results:
        return

    combined = _combine_results(results)
    st.session_state.extraction_result = combined
    st.session_state.edited_df = combined.to_dataframe()

    if truncated_files:
        st.warning(
            "Resposta truncada pelo limite de tokens em: "
            + ", ".join(f"**{f}**" for f in truncated_files)
            + ". Apenas resultados parciais exibidos. Tente recortar o cardápio em seções."
        )

    st.success(
        f"Extraídos **{combined.metadata.total_items_extracted}** itens"
        + (f" de **{len(results)}** imagens" if len(files) > 1 else "")
        + f". **{combined.metadata.total_items_flagged}** sinalizados para revisão."
    )
    st.info("Acesse a aba **Resultados** para visualizar e editar os dados extraídos.")


def _combine_results(results):
    """Consolida extrações de várias imagens em um único resultado."""
    from schemas import ExtractionMetadata, MenuExtractionResult

    if len(results) == 1:
        return results[0]

    items = [item for r in results for item in r.items]
    notes = [
        f"{r.metadata.image_filename}: {r.extraction_notes}"
        for r in results
        if r.extraction_notes
    ]
    metadata = ExtractionMetadata(
        restaurant_name=next(
            (r.metadata.restaurant_name for r in results if r.metadata.restaurant_name), None
        ),
        currency_symbol=next(
            (r.metadata.currency_symbol for r in results if r.metadata.currency_symbol), None
        ),
        currency_code=next(
            (r.metadata.currency_code for r in results if r.metadata.currency_code), None
        ),
        model_used=results[0].metadata.model_used,
        image_filename=", ".join(r.metadata.image_filename or "?" for r in results),
        extraction_duration_seconds=sum(
            r.metadata.extraction_duration_seconds or 0 for r in results
        ),
        raw_response_length=sum(r.metadata.raw_response_length for r in results),
    )
    return MenuExtractionResult(
        metadata=metadata,
        items=items,
        extraction_notes="\n".join(notes) or None,
    )


def _format_api_error(exc: Exception) -> tuple[str, bool]:
    """Retorna (mensagem amigável, fatal). Fatal = abortar os arquivos restantes."""
    from google.genai import errors as genai_errors

    if isinstance(exc, genai_errors.ClientError):
        code = getattr(exc, "code", 0) or 0
        msg = str(exc).lower()
        if code == 429 or "quota" in msg or "rate" in msg:
            return "Cota do Gemini atingida. Aguarde 1 minuto e tente novamente.", True
        if code in (401, 403) or "permission" in msg or "api key" in msg:
            return "Chave inválida. Verifique GEMINI_API_KEY no arquivo .env.", True
        if code == 400:
            return "Imagem rejeitada pela API. Tente outro arquivo ou formato.", False
        return f"Erro da API ({code}): {exc}", False
    if isinstance(exc, genai_errors.ServerError):
        return "API indisponível após 3 tentativas. Verifique sua conexão.", True
    return f"Erro: {exc}", False
