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

# Configuración de Clave Secreta para Sesiones (MUY IMPORTANTE para producción)
app.secret_key = os.environ.get('FLASK_SECRET_KEY')
if not app.secret_key:
    print("ADVERTENCIA: FLASK_SECRET_KEY no está configurada. Usando clave de desarrollo insegura.")
    app.secret_key = 'desarrollo-cambiar-esta-clave-secreta-insegura' # SOLO PARA DESARROLLO

app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 # 16 MB

# Configuración de Google Gemini API
try:
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
    if not GEMINI_API_KEY:
        print("Advertencia: GEMINI_API_KEY no configurada. Funcionalidad IA desactivada.")
        model = None
    else:
        genai.configure(api_key=GEMINI_API_KEY)
        # Considera añadir generation_config y safety_settings si es necesario
        model = genai.GenerativeModel(model_name="gemini-1.5-pro-latest") # O gemini-1.0-pro
except Exception as e:
    print(f"Error configurando la API de Gemini: {e}")
    model = None

# --- Funciones Auxiliares (SIN CAMBIOS)---
def generate_svg_logo(name, style='text', shape='none', color_primary='#007bff', color_secondary='#ffffff', font_family='Poppins, sans-serif'):
    if not name: name = "Logo"
    name = escape(name); text_content = name; font_size = 35
    if style == 'initials': words = name.split(); text_content = (words[0][0]+words[-1][0]).upper() if len(words)>=2 else (words[0][0].upper() if len(words)==1 and len(words[0])>0 else name[0].upper() if name else 'L'); font_size=45
    svg_width=100;svg_height=100;shape_element='';text_x=50;text_y=50;text_color=color_secondary
    try: r,g,b=int(color_primary[1:3],16),int(color_primary[3:5],16),int(color_primary[5:7],16); lum=(.299*r+.587*g+.114*b)/255; text_color = '#333333' if lum>0.5 and color_secondary=='#ffffff' else ('#ffffff' if lum<=0.5 and color_secondary=='#000000' else color_secondary)
    except ValueError: pass
    if shape=='circle': shape_element=f'<circle cx="50" cy="50" r="50" fill="{color_primary}"/>'
    elif shape=='square': shape_element=f'<rect width="100" height="100" rx="10" ry="10" fill="{color_primary}"/>'
    else: est_width = len(text_content)*(font_size*0.65); svg_width=max(60, est_width); svg_height=font_size*1.2; text_x=svg_width/2; text_y=svg_height*0.65; text_color=color_primary
    svg=f'''<svg width="{int(svg_width)}" height="{int(svg_height)}" viewBox="0 0 {int(svg_width)} {int(svg_height)}" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMid meet">{shape_element}<text x="{text_x}" y="{text_y}" font-family="{font_family}" font-size="{font_size}" fill="{text_color}" text-anchor="middle" dominant-baseline="middle" font-weight="600">{text_content}</text></svg>'''
    return svg.replace('\n','').replace('    ','')
def generate_svg_hero_pattern(style='waves', color_primary='#007bff', color_secondary='#6c757d', opacity=0.1):
    p='';pid=f"p-{style}";ps=50;op=max(0.01, min(1, opacity))
    if style=='waves': ps=100; p=f'<path d="M 0 {ps/2} Q {ps/4} {ps/2-ps*op*0.7} {ps/2} {ps/2} T {ps} {ps/2}" stroke="{color_secondary}" stroke-width="3" fill="none" opacity="{op}"/><path d="M 0 {ps*0.6} Q {ps/4} {ps*0.6+ps*op*0.6} {ps/2} {ps*0.6} T {ps} {ps*0.6}" stroke="{color_secondary}" stroke-width="2" fill="none" opacity="{op*0.8}"/>'
    elif style=='dots': ps=20; p=f'<circle cx="{ps/2}" cy="{ps/2}" r="{ps*0.1}" fill="{color_secondary}" opacity="{op}"/>'
    elif style=='lines': ps=15; p=f'<path d="M 0 0 L {ps} {ps} M {ps} 0 L 0 {ps}" stroke="{color_secondary}" stroke-width="1" opacity="{op}"/>'
    elif style=='triangles': ps=40; p=f'<path d="M 0 0 L {ps/2} {ps} L {ps} 0 Z" fill="{color_secondary}" opacity="{op*0.5}"/><path d="M {ps/2} 0 L 0 {ps} L {ps} {ps} Z" fill="{color_secondary}" opacity="{op*0.7}"/>'
    else: ps=20; p=f'<rect width="{ps*0.5}" height="{ps*0.5}" fill="{color_secondary}" opacity="{op}"/>'
    svg=f'''<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="100%"><defs><pattern id="{pid}" patternUnits="userSpaceOnUse" width="{ps}" height="{ps}">{p}</pattern></defs><rect width="100%" height="100%" fill="url(#{pid})" /></svg>'''
    return svg.replace('\n','').replace('    ','')
def svg_to_data_url(svg_string):
    if not svg_string: return ""
    try: encoded = base64.b64encode(svg_string.encode('utf-8')).decode('utf-8'); return f"data:image/svg+xml;base64,{encoded}"
    except Exception as e: print(f"Error Data URL: {e}"); return ""

# --- Rutas Flask ---

@app.route('/', methods=['GET', 'POST'])
def index():
    """Maneja la carga del formulario (GET) y la generación de la preview (POST)."""
    current_year = datetime.datetime.now().year
    if request.method == 'POST':
        page_data = {k: request.form.get(k, '') for k in request.form} # Forma más genérica de recoger datos
        # Valores por defecto para campos clave si están vacíos
        page_data['page_type'] = page_data.get('page_type') or 'personal'
        page_data['color_primary'] = page_data.get('color_primary') or '#007bff'
        page_data['color_secondary'] = page_data.get('color_secondary') or '#ffffff'
        page_data['logo_style'] = page_data.get('logo_style') or 'text'
        page_data['logo_shape'] = page_data.get('logo_shape') or 'none'
        page_data['hero_background_type'] = page_data.get('hero_background_type') or 'color'
        page_data['hero_pattern_style'] = page_data.get('hero_pattern_style') or 'waves'
        # Renombrar claves del formulario a las usadas internamente (si son diferentes)
        page_data['portfolio_raw'] = page_data.pop('portfolio_items', '')
        page_data['services_raw'] = page_data.pop('services', '')
        page_data['features_raw'] = page_data.pop('features', '')
        page_data['testimonials_raw'] = page_data.pop('testimonials', '')
        page_data['social_links_raw'] = page_data.pop('social_links', '')

        # Generar SVGs
        logo_svg = generate_svg_logo(page_data.get('name',''), page_data['logo_style'], page_data['logo_shape'], page_data['color_primary'], page_data['color_secondary'])
        page_data['logo_svg_string'] = logo_svg; page_data['logo_src'] = svg_to_data_url(logo_svg)
        hero_pattern_svg = None; page_data['hero_pattern_src'] = None; page_data['hero_background_css'] = None
        hero_bg_type = page_data['hero_background_type']
        if hero_bg_type == 'pattern': hero_pattern_svg = generate_svg_hero_pattern(page_data['hero_pattern_style'], page_data['color_primary'], page_data['color_secondary'], opacity=0.08); page_data['hero_background_svg_pattern_string'] = hero_pattern_svg; page_data['hero_pattern_src'] = svg_to_data_url(hero_pattern_svg)
        elif hero_bg_type == 'gradient': color2 = page_data['color_secondary'] if page_data['color_secondary'] != '#ffffff' else f"color-mix(in srgb, {page_data['color_primary']} 70%, black)"; page_data['hero_background_css'] = f"linear-gradient(135deg, {page_data['color_primary']}, {color2})"
        elif hero_bg_type != 'image_url': page_data['hero_background_css'] = page_data['color_primary']

        session['form_data'] = page_data # Guardar en sesión
        try: data_to_serialize = {k:v for k,v in page_data.items() if not k.endswith('_svg_string') and not k.endswith('_src')}; data_json = json.dumps(data_to_serialize)
        except Exception as e: print(f"JSON Error: {e}"); data_json = "{}"
        return render_template('preview.html', data=page_data, current_year=current_year, data_json=data_json)

    # GET: Cargar datos de sesión
    form_data = session.get('form_data', {})
    return render_template('index.html', current_year=current_year, form_data=form_data)

@app.route('/generate-ai-content', methods=['POST'])
def generate_ai_content():
    """Endpoint para generar contenido con IA (Gemini)."""
    if not model: return jsonify({"error": "Modelo IA no configurado."}), 503
    data = request.get_json(); headline = data.get('headline'); description = data.get('description'); field_type = data.get('field_type')
    if not (data and headline and description and field_type): return jsonify({"error": "Faltan datos (headline, description, field_type)."}), 400
    prompt_base = f"""Eres un asistente de marketing experto creando contenido conciso y atractivo para páginas de aterrizaje en español. Basándote SOLO en Título: "{headline}" y Descripción: "{description}", genera contenido para '{field_type}'. Sigue estrictamente el formato solicitado."""
    prompt_specific = ""
    if field_type == 'features': prompt_specific = """ Genera 3-4 características clave. Formato EXACTO (una línea por característica): `icono:Título:Descripción` (icono Font Awesome v6). Lista generada:"""
    elif field_type == 'services': prompt_specific = """ Genera 3-4 servicios principales. Formato EXACTO (una línea por servicio): `icono:Título del Servicio:Descripción breve` (icono Font Awesome v6 relevante). Lista generada:"""
    elif field_type == 'testimonials': prompt_specific = """ Genera 2-3 testimonios CORTOS y creíbles (ficticios). Formato EXACTO (una línea por testimonio): `"Cita." - Nombre Ficticio, Cargo/Empresa Ficticia`. Testimonios generados:"""
    else: return jsonify({"error": "Tipo de campo no soportado."}), 400
    full_prompt = prompt_base + prompt_specific
    try:
        print(f"--- Enviando prompt a Gemini para {field_type} ---")
        response = model.generate_content(full_prompt); generated_text = response.text if hasattr(response, 'text') else ""
        print(f"--- Respuesta de Gemini recibida ---")
        return jsonify({"generated_content": generated_text.strip()})
    except Exception as e: print(f"Error API Gemini: {e}"); traceback.print_exc(); return jsonify({"error": "No se pudo generar el contenido con IA en este momento."}), 500


@app.route('/download', methods=['POST'])
def download():
    """Genera y envía un archivo ZIP con el HTML, CSS y SVGs."""
    current_year = datetime.datetime.now().year
    memory_file = io.BytesIO() # Archivo ZIP en memoria

    try:
        # 1. Obtener y validar datos de configuración del formulario
        json_string = request.form.get('page_data_json')
        if not json_string:
            raise ValueError("No se recibieron datos de configuración para la descarga.")
        page_data = json.loads(json_string) # Datos base (sin SVGs/DataURLs)

        # 2. Regenerar los SVGs necesarios basados en la configuración
        logo_svg = generate_svg_logo(
            page_data.get('name', ''), page_data.get('logo_style', 'text'), page_data.get('logo_shape', 'none'),
            page_data.get('color_primary', '#007bff'), page_data.get('color_secondary', '#ffffff')
        )
        hero_svg = None
        if page_data.get('hero_background_type') == 'pattern':
            hero_svg = generate_svg_hero_pattern(
                page_data.get('hero_pattern_style', 'waves'), page_data.get('color_primary', '#007bff'),
                page_data.get('color_secondary', '#6c757d'), opacity=0.08
            )

        # 3. Preparar el diccionario de datos para renderizar el HTML descargable
        #    Usando rutas relativas para los assets que irán en el ZIP.
        download_page_data = page_data.copy() # Copia los datos base
        download_page_data['logo_src'] = 'images/logo.svg' if logo_svg else ''
        download_page_data['hero_pattern_src'] = 'images/hero_pattern.svg' if hero_svg else None
        # Recalcular el CSS de fondo si es necesario (color/gradiente)
        if page_data.get('hero_background_type') == 'gradient':
            color2 = page_data.get('color_secondary', '#ffffff')
            if color2 == '#ffffff': color2 = f"color-mix(in srgb, {page_data.get('color_primary', '#007bff')} 70%, black)"
            download_page_data['hero_background_css'] = f"linear-gradient(135deg, {page_data.get('color_primary', '#007bff')}, {color2})"
        elif page_data.get('hero_background_type') == 'color':
            download_page_data['hero_background_css'] = page_data.get('color_primary', '#007bff')
        else: # pattern or image_url
            download_page_data['hero_background_css'] = None
        # Asegurar que todos los campos _raw necesarios estén presentes
        for key in ['features_raw', 'services_raw', 'testimonials_raw', 'portfolio_raw', 'social_links_raw']:
             download_page_data.setdefault(key, '') # Añadir si falta con valor vacío

        # 4. Renderizar la plantilla HTML con los datos preparados
        html_content = render_template(
            'preview.html',
            data=download_page_data,
            current_year=current_year,
            is_download=True # Flag para usar rutas relativas en la plantilla
        )

        # 5. Leer el archivo CSS usando una ruta robusta
        css_content = ''
        # --- CORRECCIÓN: Usar app.static_folder ---
        css_path = os.path.join(app.static_folder, 'css', 'style.css')
        try:
            with open(css_path, 'r', encoding='utf-8') as f:
                css_content = f.read()
        except FileNotFoundError:
            print(f"ADVERTENCIA: Archivo CSS no encontrado en la ruta esperada: {css_path}")
        except Exception as e:
            print(f"ADVERTENCIA: Error al leer el archivo CSS '{css_path}': {e}")
            traceback.print_exc() # Log completo del error de lectura

        # 6. Crear el archivo ZIP en memoria y añadir los archivos
        with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
            # Añadir HTML
            zf.writestr('index.html', html_content)
            # Añadir CSS (solo si se leyó correctamente)
            if css_content:
                zf.writestr('css/style.css', css_content)
            else:
                 # Opcional: añadir un CSS vacío o un comentario en HTML si falla
                 print("Información: No se incluyó style.css en el ZIP porque no se pudo leer.")

            # Añadir carpeta 'images' y SVGs si se generaron
            added_images_dir = False
            if logo_svg:
                if not added_images_dir: zf.mkdir('images/'); added_images_dir = True
                zf.writestr('images/logo.svg', logo_svg)
            if hero_svg:
                if not added_images_dir: zf.mkdir('images/'); added_images_dir = True
                zf.writestr('images/hero_pattern.svg', hero_svg)

        memory_file.seek(0) # Rebobinar el buffer del archivo en memoria

        # 7. Enviar el archivo ZIP al navegador
        safe_name = ''.join(c if c.isalnum() else '_' for c in page_data.get('name', 'landing_page'))
        if not safe_name: safe_name = 'landing_page' # Fallback si el nombre resultante es vacío
        return send_file(
            memory_file,
            mimetype='application/zip',
            as_attachment=True,
            download_name=f"{safe_name}.zip"
        )

    # --- Manejo de Errores Específicos y Generales ---
    except json.JSONDecodeError:
        print("Error: Datos de descarga inválidos (JSON).")
        traceback.print_exc()
        return "Error: Los datos recibidos para la descarga no son válidos.", 400
    except ValueError as ve:
        print(f"Error de valor en descarga: {ve}")
        traceback.print_exc()
        return f"Error en los datos proporcionados: {ve}", 400
    except Exception as e:
        print(f"Error crítico durante la generación del ZIP: {e}")
        traceback.print_exc() # Log completo para depuración
        return "Error interno del servidor al generar el archivo ZIP. Por favor, inténtalo de nuevo o contacta al administrador.", 500

# Necesario para ejecutar localmente (descomentar si es necesario)
# if __name__ == '__main__':
#     # Asegúrate de quitar debug=True en un entorno de producción
#     app.run(debug=True, host='0.0.0.0', port=5001)
