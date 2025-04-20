# app.py (igual que antes, solo asegúrate de que esté limpio)
from flask import Flask, render_template, request
import datetime # Importa datetime para el año en el footer

app = Flask(__name__)

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        # Recopilar datos del formulario
        page_type = request.form.get('page_type')
        name = request.form.get('name')
        headline = request.form.get('headline')
        description = request.form.get('description')
        cta_text = request.form.get('cta_text')
        contact_email = request.form.get('contact_email')
        contact_phone = request.form.get('contact_phone')
        social_links = request.form.get('social_links')
        logo_url = request.form.get('logo_url')
        color_primary = request.form.get('color_primary', '#007bff')

        page_data = {
            'page_type': page_type,
            'name': name,
            'headline': headline,
            'description': description,
            'cta_text': cta_text,
            'contact_email': contact_email,
            'contact_phone': contact_phone,
            'social_links_raw': social_links,
            'logo_url': logo_url,
            'color_primary': color_primary,
        }

        # Pasar el año actual a la plantilla para el copyright
        current_year = datetime.datetime.now().year

        return render_template('preview.html', data=page_data, current_year=current_year)

    # Si es GET, mostrar el formulario
    return render_template('index.html')

# El bloque if __name__ == '__main__': NO se ejecuta en Vercel
# Es solo para desarrollo local
# if __name__ == '__main__':
#    app.run(debug=True)
