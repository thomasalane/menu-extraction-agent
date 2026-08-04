# 🧾 Menu Extraction Agent

## 📋 About the Project

An application that extracts structured data from restaurant menu images using AI.

Built with **Streamlit** and **Google Gemini**, the system automatically identifies items, descriptions, prices and categories from menu photos.

## 🚀 Features

- Upload one or multiple images (multi-page menus are consolidated into a single result)
- Image quality validation (resolution, blur and lighting) before extraction
- Automatic AI extraction (Gemini 2.5 Flash) with structured output — validated JSON straight from the API
- Confidence score per extracted field, automatically flagging items for review
- Review and edit the extracted data (edit, add, remove and approve items)
- Filter by category, search by name, and view only flagged items
- Mini-dashboard with price statistics and category distribution
- Export to CSV (Excel BR compatible) or JSON, with the option to export approved items only
