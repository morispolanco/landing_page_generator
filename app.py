# app.py
from flask import Flask, render_template, request, send_file
import datetime
import base64
import io
import zipfile
import json
from markupsafe import escape # Para escapar texto en SVG

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# --- Funciones de Generación SVG ---

def generate_svg_logo(name, style='text', shape='none', color_primary='#007bff', color_secondary='#ffffff', font_family='Poppins, sans-serif'):
    """Genera un logo SVG simple."""
    name = escape(name) # Escapar el nombre
    text_content = name
    font_size = 35 # Ajustar tamaño de fuente base

    if style == 'initials':
        words = name.split()
        if len(words) >= 2:
            text_content = (words[0][0] + words[-1][0]).upper()
        elif len(words) == 1 and len(words[0]) > 0:
            text_content = words[0][0].upper()
        else:
            text_content = 'L' # Fallback
        font_size = 45 # Más grande para iniciales

    svg_width = 100
    svg_height = 100
    shape_element = ''
    text_x = svg_width / 2
    text_y = svg_height / 2

    # Asegurar contraste básico para el texto
    # (Esto es muy simple, se podría usar cálculo de luminancia)
    text_color = color_secondary
    try:
        # Intenta determinar si el color primario es claro u oscuro (heurística simple)
        r, g, b = int(color_primary[1:3], 16), int(color_primary[3:5], 16), int(color_primary[5:7], 16)
        luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
        if luminance > 0.5: # Si el fondo es claro
             text_color = color_secondary if color_secondary != '#ffffff' else '#333333' # Usa secundario si no es blanco, si no, gris oscuro
        else: # Si el fondo es oscuro
             text_color = color_secondary if color_secondary != '#000000' else '#ffffff' # Usa secundario si no es negro, si no, blanco
    except:
        text_color = color_secondary # Fallback

    if shape == 'circle':
        shape_element = f'<circle cx="50" cy="50" r="50" fill="{color_primary}"/>'
    elif shape == 'square':
        shape_element = f'<rect width="100" height="100" rx="10" ry="10" fill="{color_primary}"/>' # rx/ry para bordes redondeados
        text_color = color_secondary # Asumir texto claro en cuadrado
    else: # 'none' - Ajustar tamaño y color de texto
        svg_width = len(text_content) * (font_size * 0.6) # Ancho aprox basado en texto
        svg_height = font_size * 1.2
        text_x = svg_width / 2
        text_y = svg_height * 0.7 # Ajuste vertical para texto sin fondo
        text_color = color_primary # Usar color primario para texto sin fondo


    svg_content = f'''<svg width="{int(svg_width)}" height="{int(svg_height)}" viewBox="0 0 {int(svg_width)} {int(svg_height)}"
     xmlns="http://www.w3.org/2000/svg">
    {shape_element}
    <text x="{text_x}" y="{text_y}" font-family="{font_family}" font-size="{font_size}" fill="{text_color}"
          text-anchor="middle" dominant-baseline="middle" font-weight="600">
        {text_content}
    </text>
</svg>'''
    return svg_content.replace('\n', '').replace('    ', '') # Limpiar un poco

def generate_svg_hero_pattern(style='waves', color_primary='#007bff', color_secondary='#6c757d', opacity=0.1):
    """Genera un patrón SVG simple para fondo."""
    pattern_content = ''
    pattern_id = f"pattern-{style}"
    pattern_size = 50 # Tamaño base del tile del patrón

    if style == 'waves':
        pattern_size = 100
        pattern_content = f'''
        <path d="M 0 50 Q 25 {100 - 25*opacity*100} 50 50 T 100 50" stroke="{color_secondary}" stroke-width="3" fill="none" opacity="{opacity}"/>
        <path d="M 0 60 Q 25 {110 - 25*opacity*100} 50 60 T 100 60" stroke="{color_secondary}" stroke-width="2" fill="none" opacity="{opacity*0.8}"/>
        '''
    elif style == 'dots':
         pattern_size = 20
         pattern_content = f'<circle cx="10" cy="10" r="2" fill="{color_secondary}" opacity="{opacity}"/>'
    elif style == 'lines':
         pattern_size = 15
         pattern_content = f'<path d="M 0 0 L 15 15 M 15 0 L 0 15" stroke="{color_secondary}" stroke-width="1" opacity="{opacity}"/>'
    elif style == 'triangles':
         pattern_size = 40
         pattern_content = f'''
         <path d="M 0 0 L 20 40 L 40 0 Z" fill="{color_secondary}" opacity="{opacity*0.5}"/>
         <path d="M 20 0 L 0 40 L 40 40 Z" fill="{color_secondary}" opacity="{opacity*0.7}"/>
         '''
    else: # Fallback simple
        pattern_size = 20
        pattern_content = f'<rect width="10" height="10" fill="{color_secondary}" opacity="{opacity}"/>'


    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="100%">
    <defs>
        <pattern id="{pattern_id}" patternUnits="userSpaceOnUse" width="{pattern_size}" height="{pattern_size}">
            {pattern_content}
        </pattern>
    </defs>
    <rect width="100%" height="100%" fill="url(#{pattern_id})" />
</svg>'''
    return svg.replace('\n', '').replace('    ', '')

def svg_to_data_url(svg_string):
    """Convierte una cadena SVG a Data URL base64."""
    if not svg_string:
        return ""
    encoded = base64.b64encode(svg_string.encode('utf-8')).decode('utf-8')
    return f"data:image/svg+xml;base64,{encoded}"

# --- Rutas Flask ---

@app.route('/', methods=['GET', 'POST'])
def index():
    current_year = datetime.datetime.now().year

    if request.method == 'POST':
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
            'color_secondary': request.form.get('color_secondary', '#ffffff'), # Default blanco para texto logo
            'features_raw': request.form.get('features', ''),
            'testimonials_raw': request.form.get('testimonials', ''),

            # Nuevos campos para generación SVG
            'logo_style': request.form.get('logo_style', 'text'),
            'logo_shape': request.form.get('logo_shape', 'none'),
            'hero_background_type': request.form.get('hero_background_type', 'color'),
            'hero_pattern_style': request.form.get('hero_pattern_style', 'waves'),
            'image_hero_url': request.form.get('image_hero_url', '') # URL sigue siendo opción
        }

        # Generar SVG Logo
        logo_svg_string = generate_svg_logo(
            page_data['name'],
            page_data['logo_style'],
            page_data['logo_shape'],
            page_data['color_primary'],
            page_data['color_secondary']
        )
        page_data['logo_svg_string'] = logo_svg_string # Guardar SVG crudo
        page_data['logo_src'] = svg_to_data_url(logo_svg_string) # Guardar Data URL para preview

        # Generar/Determinar Fondo Hero
        page_data['hero_background_svg_pattern_string'] = None # SVG crudo del patrón
        page_data['hero_pattern_src'] = None # Data URL del patrón
        page_data['hero_background_css'] = None # Estilo CSS para color/gradiente

        hero_bg_type = page_data['hero_background_type']
        if hero_bg_type == 'pattern':
            hero_pattern_svg_string = generate_svg_hero_pattern(
                page_data['hero_pattern_style'],
                page_data['color_primary'],
                page_data['color_secondary'],
                opacity=0.08 # Opacidad baja para patrón de fondo
            )
            page_data['hero_background_svg_pattern_string'] = hero_pattern_svg_string
            page_data['hero_pattern_src'] = svg_to_data_url(hero_pattern_svg_string)
        elif hero_bg_type == 'gradient':
             # Gradiente simple (primario a secundario o variación de primario)
             color2 = page_data['color_secondary'] if page_data['color_secondary'] != '#ffffff' else f"color-mix(in srgb, {page_data['color_primary']} 70%, black)"
             page_data['hero_background_css'] = f"linear-gradient(135deg, {page_data['color_primary']}, {color2})"
        elif hero_bg_type == 'image_url':
             # Se usará page_data['image_hero_url'] directamente en la plantilla
             pass
        else: # 'color' (por defecto)
            page_data['hero_background_css'] = page_data['color_primary']


        # Preparar datos como JSON para el botón de descarga
        try:
             # Excluimos los SVG largos del JSON, los regeneraremos en la descarga
            data_to_serialize = {k: v for k, v in page_data.items() if not k.endswith('_svg_string') and not k.endswith('_src')}
            data_json = json.dumps(data_to_serialize)
        except Exception as e:
             print(f"Error serializando page_data a JSON: {e}")
             data_json = "{}"

        return render_template(
            'preview.html',
            data=page_data, # Pasamos todo (incluyendo src y strings SVG)
            current_year=current_year,
            data_json=data_json # Pasamos JSON sin SVGs largos
        )

    return render_template('index.html', current_year=current_year)


@app.route('/download', methods=['POST'])
def download():
    current_year = datetime.datetime.now().year
    try:
        json_string = request.form.get('page_data_json')
        if not json_string:
            return "Error: No se recibieron datos para generar la descarga.", 400
        page_data = json.loads(json_string) # Contiene la configuración, no los SVGs/DataUrls

        # --- Regenerar SVGs basados en los datos del JSON ---
        logo_svg_string = generate_svg_logo(
            page_data.get('name',''), page_data.get('logo_style'), page_data.get('logo_shape'),
            page_data.get('color_primary'), page_data.get('color_secondary')
        )
        hero_pattern_svg_string = None
        if page_data.get('hero_background_type') == 'pattern':
            hero_pattern_svg_string = generate_svg_hero_pattern(
                page_data.get('hero_pattern_style'), page_data.get('color_primary'),
                page_data.get('color_secondary'), opacity=0.08
            )
        # --- Fin Regeneración ---

        # Preparar datos COMPLETOS para renderizar el HTML de descarga
        # (incluyendo URLs relativas para los archivos que irán en el ZIP)
        download_page_data = page_data.copy() # Copiar datos base
        download_page_data['logo_src'] = 'images/logo.svg' if logo_svg_string else ''
        download_page_data['image_hero_url'] = page_data.get('image_hero_url', '') # Usar la URL si es el tipo elegido
        download_page_data['hero_pattern_src'] = 'images/hero_pattern.svg' if hero_pattern_svg_string else None
        # Determinar el estilo de fondo para el HTML descargado
        if page_data.get('hero_background_type') == 'gradient':
             color2 = page_data['color_secondary'] if page_data.get('color_secondary', '#ffffff') != '#ffffff' else f"color-mix(in srgb, {page_data.get('color_primary')} 70%, black)"
             download_page_data['hero_background_css'] = f"linear-gradient(135deg, {page_data.get('color_primary')}, {color2})"
        elif page_data.get('hero_background_type') == 'color':
            download_page_data['hero_background_css'] = page_data.get('color_primary')
        else: # pattern or image_url (serán manejados por src)
             download_page_data['hero_background_css'] = None


        # 1. Renderizar el HTML (usando la plantilla preview pero con datos de descarga)
        html_content = render_template(
            'preview.html',
            data=download_page_data, # Usar datos con rutas relativas
            current_year=current_year,
            is_download=True # Flag para que use rutas relativas en CSS/JS
        )

        # 2. Leer el contenido del CSS
        css_path = 'static/css/style.css'
        try:
            with open(css_path, 'r', encoding='utf-8') as f:
                css_content = f.read()
        except Exception as e:
             return f"Error leyendo el archivo CSS: {e}", 500

        # 3. Crear archivo ZIP en memoria
        memory_file = io.BytesIO()
        with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr('index.html', html_content)
            zf.writestr('css/style.css', css_content)
            # Añadir SVGs si se generaron
            if logo_svg_string:
                zf.writestr('images/logo.svg', logo_svg_string)
            if hero_pattern_svg_string:
                 zf.writestr('images/hero_pattern.svg', hero_pattern_svg_string)

        memory_file.seek(0)

        # 4. Enviar el archivo ZIP al usuario
        return send_file(
            memory_file,
            mimetype='application/zip',
            as_attachment=True,
            download_name=f"{page_data.get('name','landing').replace(' ','_').lower()}_page.zip"
        )

    except json.JSONDecodeError:
        return "Error: Los datos recibidos para la descarga no son válidos.", 400
    except Exception as e:
        print(f"Error general en la descarga: {e}")
        import traceback
        traceback.print_exc()
        return f"Error interno del servidor al generar el archivo ZIP: {e}", 500
