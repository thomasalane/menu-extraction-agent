import streamlit as st

from config import APP_TITLE

st.set_page_config(
    page_title=APP_TITLE,
    page_icon="🧾",
    layout="wide",
    initial_sidebar_state="collapsed",
)

for key, default in {
    "extraction_result": None,
    "edited_df": None,
    "uploaded_images": None,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

st.html("""
<style>
/* Oculta o widget de status do toolbar ("Running..." + botão Stop).
   O Stop não consegue abortar a chamada bloqueante à API e o app já
   mostra progresso próprio via st.status. */
div[data-testid="stStatusWidget"] { display: none !important; }
</style>
<script>
(function () {
    const HIDE = ['Print', 'Record screen', 'Made with Streamlit'];
    const doc = window.parent.document;

    const hide = () => {
        doc.querySelectorAll('li[role="menuitem"], button').forEach(el => {
            if (HIDE.some(t => el.textContent.trim().startsWith(t))) {
                el.style.display = 'none';
                const sep = el.previousElementSibling;
                if (sep && sep.getAttribute('role') === 'separator') {
                    sep.style.display = 'none';
                }
            }
        });
    };

    const observer = new MutationObserver(hide);
    observer.observe(doc.body, { childList: true, subtree: true });

    // Disconnect after 30s — menu items are static, no need to watch forever
    setTimeout(() => observer.disconnect(), 30000);
})();
</script>
""")

st.title(f"🧾 {APP_TITLE}")
st.caption(
    "Envie fotos de cardápios e extraia itens, descrições, preços e categorias "
    "automaticamente com IA. Revise, edite e exporte em CSV ou JSON."
)

tab_upload, tab_results = st.tabs(["📤 Upload", "📋 Resultados"])

with tab_upload:
    from ui.tab_upload import render_upload_tab
    render_upload_tab()

with tab_results:
    from ui.tab_results import render_results_tab
    render_results_tab()
