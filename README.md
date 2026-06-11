# 🧾 Menu Extraction Agent

## 📋 Sobre o Projeto

Aplicação para extrair dados estruturados de imagens de cardápios usando IA.

Desenvolvido com **Streamlit** e **Google Gemini**, o sistema identifica automaticamente itens, descrições, preços e categorias a partir de fotos de menus.

## 🚀 Funcionalidades

- Upload de uma ou várias imagens (cardápios de múltiplas páginas são consolidados)
- Validação de qualidade da imagem (resolução, desfoque e iluminação) antes da extração
- Extração automática via IA (Gemini 2.5 Flash) com structured output — JSON validado direto da API
- Score de confiança por campo extraído, com sinalização automática de itens para revisão
- Revisão e edição dos dados extraídos (editar, adicionar, remover e aprovar itens)
- Filtros por categoria, busca por nome e visualização apenas dos itens sinalizados
- Mini-dashboard com estatísticas de preço e distribuição por categoria
- Exportação em CSV (compatível com Excel BR) ou JSON, com opção de exportar só itens aprovados
