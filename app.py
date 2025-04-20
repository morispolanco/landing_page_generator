# app.py
from flask import Flask, render_template, request
import datetime

app = Flask(__name__)

@app.route('/', methods=['GET', 'POST'])
def index():
    current_year = datetime.datetime.now().year

    if request.method == 'POST':
        # Recopilar datos del formulario (incluyendo los nuevos)
        page_data = {
            'page_type': request.form.get('page_type', 'personal'),
            'name': request.form.get('name', 'Mi Nombre/Empresa'),
            'headline': request.form.get('headline', 'Una propuesta de valor increíble'),
            'description': request.form.get('description', ''),
            'cta_text': request.form.get('cta_text', 'Saber Más'),
            'contact_email': request.form.get('contact_email'),
            'contact_phone': request.form.get('contact_phone', ''),
            'social_links_raw': request.form.get('social_links', ''),
            'logo_url': request.form.get('logo_url', ''),
            'color_primary': request.form.get('color_primary', '#007bff'),
            'color_secondary': request.form.get('color_secondary', '#6c757d'), # Nuevo: color secundario
            'features_raw': request.form.get('features', ''), # Nuevo: Características
            'testimonials_raw': request.form.get('testimonials', ''), # Nuevo: Testimonios
            'image_hero_url': request.form.get('image_hero_url', '') # Nuevo: Imagen para Hero
        }

        return render_template('preview.html', data=page_data, current_year=current_year)

    return render_template('index.html', current_year=current_year)

# No se necesita __main__ para Vercel
