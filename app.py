# app.py
from flask import Flask, render_template, request, send_file, jsonify
import datetime
import base64
import io
import zipfile
import json
from markupsafe import escape
import os
import google.generativeai as genai

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# --- Configurar Gemini (como antes) ---
try:
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
    if not GEMINI_API_KEY: print("Advertencia: Variable GEMINI_API_KEY no configurada.")
    else:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel(model_name="gemini-1.5-pro-latest")
except Exception as e:
    print(f"Error configurando Gemini: {e}")
    model = None

# --- (Funciones SVG y Data URL SIN CAMBIOS) ---
def generate_svg_logo(name, style='text', shape='none', color_primary='#007bff', color_secondary='#ffffff', font_family='Poppins, sans-serif'):
    name = escape(name); text_content = name; font_size = 35
    if style == 'initials':
        words = name.split(); text_content = (words[0][0] + words[-1][0]).upper() if len(words) >= 2 else (words[0][0].upper() if len(words) == 1 and len(words[0]) > 0 else 'L'); font_size = 45
    svg_width = 100; svg_height = 100; shape_element = ''; text_x = 50; text_y = 50; text_color = color_secondary
    try:
        r, g, b = int(color_primary[1:3], 16), int(color_primary[3:5], 16), int(color_primary[5:7], 16); lum = (0.299*r + 0.587*g + 0.114*b)/255
        if lum > 0.5: text_color = color_secondary if color_secondary != '#ffffff' else '#333333'
        else: text_color = color_secondary if color_secondary != '#000000' else '#ffffff'
    except: pass
    if shape == 'circle': shape_element = f'<circle cx="50" cy="50" r="50" fill="{color_primary}"/>'
    elif shape == 'square': shape_element = f'<rect width="100" height="100" rx="10" ry="10" fill="{color_primary}"/>'
    else: svg_width = len(text_content)*(font_size*0.6); svg_height=font_size*1.2; text_x=svg_width/2; text_y=svg_height*0.7; text_color=color_primary
    svg = f'''<svg width="{int(svg_width)}" height="{int(svg_height)}" viewBox="0 0 {int(svg_width)} {int(svg_height)}" xmlns="http://www.w3.org/2000/svg">{shape_element}<text x="{text_x}" y="{text_y}" font-family="{font_family}" font-size="{font_size}" fill="{text_color}" text-anchor="middle" dominant-baseline="middle" font-weight="600">{text_content}</text></svg>'''
    return svg.replace('\n','').replace('    ','')

def generate_svg_hero_pattern(style='waves', color_primary='#007bff', color_secondary='#6c757d', opacity=0.1):
    p = ''; pid = f"p-{style}"; ps = 50
    if style=='waves': ps=100; p=f'<path d="M 0 50 Q 25 {100-25*opacity*100} 50 50 T 100 50" stroke="{color_secondary}" stroke-width="3" fill="none" opacity="{opacity}"/><path d="M 0 60 Q 25 {110-25*opacity*100} 50 60 T 100 60" stroke="{color_secondary}" stroke-width="2" fill="none" opacity="{opacity*0.8}"/>'
    elif style=='dots': ps=20; p=f'<circle cx="10" cy="10" r="2" fill="{color_secondary}" opacity="{opacity}"/>'
    elif style=='lines': ps=15; p=f'<path d="M 0 0 L {ps} {ps} M {ps} 0 L 0 {ps}" stroke="{color_secondary}" stroke-width="1" opacity="{opacity}"/>'
    elif style=='triangles': ps=40; p=f'<path d="M 0 0 L {ps/2} {ps} L {ps} 0 Z" fill="{color_secondary}" opacity="{opacity*0.5}"/><path d="M {ps/2} 0 L 0 {ps} L {ps} {ps} Z" fill="{color_secondary}" opacity="{opacity*0.7}"/>'
    else: ps=20; p=f'<rect width="10" height="10" fill="{color_secondary}" opacity="{opacity}"/>'
    svg=f'''<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="100%"><defs><pattern id="{pid}" patternUnits="userSpaceOnUse" width="{ps}" height="{ps}">{p}</pattern></defs><rect width="100%" height="100%" fill="url(#{pid})" /></svg>'''
    return svg.replace('\n','').replace('    ','')

def svg_to_data_url(svg_string):
    if not svg_string: return ""
    encoded = base64.b64encode(svg_string.encode('utf-8')).decode('utf-8')
    return f"data:image/svg+xml;base64,{encoded}"

# --- Rutas Flask ---

@app.route('/', methods=['GET', 'POST'])
def index():
    current_year = datetime.datetime.now().year
    if request.method == 'POST':
        page_data = {
            # ... (Datos anteriores) ...
            'page_type': request.form.get('page_type', 'personal'),
            'name': request.form.get('name', 'Mi Nombre/Empresa'),
            'headline': request.form.get('headline', 'Una propuesta de valor increíble'),
            'description': request.form.get('description', ''),
            'cta_text': request.form.get('cta_text', 'Saber Más'),
            'contact_email': request.form.get('contact_email'),
            'contact_phone': request.form.get('contact_phone', ''),
            'social_links_raw': request.form.get('social_links', ''),
            'color_primary': request.form.get('color_primary', '#007bff'),
            'color_secondary': request.form.get('color_secondary', '#ffffff'),
            'features_raw': request.form.get('features', ''),
            'testimonials_raw': request.form.get('testimonials', ''),
            'logo_style': request.form.get('logo_style', 'text'),
            'logo_shape': request.form.get('logo_shape', 'none'),
            'hero_background_type': request.form.get('hero_background_type', 'color'),
            'hero_pattern_style': request.form.get('hero_pattern_style', 'waves'),
            'image_hero_url': request.form.get('image_hero_url', ''),
            # --- NUEVO CAMPO PORTAFOLIO ---
            'portfolio_raw': request.form.get('portfolio_items', ''),
        }

        # --- (Generación SVG Logo y Hero Background como antes) ---
        logo_svg_string = generate_svg_logo(
            page_data['name'], page_data['logo_style'], page_data['logo_shape'],
            page_data['color_primary'], page_data['color_secondary']
        )
        page_data['logo_svg_string'] = logo_svg_string
        page_data['logo_src'] = svg_to_data_url(logo_svg_string)

        page_data['hero_background_svg_pattern_string'] = None
        page_data['hero_pattern_src'] = None
        page_data['hero_background_css'] = None
        hero_bg_type = page_data['hero_background_type']
        # ... (lógica hero background sin cambios) ...
        if hero_bg_type == 'pattern':
            hero_pattern_svg_string = generate_svg_hero_pattern(
                page_data['hero_pattern_style'], page_data['color_primary'],
                page_data['color_secondary'], opacity=0.08
            )
            page_data['hero_background_svg_pattern_string'] = hero_pattern_svg_string
            page_data['hero_pattern_src'] = svg_to_data_url(hero_pattern_svg_string)
        elif hero_bg_type == 'gradient':
             color2 = page_data['color_secondary'] if page_data['color_secondary'] != '#ffffff' else f"color-mix(in srgb, {page_data['color_primary']} 70%, black)"
             page_data['hero_background_css'] = f"linear-gradient(135deg, {page_data['color_primary']}, {color2})"
        elif hero_bg_type != 'image_url': # color
            page_data['hero_background_css'] = page_data['color_primary']

        # --- Preparar JSON para descarga (excluyendo SVGs largos) ---
        try:
            data_to_serialize = {k: v for k, v in page_data.items() if not k.endswith('_svg_string') and not k.endswith('_src')}
            data_json = json.dumps(data_to_serialize)
        except Exception as e:
             print(f"Error serializando page_data a JSON: {e}"); data_json = "{}"

        return render_template(
            'preview.html', data=page_data, current_year=current_year, data_json=data_json
        )

    # GET request
    return render_template('index.html', current_year=current_year)


# --- (Endpoint /generate-ai-content SIN CAMBIOS) ---
@app.route('/generate-ai-content', methods=['POST'])
def generate_ai_content():
    if not model: return jsonify({"error": "Modelo IA no configurado."}), 503
    data = request.get_json()
    if not data: return jsonify({"error": "Petición inválida."}), 400
    headline = data.get('headline'); description = data.get('description'); field_type = data.get('field_type')
    if not headline or not description or not field_type: return jsonify({"error": "Faltan datos (headline, description, field_type)."}), 400

    prompt = f"""Eres un asistente de marketing experto creando contenido conciso y atractivo para páginas de aterrizaje. Basándote SOLO en Título: "{headline}" y Descripción: "{description}", genera contenido para '{field_type}'."""
    if field_type == 'features':
        prompt += """ Genera 3-4 características/beneficios clave en formato `icono:Título:Descripción` (icono de Font Awesome v6, uno por línea). Sé breve. Lista generada:"""
    elif field_type == 'testimonials':
        prompt += """ Genera 2-3 testimonios CORTOS y creíbles (ficticios) en formato `"Cita." - Nombre Ficticio, Cargo/Empresa Ficticia` (uno por línea). Testimonios generados:"""
    else: return jsonify({"error": "Tipo de campo no soportado."}), 400

    try:
        response = model.generate_content(prompt); generated_text = response.text.strip()
        return jsonify({"generated_content": generated_text})
    except Exception as e: print(f"Error API Gemini: {e}"); return jsonify({"error": f"Error IA: {e}"}), 500

# --- Ruta de Descarga (Modificada para incluir portfolio_raw) ---
@app.route('/download', methods=['POST'])
def download():
    current_year = datetime.datetime.now().year
    try:
        json_string = request.form.get('page_data_json')
        if not json_string: return "Error: No se recibieron datos.", 400
        page_data = json.loads(json_string) # Configuración base (SIN SVGs/DataUrls)

        # --- Regenerar SVGs ---
        logo_svg_string = generate_svg_logo( page_data.get('name',''), page_data.get('logo_style'), page_data.get('logo_shape'), page_data.get('color_primary'), page_data.get('color_secondary') )
        hero_pattern_svg_string = None
        if page_data.get('hero_background_type') == 'pattern': hero_pattern_svg_string = generate_svg_hero_pattern( page_data.get('hero_pattern_style'), page_data.get('color_primary'), page_data.get('color_secondary'), opacity=0.08 )

        # --- Preparar datos para HTML descargado ---
        download_page_data = page_data.copy()
        download_page_data['logo_src'] = 'images/logo.svg' if logo_svg_string else ''
        download_page_data['hero_pattern_src'] = 'images/hero_pattern.svg' if hero_pattern_svg_string else None
        # (lógica hero_background_css como antes)
        if page_data.get('hero_background_type') == 'gradient':
             color2 = page_data['color_secondary'] if page_data.get('color_secondary', '#ffffff') != '#ffffff' else f"color-mix(in srgb, {page_data.get('color_primary')} 70%, black)"
             download_page_data['hero_background_css'] = f"linear-gradient(135deg, {page_data.get('color_primary')}, {color2})"
        elif page_data.get('hero_background_type') == 'color':
            download_page_data['hero_background_css'] = page_data.get('color_primary')
        else: download_page_data['hero_background_css'] = None
        # Incluir portfolio_raw para que la plantilla lo renderice
        download_page_data['portfolio_raw'] = page_data.get('portfolio_raw', '')


        # --- Renderizar HTML, Leer CSS, Crear ZIP (como antes) ---
        html_content = render_template('preview.html', data=download_page_data, current_year=current_year, is_download=True)
        css_path = 'static/css/style.css'; css_content = ''
        try:
            with open(css_path, 'r', encoding='utf-8') as f: css_content = f.read()
        except Exception as e: print(f"Advertencia: No se pudo leer {css_path}: {e}") # No detener la descarga por CSS

        memory_file = io.BytesIO()
        with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr('index.html', html_content)
            if css_content: zf.writestr('css/style.css', css_content) # Solo añadir si se leyó
            if logo_svg_string: zf.writestr('images/logo.svg', logo_svg_string)
            if hero_pattern_svg_string: zf.writestr('images/hero_pattern.svg', hero_pattern_svg_string)
            # Podríamos añadir una carpeta 'portfolio_images' si gestionáramos subidas, pero no es el caso.
        memory_file.seek(0)

        # --- Enviar ZIP ---
        safe_name = ''.join(c if c.isalnum() else '_' for c in page_data.get('name','landing'))
        return send_file(memory_file, mimetype='application/zip', as_attachment=True, download_name=f"{safe_name}_page.zip")

    except json.JSONDecodeError: return "Error: Datos de descarga inválidos.", 400
    except Exception as e:
        print(f"Error en descarga: {e}"); import traceback; traceback.print_exc()
        return f"Error interno al generar ZIP: {e}", 500
