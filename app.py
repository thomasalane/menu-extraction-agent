import streamlit as st

from config import APP_TITLE

st.set_page_config(page_title=APP_TITLE, layout="wide", initial_sidebar_state="collapsed")

for key, default in {
    "extraction_result": None,
    "edited_df": None,
    "uploaded_bytes": None,
    "uploaded_filename": None,
    "blur_score": None,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

st.html("""
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

st.title(APP_TITLE)

tab_upload, tab_results = st.tabs(["Upload", "Resultados"])

with tab_upload:
    from ui.tab_upload import render_upload_tab
    render_upload_tab()

with tab_results:
    from ui.tab_results import render_results_tab
    render_results_tab()
