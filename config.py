APP_TITLE = "Menu Extraction Agent"
MODEL_NAME = "gemini-2.5-flash"
MAX_IMAGE_SIZE_MB = 20
MAX_IMAGE_DIMENSION = 1568
SUPPORTED_FORMATS = ["jpg", "jpeg", "png", "webp"]
MAX_TOKENS = 8192

# Limiares de qualidade da imagem (avisos, não bloqueiam a extração)
MIN_IMAGE_DIMENSION = 700        # menor lado abaixo disso = aviso de resolução baixa
BLUR_THRESHOLD = 80.0            # variância do Laplaciano abaixo disso = possível desfoque
BRIGHTNESS_DARK = 50.0           # luminância média abaixo disso = imagem muito escura
BRIGHTNESS_BRIGHT = 215.0        # luminância média acima disso = imagem estourada
