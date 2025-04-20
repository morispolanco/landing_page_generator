# app.py
from flask import Flask, render_template, request, send_file, jsonify, session # Añadir session
import datetime
import base64
import io
import zipfile
import json
from markupsafe import escape
import os
import google.generativeai as genai

app = Flask(__name__)

# --- CLAVE SECRETA PARA SESIONES (¡MUY IMPORTANTE!) ---
# Genera una clave segura para producción y guárdala como variable de entorno.
# Para desarrollo local, puedes usar os.urandom o una cadena fija (menos seguro).
# ¡NUNCA subas una clave fija a un repositorio público!
app.secret_key = os.environ.get('FLASK_SECRET_KEY', os.urandom(24))
# Ejemplo de cómo establecerla si no está en entorno (SOLO DESARROLLO):
# if not app.secret_key or app.secret_key == os.urandom(24):
#     print("ADVERTENCIA: Usando clave secreta de desarrollo. Establece FLASK_SECRET_KEY en producción.")
#     app.secret_key = 'desarrollo-cambiar-esta-clave-secreta'


app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 # 16 MB

# --- Configurar Gemini ---
try:
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
    if not GEMINI_API_KEY:
        print("Advertencia: La variable de entorno GEMINI_API_KEY no está configurada.")
        model = None
    else:
        genai.configure(api_key=GEMINI_API_KEY)
        # Considera añadir configuraciones de generación y seguridad aquí si es necesario
        model = genai.GenerativeModel(model_name="gemini-1.5-pro-latest") # O "gemini-pro"
except Exception as e:
    print(f"Error configurando Gemini: {e}")
    model = None # Indicar que el modelo no está disponible

# --- Funciones de Generación SVG ---
def generate_svg_logo(name, style='text', shape='none', color_primary='#007bff', color_secondary='#ffffff', font_family='Poppins, sans-serif'):
    """Genera un logo SVG simple."""
    name = escape(name) # Escapar el nombre
    text_content = name
    font_size = 35 # Ajustar tamaño de fuente base

    if style == 'initials':
        words = name.split()
        if len(words) >= 2: text_content = (words[0][0] + words[-1][0]).upper()
        elif len(words) == 1 and len(words[0]) > 0: text_content = words[0][0].upper()
        else: text_content = 'L' # Fallback
        font_size = 45 # Más grande para iniciales

    svg_width = 100; svg_height = 100; shape_element = ''; text_x = 50; text_y = 50; text_color = color_secondary
    try: # Simple contrast check
        r,g,b = int(color_primary[1:3],16),int(color_primary[3:5],16),int(color_primary[5:7],16); lum=(.299*r+.587*g+.114*b)/255
        # Basic logic: if background is light (>0.5) and secondary is pure white, use dark gray. If background is dark and secondary is pure black, use white. Otherwise, use secondary.
        text_color = '#333333' if lum > 0.5 and color_secondary=='#ffffff' else ('#ffffff' if lum <= 0.5 and color_secondary=='#000000' else color_secondary)
    except: pass # Ignore errors for invalid colors, use default secondary

    if shape == 'circle': shape_element = f'<circle cx="50" cy="50" r="50" fill="{color_primary}"/>'
    elif shape == 'square': shape_element = f'<rect width="100" height="100" rx="10" ry="10" fill="{color_primary}"/>'
    else: # 'none'
        # Estimate width/height based on text, adjust text position
        svg_width = max(100, len(text_content)*(font_size*0.65)) # Ensure minimum width
        svg_height=font_size*1.2; text_x=svg_width/2; text_y=svg_height*0.65; text_color=color_primary # Use primary color for text without shape

    # Ensure viewBox matches calculated width/height for proper scaling
    svg=f'''<svg width="{int(svg_width)}" height="{int(svg_height)}" viewBox="0 0 {int(svg_width)} {int(svg_height)}" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMid meet">{shape_element}<text x="{text_x}" y="{text_y}" font-family="{font_family}" font-size="{font_size}" fill="{text_color}" text-anchor="middle" dominant-baseline="middle" font-weight="600">{text_content}</text></svg>'''
    return svg.replace('\n','').replace('    ','') # Basic cleanup

def generate_svg_hero_pattern(style='waves', color_primary='#007bff', color_secondary='#6c757d', opacity=0.1):
    """Genera un patrón SVG simple para fondo."""
    p=''; pid=f"p-{style}"; ps=50; op=max(0.01, min(1, opacity)) # Clamp opacity
    if style=='waves': ps=100; p=f'<path d="M 0 {ps/2} Q {ps/4} {ps/2 - ps*op*0.7} {ps/2} {ps/2} T {ps} {ps/2}" stroke="{color_secondary}" stroke-width="3" fill="none" opacity="{op}"/><path d="M 0 {ps*0.6} Q {ps/4} {ps*0.6 + ps*op*0.6} {ps/2} {ps*0.6} T {ps} {ps*0.6}" stroke="{color_secondary}" stroke-width="2" fill="none" opacity="{op*0.8}"/>'
    elif style=='dots': ps=20; p=f'<circle cx="{ps/2}" cy="{ps/2}" r="{ps*0.1}" fill="{color_secondary}" opacity="{op}"/>'
    elif style=='lines': ps=15; p=f'<path d="M 0 0 L {ps} {ps} M {ps} 0 L 0 {ps}" stroke="{color_secondary}" stroke-width="1" opacity="{op}"/>'
    elif style=='triangles': ps=40; p=f'<path d="M 0 0 L {ps/2} {ps} L {ps} 0 Z" fill="{color_secondary}" opacity="{op*0.5}"/><path d="M {ps/2} 0 L 0 {ps} L {ps} {ps} Z" fill="{color_secondary}" opacity="{op*0.7}"/>'
    else: ps=20; p=f'<rect width="{ps*0.5}" height="{ps*0.5}" fill="{color_secondary}" opacity="{op}"/>'
    svg=f'''<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="100%"><defs><pattern id="{pid}" patternUnits="userSpaceOnUse" width="{ps}" height="{ps}">{p}</pattern></defs><rect width="100%" height="100%" fill="url(#{pid})" /></svg>'''
    return svg.replace('\n','').replace('    ','')

def svg_to_data_url(svg_string):
    """Convierte una cadena SVG a Data URL base64."""
    if not svg_string: return ""
    encoded = base64.b64encode(svg_string.encode('utf-8')).decode('utf-8')
    return f"data:image/svg+xml;base64,{encoded}"


# --- Rutas Flask ---

@app.route('/', methods=['GET', 'POST'])
def index():
    current_year = datetime.datetime.now().year

    if request.method == 'POST':
        # Recopilar datos del formulario
        page_data = {
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
            'portfolio_raw': request.form.get('portfolio_items', ''),
        }

        # Generar SVG Logo y Hero Background (y sus Data URLs para preview)
        logo_svg_string = generate_svg_logo( page_data['name'], page_data['logo_style'], page_data['logo_shape'], page_data['color_primary'], page_data['color_secondary'] )
        page_data['logo_svg_string'] = logo_svg_string # Guardar para posible descarga
        page_data['logo_src'] = svg_to_data_url(logo_svg_string) # Para mostrar en preview

        hero_pattern_svg_string = None
        page_data['hero_pattern_src'] = None
        page_data['hero_background_css'] = None
        hero_bg_type = page_data['hero_background_type']
        if hero_bg_type == 'pattern':
            hero_pattern_svg_string = generate_svg_hero_pattern( page_data['hero_pattern_style'], page_data['color_primary'], page_data['color_secondary'], opacity=0.08 )
            page_data['hero_background_svg_pattern_string'] = hero_pattern_svg_string # Para descarga
            page_data['hero_pattern_src'] = svg_to_data_url(hero_pattern_svg_string) # Para preview
        elif hero_bg_type == 'gradient':
             color2 = page_data['color_secondary'] if page_data['color_secondary'] != '#ffffff' else f"color-mix(in srgb, {page_data['color_primary']} 70%, black)"
             page_data['hero_background_css'] = f"linear-gradient(135deg, {page_data['color_primary']}, {color2})"
        elif hero_bg_type != 'image_url': # 'color' or fallback
            page_data['hero_background_css'] = page_data['color_primary']
        # Si es 'image_url', se usa page_data['image_hero_url'] directamente en la plantilla

        # <<< GUARDAR DATOS EN SESIÓN >>>
        session['form_data'] = page_data # Guarda los datos del formulario actual

        # Preparar JSON para el botón de descarga (excluyendo SVGs largos y Data URLs)
        try:
            data_to_serialize = {k: v for k, v in page_data.items() if not k.endswith('_svg_string') and not k.endswith('_src')}
            data_json = json.dumps(data_to_serialize)
        except Exception as e:
             print(f"Error serializando page_data a JSON: {e}"); data_json = "{}"

        # Renderizar la vista previa
        return render_template(
            'preview.html',
            data=page_data, # Pasar todos los datos (incluyendo src y strings SVG)
            current_year=current_year,
            data_json=data_json # Pasar JSON sin SVGs largos para el botón de descarga
        )

    # --- Petición GET ---
    # <<< CARGAR DATOS DESDE SESIÓN (si existen) >>>
    form_data = session.get('form_data', {}) # Obtiene datos o un dict vacío
    # Renderizar el formulario, pasando los datos de sesión para pre-rellenarlo
    return render_template('index.html', current_year=current_year, form_data=form_data)


# --- Endpoint para Generación IA (Sin cambios funcionales) ---
@app.route('/generate-ai-content', methods=['POST'])
def generate_ai_content():
    if not model: return jsonify({"error": "Modelo IA no configurado."}), 503
    data = request.get_json(); headline = data.get('headline'); description = data.get('description'); field_type = data.get('field_type')
    if not (data and headline and description and field_type): return jsonify({"error": "Faltan datos."}), 400
    prompt = f"""Eres asistente marketing experto en landing pages. Basado en Título: "{headline}" y Descripción: "{description}", genera contenido para '{field_type}'."""
    if field_type == 'features': prompt += """ Genera 3-4 características clave en formato `icono:Título:Descripción` (Font Awesome v6, uno por línea). Lista:"""
    elif field_type == 'testimonials': prompt += """ Genera 2-3 testimonios CORTOS y creíbles (ficticios) en formato `"Cita." - Nombre Ficticio, Cargo/Empresa Ficticia` (uno por línea). Testimonios:"""
    else: return jsonify({"error": "Tipo no soportado."}), 400
    try: response = model.generate_content(prompt); return jsonify({"generated_content": response.text.strip()})
    except Exception as e: print(f"Error API Gemini: {e}"); return jsonify({"error": f"Error IA: {e}"}), 500

# --- Ruta de Descarga (Sin cambios funcionales) ---
@app.route('/download', methods=['POST'])
def download():
    current_year = datetime.datetime.now().year; memory_file = io.BytesIO()
    try:
        json_string = request.form.get('page_data_json'); page_data = json.loads(json_string) # Datos de configuración
        # Regenerar SVGs
        logo_svg = generate_svg_logo(page_data.get('name',''), page_data.get('logo_style'), page_data.get('logo_shape'), page_data.get('color_primary'), page_data.get('color_secondary'))
        hero_svg = generate_svg_hero_pattern(page_data.get('hero_pattern_style'), page_data.get('color_primary'), page_data.get('color_secondary'), 0.08) if page_data.get('hero_background_type') == 'pattern' else None
        # Preparar datos para renderizar HTML de descarga
        d_data = page_data.copy(); d_data['logo_src'] = 'images/logo.svg' if logo_svg else ''; d_data['hero_pattern_src'] = 'images/hero_pattern.svg' if hero_svg else None
        if page_data.get('hero_background_type') == 'gradient': d_data['hero_background_css'] = f"linear-gradient(135deg, {page_data.get('color_primary')}, {page_data.get('color_secondary') if page_data.get('color_secondary', '#ffffff') != '#ffffff' else f'color-mix(in srgb, {page_data.get("color_primary")} 70%, black)'})"
        elif page_data.get('hero_background_type') == 'color': d_data['hero_background_css'] = page_data.get('color_primary')
        else: d_data['hero_background_css'] = None
        d_data['portfolio_raw'] = page_data.get('portfolio_raw', '') # Asegurarse de incluir portfolio
        # Renderizar HTML
        html_content = render_template('preview.html', data=d_data, current_year=current_year, is_download=True)
        # Leer CSS
        css_content = ''; css_path = 'static/css/style.css'
        try:
             with open(css_path, 'r', encoding='utf-8') as f: css_content = f.read()
        except Exception as e: print(f"Warn: Cannot read {css_path}: {e}")
        # Crear ZIP
        with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr('index.html', html_content); zf.writestr('css/style.css', css_content)
            if logo_svg: zf.writestr('images/logo.svg', logo_svg)
            if hero_svg: zf.writestr('images/hero_pattern.svg', hero_svg)
        memory_file.seek(0)
        # Enviar ZIP
        safe_name = ''.join(c if c.isalnum() else '_' for c in page_data.get('name','landing'))
        return send_file(memory_file, mimetype='application/zip', as_attachment=True, download_name=f"{safe_name}_page.zip")
    except Exception as e: print(f"Error descarga: {e}"); import traceback; traceback.print_exc(); return f"Error interno descarga: {e}", 500

# --- Necesario para ejecutar localmente (Flask dev server) ---
# if __name__ == '__main__':
#    app.run(debug=True) # debug=True SOLO para desarrollo
