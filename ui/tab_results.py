from __future__ import annotations

import re
import uuid

import pandas as pd
import streamlit as st


def _parse_price(raw: str) -> float | None:
    if not raw:
        return None
    try:
        return float(re.sub(r"[^\d,.]", "", raw).replace(",", "."))
    except ValueError:
        return None


def _apply_editor_delta(base_df: pd.DataFrame) -> pd.DataFrame:
    """Apply pending data_editor edits to base_df without mutating session state."""
    editor_state = st.session_state.get("main_editor") or {}
    edited_rows = editor_state.get("edited_rows") or {}
    if not edited_rows:
        return base_df.copy()

    display_indices = st.session_state.get("_display_indices") or list(range(len(base_df)))
    df = base_df.copy()

    for visual_row, changes in edited_rows.items():
        if visual_row >= len(display_indices):
            continue
        actual_idx = display_indices[visual_row]
        for col, val in changes.items():
            df.at[actual_idx, col] = val
        if "price_raw" in changes:
            df.at[actual_idx, "price_float"] = _parse_price(str(changes.get("price_raw") or ""))

    return df


def _commit_and_reset() -> None:
    """Commit pending edits to session state and clear editor state."""
    st.session_state.edited_df = _apply_editor_delta(st.session_state.edited_df)
    st.session_state.pop("main_editor", None)


def _on_editor_change() -> None:
    """Fires when user makes an edit in data_editor. Commits delta to edited_df."""
    state = st.session_state.get("main_editor") or {}
    edited_rows = state.get("edited_rows") or {}
    if not edited_rows:
        return

    display_indices = st.session_state.get("_display_indices") or []
    df = st.session_state.edited_df

    for visual_row, changes in edited_rows.items():
        if visual_row >= len(display_indices):
            continue
        actual_idx = display_indices[visual_row]
        for col, val in changes.items():
            df.at[actual_idx, col] = val
        if "price_raw" in changes:
            df.at[actual_idx, "price_float"] = _parse_price(str(changes["price_raw"] or ""))


_FLAG_LABELS = {
    "low_confidence": "Baixa confiança da IA",
    "price_parse_failed": "Preço não reconhecido",
    "missing_description": "Descrição ausente",
}


def _render_validation_panel(df: pd.DataFrame) -> None:
    """Surface the Pydantic-generated quality flags so the user can review them."""
    if "flags" not in df.columns:
        return

    flagged = df[df["flags"].astype(str).str.strip() != ""]
    if flagged.empty:
        st.success("Validação: nenhum item sinalizado. Todos os campos passaram nas verificações.")
        return

    with st.expander(f"Ver {len(flagged)} item(ns) sinalizado(s) na validação"):
        for _, row in flagged.iterrows():
            raw_flags = [f.strip() for f in str(row["flags"]).split(",") if f.strip()]
            labels = [_FLAG_LABELS.get(f, f) for f in raw_flags]
            nome = row["name"] or "(sem nome)"
            categoria = row["category"] or "Sem categoria"
            st.markdown(f"**{nome}** · _{categoria}_ — {', '.join(labels)}")


def _render_dashboard(df: pd.DataFrame, currency: str) -> None:
    """Mini-dashboard: estatísticas de preço e distribuição por categoria."""
    prices = pd.to_numeric(df["price_float"], errors="coerce").dropna()
    with st.expander("📊 Resumo do cardápio", expanded=False):
        if prices.empty:
            st.caption("Nenhum preço numérico reconhecido para gerar estatísticas.")
        else:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Menor preço", f"{currency} {prices.min():,.2f}")
            c2.metric("Preço médio", f"{currency} {prices.mean():,.2f}")
            c3.metric("Maior preço", f"{currency} {prices.max():,.2f}")
            conf_cols = ["conf_name", "conf_description", "conf_price", "conf_category"]
            avg_conf = df[conf_cols].mean().mean()
            c4.metric(
                "Confiança média",
                f"{avg_conf:.0%}",
                help="Média das confianças da IA em todos os campos extraídos.",
            )

        cat_series = df["category"].replace("", "Sem categoria")
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("**Itens por categoria**")
            st.bar_chart(cat_series.value_counts(), horizontal=True, color="#E8A33D")
        with col_b:
            st.markdown("**Preço médio por categoria**")
            price_by_cat = (
                df.assign(category=cat_series, price=pd.to_numeric(df["price_float"], errors="coerce"))
                .groupby("category")["price"]
                .mean()
                .dropna()
                .sort_values(ascending=False)
            )
            if price_by_cat.empty:
                st.caption("Sem preços numéricos por categoria.")
            else:
                st.bar_chart(price_by_cat, horizontal=True, color="#E8A33D")


def _render_editor(display_df: pd.DataFrame, display_indices: list[int], multi_source: bool) -> None:
    # --- Aprovação em massa (atua nos itens filtrados/visíveis) ---
    bc1, bc2, _ = st.columns([1, 1, 3])
    if bc1.button("✓ Aprovar visíveis", use_container_width=True):
        _commit_and_reset()
        st.session_state.edited_df.loc[display_indices, "approved"] = True
        st.rerun()
    if bc2.button("✗ Desmarcar visíveis", use_container_width=True):
        _commit_and_reset()
        st.session_state.edited_df.loc[display_indices, "approved"] = False
        st.rerun()

    # Show editor — do NOT use return value.
    # Edits accumulate in st.session_state["main_editor"] and are applied on demand.
    st.data_editor(
        display_df,
        column_config={
            "approved": st.column_config.CheckboxColumn("✓", width="small"),
            "id": st.column_config.TextColumn("ID", disabled=True, width="small"),
            "category": st.column_config.TextColumn("Categoria"),
            "name": st.column_config.TextColumn("Nome do Item", required=True),
            "description": st.column_config.TextColumn("Descrição", width="large"),
            "price_raw": st.column_config.TextColumn("Preço (original)"),
            "price_float": st.column_config.NumberColumn("Preço", format="%.2f", disabled=True),
            "conf_name": st.column_config.ProgressColumn(
                "Conf. Nome", min_value=0.0, max_value=1.0, format="%.2f"
            ),
            "conf_description": st.column_config.ProgressColumn(
                "Conf. Desc.", min_value=0.0, max_value=1.0, format="%.2f"
            ),
            "conf_price": st.column_config.ProgressColumn(
                "Conf. Preço", min_value=0.0, max_value=1.0, format="%.2f"
            ),
            "conf_category": st.column_config.ProgressColumn(
                "Conf. Cat.", min_value=0.0, max_value=1.0, format="%.2f"
            ),
            "flags": None,
            "source_image": (
                st.column_config.TextColumn("Imagem", disabled=True) if multi_source else None
            ),
        },
        hide_index=True,
        width="stretch",
        num_rows="fixed",
        key="main_editor",
        on_change=_on_editor_change,
    )


def _render_source_images() -> None:
    images = st.session_state.get("uploaded_images") or []
    if not images:
        return
    with st.expander(f"🖼️ Ver imagem(ns) original(is) ({len(images)})"):
        for name, file_bytes in images:
            st.image(file_bytes, caption=name, width="stretch")


def render_results_tab() -> None:
    st.header("Itens Extraídos")

    if st.session_state.get("extraction_result") is None:
        st.info("Nenhuma extração realizada. Faça o upload de uma imagem primeiro.")
        return

    result = st.session_state.extraction_result

    # Reset editor state on new extraction
    extraction_ts = str(result.metadata.extraction_timestamp)
    if st.session_state.get("_extraction_ts") != extraction_ts:
        st.session_state["_extraction_ts"] = extraction_ts
        st.session_state.pop("main_editor", None)
        st.session_state.pop("_filter_prev", None)
        st.session_state.pop("_display_indices", None)

    base_df = st.session_state.edited_df

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total de Itens", len(base_df))
    c2.metric(
        "Sinalizados",
        result.metadata.total_items_flagged,
        help="Itens com algum problema de qualidade detectado automaticamente: "
        "baixa confiança da IA, preço não reconhecido ou descrição ausente.",
    )
    c3.metric("Restaurante", result.metadata.restaurant_name or "Desconhecido")
    c4.metric("Aprovados", int(base_df["approved"].sum()) if not base_df.empty else 0)

    duration = result.metadata.extraction_duration_seconds
    st.caption(
        f"Modelo: {result.metadata.model_used}"
        + (f" · Tempo de extração: {duration:.1f}s" if duration else "")
        + (f" · Arquivo(s): {result.metadata.image_filename}" if result.metadata.image_filename else "")
    )

    if result.extraction_notes:
        st.info(f"Notas da extração: {result.extraction_notes}")

    _render_validation_panel(base_df)
    _render_source_images()

    if base_df.empty:
        st.warning("Nenhum item foi extraído. Tente com outra imagem ou verifique a qualidade da foto.")
        return

    currency = result.metadata.currency_symbol or "R$"
    _render_dashboard(base_df, currency)

    # --- Filtros ---
    categories = ["Todos"] + sorted(c for c in base_df["category"].unique().tolist() if c)
    fc1, fc2, fc3 = st.columns([2, 2, 1])
    with fc1:
        selected = st.selectbox("Filtrar por categoria", categories)
    with fc2:
        search = st.text_input("Buscar por nome", placeholder="Ex: feijoada")
    with fc3:
        flagged_only = st.toggle("Só sinalizados", help="Mostrar apenas itens com avisos de validação.")

    # When any filter changes: commit pending edits and reset editor
    filter_sig = (selected, search.strip().lower(), flagged_only)
    if filter_sig != st.session_state.get("_filter_prev"):
        _commit_and_reset()
        st.session_state["_filter_prev"] = filter_sig
        base_df = st.session_state.edited_df  # refresh after commit

    mask = pd.Series(True, index=base_df.index)
    if selected != "Todos":
        mask &= base_df["category"] == selected
    if search.strip():
        mask &= base_df["name"].astype(str).str.lower().str.contains(
            search.strip().lower(), regex=False
        )
    if flagged_only:
        mask &= base_df["flags"].astype(str).str.strip() != ""

    filtered = base_df[mask]
    display_indices = filtered.index.tolist()
    display_df = filtered.reset_index(drop=True)
    st.session_state["_display_indices"] = display_indices

    multi_source = base_df["source_image"].astype(str).str.strip().nunique() > 1

    if display_df.empty:
        st.warning("Nenhum item corresponde aos filtros selecionados.")
    else:
        _render_editor(display_df, display_indices, multi_source)

    # --- Add item manually ---
    st.divider()
    with st.expander("Adicionar item manualmente"):
        with st.form("add_item_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                f_name = st.text_input("Nome *", placeholder="Ex: Feijoada Completa")
                f_category = st.text_input("Categoria", placeholder="Ex: Pratos Principais")
                f_price_raw = st.text_input("Preço (original)", placeholder="Ex: R$45,90")
            with col2:
                f_description = st.text_area(
                    "Descrição", placeholder="Ex: Acompanha arroz, farofa e couve.", height=120
                )
            submitted = st.form_submit_button("Adicionar Item", type="primary", use_container_width=True)

        if submitted:
            if not f_name.strip():
                st.error("O campo Nome é obrigatório.")
            else:
                _commit_and_reset()
                new_row = {
                    "approved": True,
                    "id": str(uuid.uuid4())[:8],
                    "category": f_category.strip(),
                    "name": f_name.strip(),
                    "description": f_description.strip(),
                    "price_raw": f_price_raw.strip(),
                    "price_float": _parse_price(f_price_raw),
                    "conf_name": 1.0,
                    "conf_description": 1.0,
                    "conf_price": 1.0,
                    "conf_category": 1.0,
                    "flags": "",
                    "source_image": "manual",
                }
                new_df = pd.DataFrame([new_row])
                current = st.session_state.edited_df
                if current.empty:
                    st.session_state.edited_df = new_df
                else:
                    # Drop all-NA columns from each side to avoid pandas FutureWarning
                    st.session_state.edited_df = pd.concat(
                        [current.dropna(axis=1, how="all"), new_df.dropna(axis=1, how="all")],
                        ignore_index=True,
                    )
                st.success(f"Item **{f_name.strip()}** adicionado.")
                st.rerun()

    # --- Remove items ---
    with st.expander("Remover itens"):
        df_current = st.session_state.edited_df

        def _item_label(idx: int) -> str:
            row = df_current.loc[idx]
            return (
                f"[{row['category'] or 'Sem categoria'}] {row['name']} "
                f"({row['price_raw'] or 'sem preço'})"
            )

        to_remove = st.multiselect(
            "Selecione os itens para remover",
            options=df_current.index.tolist(),
            format_func=_item_label,
            placeholder="Escolha um ou mais itens...",
        )
        if to_remove:
            if st.button("Remover selecionados", type="primary"):
                _commit_and_reset()
                st.session_state.edited_df = (
                    st.session_state.edited_df.drop(index=to_remove).reset_index(drop=True)
                )
                st.success(f"{len(to_remove)} item(s) removido(s).")
                st.rerun()

    # --- Export (apply pending edits before exporting) ---
    st.divider()
    export_columns = [
        "approved", "id", "category", "name", "description",
        "price_raw", "price_float",
        "conf_name", "conf_description", "conf_price", "conf_category",
    ]
    if multi_source:
        export_columns.append("source_image")

    export_df = _apply_editor_delta(st.session_state.edited_df)

    approved_only = st.checkbox(
        "Exportar apenas itens aprovados (✓)",
        help="Quando marcado, somente as linhas com a coluna ✓ marcada entram no arquivo.",
    )
    if approved_only:
        export_df = export_df[export_df["approved"] == True]  # noqa: E712

    export_df = export_df.reindex(columns=export_columns)
    st.caption(f"{len(export_df)} item(ns) serão exportados.")

    col_a, col_b, _ = st.columns([1, 1, 4])
    with col_a:
        # Brazilian Excel expects ';' as field separator and ',' as decimal.
        # utf-8-sig adds BOM so Excel reads accents correctly on Windows.
        csv = export_df.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig")
        st.download_button("Exportar CSV", csv, "cardapio.csv", "text/csv")
    with col_b:
        json_str = export_df.to_json(orient="records", force_ascii=False, indent=2)
        st.download_button(
            "Exportar JSON",
            json_str.encode("utf-8"),
            "cardapio.json",
            "application/json",
        )
