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
        st.session_state.pop("_cat_prev", None)
        st.session_state.pop("_display_indices", None)

    base_df = st.session_state.edited_df

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total de Itens", len(base_df))
    c2.metric("Sinalizados", result.metadata.total_items_flagged)
    c3.metric("Restaurante", result.metadata.restaurant_name or "Desconhecido")
    c4.metric("Modelo", result.metadata.model_used)

    if result.extraction_notes:
        st.info(f"Notas da extração: {result.extraction_notes}")

    if base_df.empty:
        st.warning("Nenhum item foi extraído. Tente com outra imagem ou verifique a qualidade da foto.")
        return

    categories = ["Todos"] + sorted(c for c in base_df["category"].unique().tolist() if c)
    prev_filter = st.session_state.get("_cat_prev", "Todos")
    selected = st.selectbox("Filtrar por categoria", categories)

    # When filter changes: commit pending edits and reset editor
    if selected != prev_filter:
        _commit_and_reset()
        st.session_state["_cat_prev"] = selected
        base_df = st.session_state.edited_df  # refresh after commit

    # Build display_df with reset index so data_editor uses 0-based visual rows
    if selected == "Todos":
        filtered = base_df
        display_indices = list(range(len(base_df)))
    else:
        filtered = base_df[base_df["category"] == selected]
        display_indices = filtered.index.tolist()

    display_df = filtered.reset_index(drop=True)
    st.session_state["_display_indices"] = display_indices

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
        },
        hide_index=True,
        width="stretch",
        num_rows="fixed",
        key="main_editor",
    )

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
                }
                st.session_state.edited_df = pd.concat(
                    [st.session_state.edited_df, pd.DataFrame([new_row])],
                    ignore_index=True,
                )
                st.success(f"Item **{f_name.strip()}** adicionado.")
                st.rerun()

    # --- Remove items ---
    with st.expander("Remover itens"):
        df_current = st.session_state.edited_df
        item_labels = [
            f"{row['name']} ({row['price_raw'] or 'sem preço'})"
            for _, row in df_current.iterrows()
        ]
        to_remove = st.multiselect(
            "Selecione os itens para remover",
            options=item_labels,
            placeholder="Escolha um ou mais itens...",
        )
        if to_remove:
            if st.button("Remover selecionados", type="primary"):
                _commit_and_reset()
                remove_set = set(to_remove)
                keep = [i for i, lbl in enumerate(item_labels) if lbl not in remove_set]
                st.session_state.edited_df = df_current.iloc[keep].reset_index(drop=True)
                st.success(f"{len(to_remove)} item(s) removido(s).")
                st.rerun()

    # --- Export (apply pending edits before exporting) ---
    col_a, col_b, _ = st.columns([1, 1, 4])
    export_df = _apply_editor_delta(st.session_state.edited_df)
    with col_a:
        csv = export_df.to_csv(index=False).encode("utf-8")
        st.download_button("Exportar CSV", csv, "cardapio.csv", "text/csv")
    with col_b:
        json_str = export_df.to_json(orient="records", force_ascii=False, indent=2)
        st.download_button(
            "Exportar JSON",
            json_str.encode("utf-8"),
            "cardapio.json",
            "application/json",
        )
