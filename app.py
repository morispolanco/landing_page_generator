# app.py
from flask import Flask, render_template, request, send_file, jsonify, session
import datetime
import base64
import io
import zipfile
import json
from markupsafe import escape
import os
import google.generativeai as genai
import traceback # Para logs de errores más detallados

app = Flask(__name__)

# Configuración de Clave Secreta para Sesiones (¡MUY IMPORTANTE para producción!)
# Genera una clave segura (ej. `python -c 'import os; print(os.urandom(24))'`)
# y guárdala como variable de entorno FLASK_SECRET_KEY.
app.secret_key = os.environ.get('FLASK_SECRET_KEY')
if not app.secret_key:
    print("ADVERTENCIA: FLASK_SECRET_KEY no está configurada. Usando clave de desarrollo insegura.")
    app.secret_key = 'cambiar-esta-clave-en-produccion!' # SOLO PARA DESARROLLO

# Límite de tamaño de contenido (útil si se habilitaran subidas de archivos)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 # 16 MB

# Configuración de Google Gemini API
try:
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
    if not GEMINI_API_KEY:
        print("Advertencia: GEMINI_API_KEY no configurada. Funcionalidad IA desactivada.")
        model = None
    else:
        genai.configure(api_key=GEMINI_API_KEY)
        # Configura el modelo que deseas usar (ej. 'gemini-1.5-pro-latest' o 'gemini-1.0-pro')
        # Considera añadir generation_config y safety_settings aquí si es necesario
        model = genai.GenerativeModel(model_name="gemini-1.5-pro-latest")
except ImportError:
    print("Error: Librería google-generativeai no encontrada. Instálala con 'pip install google-generativeai'")
    model = None
except Exception as e:
    print(f"Error configurando la API de Gemini: {e}")
    traceback.print_exc()
    model = None

# --- Funciones Auxiliares ---

def generate_svg_logo(name, style='text', shape='none', color_primary='#007bff', color_secondary='#ffffff', font_family='Poppins, sans-serif'):
    """Genera un logo SVG simple basado en texto o iniciales con forma opcional."""
    if not name: name = "Logo" # Fallback si el nombre está vacío
    name = escape(name)
    text_content = name
    font_size = 35 # Tamaño base

    if style == 'initials':
        words = name.split()
        if len(words) >= 2: text_content = (words[0][0] + words[-1][0]).upper()
        elif len(words) == 1 and len(words[0]) > 0: text_content = words[0][0].upper()
        else: text_content = name[0].upper() if name else 'L' # Usa la primera letra si hay nombre
        font_size = 45 # Más grande para iniciales

    svg_width = 100; svg_height = 100; shape_element = ''; text_x = 50; text_y = 50; text_color = color_secondary
    try: # Intento simple de contraste
        # Convertir hex a RGB
        rgb_primary = tuple(int(color_primary.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
        # Cálculo de luminancia (simplificado)
        lum = (0.299 * rgb_primary[0] + 0.587 * rgb_primary[1] + 0.114 * rgb_primary[2]) / 255
        # Decidir color del texto
        text_color = '#333333' if lum > 0.5 and color_secondary == '#ffffff' else ('#ffffff' if lum <= 0.5 and color_secondary == '#000000' else color_secondary)
    except (ValueError, IndexError, TypeError):
        print(f"Advertencia: Color primario inválido '{color_primary}', usando color secundario por defecto para texto.")
        pass # Usar color secundario por defecto si falla la conversión/cálculo

    if shape == 'circle': shape_element = f'<circle cx="50" cy="50" r="50" fill="{color_primary}"/>'
    elif shape == 'square': shape_element = f'<rect width="100" height="100" rx="10" ry="10" fill="{color_primary}"/>' # rx/ry para bordes redondeados
    else: # 'none' - Sin forma de fondo
        # Estimar ancho basado en texto y tamaño de fuente (ajustar multiplicador según fuente)
        est_width = len(text_content) * (font_size * 0.65)
        svg_width = max(60, est_width) # Ancho mínimo para legibilidad
        svg_height= font_size * 1.2 # Altura basada en fuente
        text_x = svg_width / 2
        text_y = svg_height * 0.65 # Ajuste vertical para texto sin fondo
        text_color = color_primary # Usar color primario para el texto cuando no hay fondo

    # Generar el string SVG final
    svg_content = f'''<svg width="{int(svg_width)}" height="{int(svg_height)}" viewBox="0 0 {int(svg_width)} {int(svg_height)}"
     xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMid meet">
    {shape_element}
    <text x="{text_x}" y="{text_y}" font-family="{font_family}" font-size="{font_size}" fill="{text_color}"
          text-anchor="middle" dominant-baseline="central" font-weight="600">
        {text_content}
    </text>
</svg>'''
    # Limpieza básica de espacios innecesarios
    return svg_content.replace('\n', '').replace('    ', ' ')

def generate_svg_hero_pattern(style='waves', color_primary='#007bff', color_secondary='#6c757d', opacity=0.1):
    """Genera un patrón SVG simple para usar como fondo."""
    pattern_content = ''; pattern_id = f"pattern-{style}"; pattern_size = 50; clamped_opacity = max(0.01, min(1, opacity))
    try: # Validar color secundario
        c2 = color_secondary if color_secondary and color_secondary.startswith('#') and len(color_secondary) == 7 else '#6c757d'
    except: c2 = '#6c757d' # Fallback

    if style == 'waves':
        pattern_size = 100
        pattern_content = f'''<path d="M 0 {pattern_size/2} Q {pattern_size/4} {pattern_size/2 - pattern_size*clamped_opacity*0.7} {pattern_size/2} {pattern_size/2} T {pattern_size} {pattern_size/2}" stroke="{c2}" stroke-width="3" fill="none" opacity="{clamped_opacity}"/>
                           <path d="M 0 {pattern_size*0.6} Q {pattern_size/4} {pattern_size*0.6 + pattern_size*clamped_opacity*0.6} {pattern_size/2} {pattern_size*0.6} T {pattern_size} {pattern_size*0.6}" stroke="{c2}" stroke-width="2" fill="none" opacity="{clamped_opacity*0.8}"/>'''
    elif style == 'dots':
         pattern_size = 20
         pattern_content = f'<circle cx="{pattern_size/2}" cy="{pattern_size/2}" r="{pattern_size*0.1}" fill="{c2}" opacity="{clamped_opacity}"/>'
    elif style == 'lines':
         pattern_size = 15
         pattern_content = f'<path d="M 0 0 L {pattern_size} {pattern_size} M {pattern_size} 0 L 0 {pattern_size}" stroke="{c2}" stroke-width="1" opacity="{clamped_opacity}"/>'
    elif style == 'triangles':
         pattern_size = 40
         pattern_content = f'''<path d="M 0 0 L {pattern_size/2} {pattern_size} L {pattern_size} 0 Z" fill="{c2}" opacity="{clamped_opacity*0.5}"/>
                           <path d="M {pattern_size/2} 0 L 0 {pattern_size} L {pattern_size} {pattern_size} Z" fill="{c2}" opacity="{clamped_opacity*0.7}"/>'''
    else: # Fallback: Pequeños cuadrados
        pattern_size = 20
        pattern_content = f'<rect width="{pattern_size*0.5}" height="{pattern_size*0.5}" fill="{c2}" opacity="{clamped_opacity}"/>'

    svg_pattern = f'''<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="100%">
    <defs>
        <pattern id="{pattern_id}" patternUnits="userSpaceOnUse" width="{pattern_size}" height="{pattern_size}">
            {pattern_content}
        </pattern>
    </defs>
    <rect width="100%" height="100%" fill="url(#{pattern_id})" />
</svg>'''
    return svg_pattern.replace('\n', '').replace('    ', ' ')

def svg_to_data_url(svg_string):
    """Convierte una cadena SVG a Data URL base64."""
    if not svg_string: return ""
    try:
        encoded = base64.b64encode(svg_string.encode('utf-8')).decode('utf-8')
        return f"data:image/svg+xml;base64,{encoded}"
    except Exception as e:
        print(f"Error codificando SVG a Data URL: {e}")
        return ""

# --- Rutas Flask ---

@app.route('/', methods=['GET', 'POST'])
def index():
    """Maneja la carga del formulario (GET) y la generación de la preview (POST)."""
    current_year = datetime.datetime.now().year

    if request.method == 'POST':
        # Recopilar datos del formulario de forma más segura y con defaults
        page_data = {
            'page_type': request.form.get('page_type', 'personal'),
            'name': request.form.get('name', '').strip(),
            'headline': request.form.get('headline', '').strip(),
            'description': request.form.get('description', '').strip(),
            'cta_text': request.form.get('cta_text', '').strip(),
            'contact_email': request.form.get('contact_email', '').strip(),
            'contact_phone': request.form.get('contact_phone', '').strip(),
            'social_links_raw': request.form.get('social_links', '').strip(),
            'color_primary': request.form.get('color_primary', '#007bff'),
            'color_secondary': request.form.get('color_secondary', '#ffffff'),
            'features_raw': request.form.get('features', '').strip(),
            'services_raw': request.form.get('services', '').strip(),
            'testimonials_raw': request.form.get('testimonials', '').strip(),
            'portfolio_raw': request.form.get('portfolio_items', '').strip(), # Nombre del campo en el form
            'logo_style': request.form.get('logo_style', 'text'),
            'logo_shape': request.form.get('logo_shape', 'none'),
            'hero_background_type': request.form.get('hero_background_type', 'color'),
            'hero_pattern_style': request.form.get('hero_pattern_style', 'waves'),
            'image_hero_url': request.form.get('image_hero_url', '').strip(), # URL para imagen junto al título
        }

        # Generar SVG Logo y Hero Background
        logo_svg = generate_svg_logo( page_data['name'], page_data['logo_style'], page_data['logo_shape'], page_data['color_primary'], page_data['color_secondary'] )
        page_data['logo_svg_string'] = logo_svg # Guardar para descarga
        page_data['logo_src'] = svg_to_data_url(logo_svg) # Para preview

        hero_pattern_svg = None; page_data['hero_pattern_src'] = None; page_data['hero_background_css'] = None
        hero_bg_type = page_data['hero_background_type']

        # Definir el fondo de la SECCIÓN .hero
        if hero_bg_type == 'pattern':
            hero_pattern_svg = generate_svg_hero_pattern( page_data['hero_pattern_style'], page_data['color_primary'], page_data['color_secondary'], opacity=0.08 )
            page_data['hero_background_svg_pattern_string'] = hero_pattern_svg # Para descarga
            page_data['hero_pattern_src'] = svg_to_data_url(hero_pattern_svg) # Para preview
        elif hero_bg_type == 'gradient':
             # Usa secundario si es distinto de blanco, si no, mezcla primario con negro
             color2 = page_data['color_secondary'] if page_data['color_secondary'] != '#ffffff' else f"color-mix(in srgb, {page_data['color_primary']} 70%, black)"
             page_data['hero_background_css'] = f"linear-gradient(135deg, {page_data['color_primary']}, {color2})"
        elif hero_bg_type == 'color':
            page_data['hero_background_css'] = page_data['color_primary']
        # Si es 'image_url', no se establece fondo CSS aquí; la plantilla usará page_data['image_hero_url'] para un <img>

        # Guardar los datos procesados en la sesión para pre-rellenar
        session['form_data'] = page_data

        # Preparar JSON para el botón de descarga (sin SVGs/Data URLs)
        try:
            data_to_serialize = {k:v for k,v in page_data.items() if not k.endswith('_svg_string') and not k.endswith('_src')}
            data_json = json.dumps(data_to_serialize)
        except Exception as e:
             print(f"Error serializando page_data a JSON: {e}"); data_json = "{}"

        # Renderizar la vista previa
        return render_template(
            'preview.html',
            data=page_data, # Pasar todos los datos procesados
            current_year=current_year,
            data_json=data_json # Pasar JSON limpio para el botón de descarga
        )

    # --- Petición GET ---
    # Cargar datos de la sesión anterior, si existen, para pre-rellenar
    form_data = session.get('form_data', {})
    return render_template('index.html', current_year=current_year, form_data=form_data)

@app.route('/generate-ai-content', methods=['POST'])
def generate_ai_content():
    """Endpoint AJAX para generar contenido con IA (Gemini)."""
    if not model: return jsonify({"error": "Modelo IA no disponible o no configurado correctamente."}), 503

    data = request.get_json();
    if not data: return jsonify({"error": "Petición inválida (no JSON)."}), 400

    headline = data.get('headline', '').strip()
    description = data.get('description', '').strip()
    field_type = data.get('field_type')

    if not (headline and description and field_type):
        missing = [k for k in ['headline', 'description', 'field_type'] if not data.get(k)]
        return jsonify({"error": f"Faltan datos requeridos: {', '.join(missing)}."}), 400

    # Construir Prompt dinámicamente
    prompt_base = f"""Eres un asistente de marketing experto creando contenido conciso y atractivo para páginas de aterrizaje en español.
Basándote SOLO en el siguiente Título Principal y Descripción:

Título Principal: "{headline}"
Descripción: "{description}"

Genera contenido para la sección de '{field_type}'. Sigue estrictamente el formato solicitado y devuelve SOLO la lista generada, sin texto introductorio ni explicaciones adicionales.
"""
    prompt_specific = ""
    if field_type == 'features':
        prompt_specific = """Genera 3-4 características o beneficios clave. Formato EXACTO (una línea por característica): `icono:Título:Descripción` (icono Font Awesome v6, ej: `fa-solid fa-rocket`). Lista generada:"""
    elif field_type == 'services':
        prompt_specific = """Genera 3-4 servicios principales. Formato EXACTO (una línea por servicio): `icono:Título del Servicio:Descripción breve` (icono Font Awesome v6 relevante, ej: `fa-solid fa-laptop-code`). Lista generada:"""
    elif field_type == 'testimonials':
        prompt_specific = """Genera 2-3 testimonios CORTOS y creíbles (ficticios). Formato EXACTO (una línea por testimonio): `"Cita." - Nombre Ficticio, Cargo/Empresa Ficticia`. Testimonios generados:"""
    else:
        return jsonify({"error": "Tipo de campo no soportado."}), 400

    full_prompt = prompt_base + prompt_specific

    # Llamada a la API de Gemini
    try:
        print(f"--- Enviando prompt a Gemini para {field_type} ---")
        response = model.generate_content(full_prompt)
        generated_text = response.text if hasattr(response, 'text') else ""
        print(f"--- Respuesta de Gemini recibida ---")
        # Podríamos añadir validación del formato de respuesta aquí
        return jsonify({"generated_content": generated_text.strip()})
    except Exception as e:
        print(f"Error llamando a la API de Gemini: {e}")
        traceback.print_exc() # Log completo del error
        # Devolver un error más informativo si es posible, si no, genérico
        error_message = f"Error IA: {type(e).__name__}" if isinstance(e, genai.types.generation_types.StopCandidateException) else "No se pudo generar el contenido con IA."
        return jsonify({"error": error_message}), 500

@app.route('/download', methods=['POST'])
def download():
    """Genera y envía un archivo ZIP con el HTML, CSS y SVGs."""
    current_year = datetime.datetime.now().year
    memory_file = io.BytesIO() # Archivo ZIP en memoria

    try:
        # 1. Obtener y validar datos de configuración del formulario oculto
        json_string = request.form.get('page_data_json')
        if not json_string: raise ValueError("No se recibieron datos de configuración.")
        try: page_data = json.loads(json_string) # Datos base (sin SVGs/DataURLs)
        except json.JSONDecodeError: raise ValueError("Los datos de configuración recibidos son inválidos (JSON).")

        # 2. Regenerar los SVGs necesarios basados en la configuración
        logo_svg = generate_svg_logo(
            page_data.get('name',''), page_data.get('logo_style'), page_data.get('logo_shape'),
            page_data.get('color_primary'), page_data.get('color_secondary')
        )
        hero_svg = None
        if page_data.get('hero_background_type') == 'pattern':
            hero_svg = generate_svg_hero_pattern(
                page_data.get('hero_pattern_style'), page_data.get('color_primary'),
                page_data.get('color_secondary'), opacity=0.08
            )

        # 3. Preparar el diccionario de datos COMPLETO para renderizar el HTML descargable
        d_data = page_data.copy() # Copiar datos base
        d_data['logo_src'] = 'images/logo.svg' if logo_svg else '' # Ruta relativa para el ZIP
        d_data['hero_pattern_src'] = 'images/hero_pattern.svg' if hero_svg else None # Ruta relativa
        d_data['image_hero_url'] = page_data.get('image_hero_url', '') # Mantener URL si existe

        # Recalcular CSS de fondo para la sección .hero
        if page_data.get('hero_background_type') == 'gradient':
            color2 = page_data.get('color_secondary', '#ffffff')
            if color2 == '#ffffff': color2 = f"color-mix(in srgb, {page_data.get('color_primary', '#007bff')} 70%, black)"
            d_data['hero_background_css'] = f"linear-gradient(135deg, {page_data.get('color_primary', '#007bff')}, {color2})"
        elif page_data.get('hero_background_type') == 'color':
            d_data['hero_background_css'] = page_data.get('color_primary', '#007bff')
        else: # pattern or image_url - El fondo se aplica de otra forma
            d_data['hero_background_css'] = None

        # Asegurar que todos los campos _raw necesarios existan en d_data para evitar errores en plantilla
        for key in ['features_raw', 'services_raw', 'testimonials_raw', 'portfolio_raw', 'social_links_raw']:
             d_data.setdefault(key, '')

        # 4. Renderizar la plantilla HTML con los datos preparados
        html_content = render_template(
            'preview.html',
            data=d_data, # Usar datos con rutas relativas y CSS calculado
            current_year=current_year,
            is_download=True # Flag crucial para usar rutas relativas en la plantilla
        )

        # 5. Leer el archivo CSS usando una ruta robusta y segura
        css_content = ''
        css_path = os.path.join(app.static_folder, 'css', 'style.css')
        try:
            # Validar que la ruta está dentro de la carpeta static permitida
            if os.path.commonpath([app.static_folder]) == os.path.commonpath([app.static_folder, css_path]):
                 with open(css_path, 'r', encoding='utf-8') as f:
                     css_content = f.read()
            else:
                 print(f"ADVERTENCIA: Intento de acceso a CSS fuera de la carpeta static: {css_path}")
        except FileNotFoundError: print(f"ADVERTENCIA: Archivo CSS no encontrado en {css_path}")
        except Exception as e: print(f"ADVERTENCIA: Error al leer CSS '{css_path}': {e}"); traceback.print_exc()

        # 6. Crear el archivo ZIP en memoria y añadir los archivos
        with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr('index.html', html_content)
            # Añadir CSS sólo si se leyó y crear su carpeta
            if css_content: zf.writestr('css/style.css', css_content)
            # Añadir SVGs si se generaron y crear carpeta images
            if logo_svg or hero_svg:
                # Crear entrada de directorio (buena práctica)
                if not any(zi.filename == 'images/' for zi in zf.filelist):
                    zf.mkdir('images/')
                if logo_svg: zf.writestr('images/logo.svg', logo_svg)
                if hero_svg: zf.writestr('images/hero_pattern.svg', hero_svg)

        memory_file.seek(0) # Rebobinar el buffer del archivo en memoria

        # 7. Enviar el archivo ZIP al navegador
        safe_name = ''.join(c if c.isalnum() or c in ['-', '_'] else '_' for c in page_data.get('name', 'landing_page'))
        safe_name = safe_name.strip('_') # Eliminar guiones bajos al inicio/final
        if not safe_name: safe_name = 'landing_page' # Fallback final
        return send_file(
            memory_file,
            mimetype='application/zip',
            as_attachment=True,
            download_name=f"{safe_name}.zip"
        )

    # --- Manejo de Errores Específicos y Generales ---
    except json.JSONDecodeError:
        print("Error: Datos de descarga inválidos (JSON)."); traceback.print_exc()
        return "Error: Los datos recibidos para la descarga no son válidos.", 400
    except ValueError as ve: # Para errores de validación propios
        print(f"Error de valor en descarga: {ve}"); traceback.print_exc()
        return f"Error en los datos proporcionados: {ve}", 400
    except Exception as e:
        print(f"Error crítico durante la generación del ZIP: {e}")
        traceback.print_exc() # Log completo para depuración
        return "Error interno del servidor al generar el archivo ZIP. Por favor, inténtalo de nuevo o contacta al administrador.", 500

# Necesario para ejecutar localmente con `python app.py`
# if __name__ == '__main__':
#     # ¡IMPORTANTE!: Quita debug=True antes de desplegar en producción
#     # host='0.0.0.0' permite conexiones desde otras máquinas en la red local
#     app.run(debug=True, host='0.0.0.0', port=5001)
