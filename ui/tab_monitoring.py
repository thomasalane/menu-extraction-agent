from __future__ import annotations

import streamlit as st

from config import CONFIDENCE_HIGH, CONFIDENCE_MEDIUM


def _conf_color(score: float) -> str:
    if score >= CONFIDENCE_HIGH:
        return "green"
    if score >= CONFIDENCE_MEDIUM:
        return "orange"
    return "red"


def render_monitoring_tab() -> None:
    st.header("Monitoramento Human-in-the-Loop")

    if st.session_state.get("extraction_result") is None:
        st.info("Nenhuma extração realizada. Faça o upload de uma imagem primeiro.")
        return

    result = st.session_state.extraction_result
    df = st.session_state.edited_df

    show_all = st.toggle("Mostrar todos os itens (não apenas sinalizados)", value=False)
    review_df = df if show_all else df[df["flags"].str.len() > 0]

    if review_df.empty:
        st.success("Nenhum item sinalizado. Todos os scores de confiança estão acima do limite.")
        return

    img_col, items_col = st.columns([1, 1])

    with img_col:
        st.subheader("Imagem Original")
        if st.session_state.get("uploaded_bytes"):
            from image_utils import make_thumbnail
            thumb = make_thumbnail(st.session_state.uploaded_bytes, max_width=600)
            st.image(thumb, width="stretch")

        blur = st.session_state.get("blur_score")
        if blur is not None:
            quality = "Boa" if blur > 50 else ("Ruim" if blur < 10 else "Marginal")
            st.caption(f"Blur score: {blur:.1f} ({quality})")

        if result.extraction_notes:
            st.info(f"Notas: {result.extraction_notes}")

    with items_col:
        flagged_count = len(review_df)
        st.subheader(f"Itens para Revisão ({flagged_count})")

        for _, row in review_df.iterrows():
            min_conf = min(
                row["conf_name"],
                row["conf_price"],
                row["conf_description"],
                row["conf_category"],
            )
            color = _conf_color(min_conf)
            level = "ALTA" if color == "green" else ("MÉDIA" if color == "orange" else "BAIXA")

            label = (
                f":{color}[{level}] {row['name']} — "
                f"{row['price_raw'] or 'sem preço'} | {row['flags'] or 'sem flags'}"
            )

            with st.expander(label, expanded=(min_conf < CONFIDENCE_MEDIUM)):
                sub1, sub2 = st.columns(2)
                with sub1:
                    st.write(f"**Categoria**: {row['category'] or '—'}")
                    st.write(f"**Descrição**: {row['description'] or '—'}")
                    st.write(f"**Preço original**: {row['price_raw'] or '—'}")
                    st.write(f"**Preço numérico**: {row['price_float']}")

                with sub2:
                    for field_label, conf_key in [
                        ("Nome", "conf_name"),
                        ("Preço", "conf_price"),
                        ("Descrição", "conf_description"),
                        ("Categoria", "conf_category"),
                    ]:
                        v = row[conf_key]
                        c = _conf_color(v)
                        st.write(f"**{field_label}**: :{c}[{v:.2f}]")

                approved = st.checkbox(
                    "Marcar como revisado/aprovado",
                    value=bool(row.get("approved", False)),
                    key=f"approve_{row['id']}",
                )
                if approved != bool(row.get("approved", False)):
                    st.session_state.edited_df.loc[
                        st.session_state.edited_df["id"] == row["id"], "approved"
                    ] = approved

        if st.button("Aprovar Todos os Itens Visíveis"):
            for _, row in review_df.iterrows():
                st.session_state.edited_df.loc[
                    st.session_state.edited_df["id"] == row["id"], "approved"
                ] = True
            st.rerun()

        approved_count = int(st.session_state.edited_df["approved"].sum())
        total = len(st.session_state.edited_df)
        st.metric("Aprovados", f"{approved_count} / {total}")
