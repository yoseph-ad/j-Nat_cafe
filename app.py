import os
import json
import uuid
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, jsonify, session, flash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'jnet_cafe_secret_key_123'

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

PASSWORD_FILE = os.path.join(os.path.dirname(__file__), 'password.txt')
DEFAULT_PASSWORD = 'jnet123'

def get_admin_password():
    if 'KV_URL' in os.environ:
        try:
            import redis
            r = redis.from_url(os.environ['KV_URL'])
            pw = r.get("jnet_password")
            if pw:
                return pw.decode('utf-8').strip()
        except Exception as e:
            print(f"Error loading password from KV: {e}")

    if not os.path.exists(PASSWORD_FILE):
        try:
            with open(PASSWORD_FILE, 'w', encoding='utf-8') as f:
                f.write(DEFAULT_PASSWORD)
        except Exception as e:
            print(f"Error initializing password file: {e}")
        return DEFAULT_PASSWORD
    try:
        with open(PASSWORD_FILE, 'r', encoding='utf-8') as f:
            return f.read().strip()
    except Exception as e:
        print(f"Error reading password file: {e}")
        return DEFAULT_PASSWORD

def set_admin_password(new_password):
    kv_saved = False
    if 'KV_URL' in os.environ:
        try:
            import redis
            r = redis.from_url(os.environ['KV_URL'])
            r.set("jnet_password", new_password.strip())
            kv_saved = True
        except Exception as e:
            print(f"Error saving password to KV: {e}")

    try:
        with open(PASSWORD_FILE, 'w', encoding='utf-8') as f:
            f.write(new_password.strip())
        return True
    except Exception as e:
        print(f"Error saving password file: {e}")
        return kv_saved

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_uploaded_file(file):
    if file and file.filename != '' and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        
        # Check if we should use Vercel Blob
        if 'BLOB_READ_WRITE_TOKEN' in os.environ:
            try:
                import vercel.blob
                file_data = file.read()
                result = vercel.blob.put(filename, file_data, access='public', add_random_suffix=True)
                return result.url
            except Exception as e:
                print(f"Error uploading to Vercel Blob: {e}")
                # Reset file cursor for local fallback
                file.seek(0)

        ext = filename.rsplit('.', 1)[1].lower()
        unique_filename = f"{uuid.uuid4().hex}.{ext}"
        filepath = os.path.join(UPLOAD_FOLDER, unique_filename)
        file.save(filepath)
        return f"/static/uploads/{unique_filename}"
    return None

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

DB_FILE = os.path.join(os.path.dirname(__file__), 'menu.json')

def load_menu():
    if 'KV_URL' in os.environ:
        try:
            import redis
            r = redis.from_url(os.environ['KV_URL'])
            data = r.get("jnet_menu")
            if data:
                return json.loads(data.decode('utf-8'))
        except Exception as e:
            print(f"Error loading menu from KV: {e}")

    if not os.path.exists(DB_FILE):
        return []
    try:
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading menu: {e}")
        return []

def save_menu(menu_data):
    kv_saved = False
    if 'KV_URL' in os.environ:
        try:
            import redis
            r = redis.from_url(os.environ['KV_URL'])
            r.set("jnet_menu", json.dumps(menu_data, ensure_ascii=False))
            kv_saved = True
        except Exception as e:
            print(f"Error saving menu to KV: {e}")

    try:
        with open(DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(menu_data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error saving menu: {e}")
        return kv_saved

GALLERY_FILE = os.path.join(os.path.dirname(__file__), 'gallery.json')

def load_gallery():
    if 'KV_URL' in os.environ:
        try:
            import redis
            r = redis.from_url(os.environ['KV_URL'])
            data = r.get("jnet_gallery")
            if data:
                return json.loads(data.decode('utf-8'))
        except Exception as e:
            print(f"Error loading gallery from KV: {e}")

    if not os.path.exists(GALLERY_FILE):
        try:
            with open(GALLERY_FILE, 'w', encoding='utf-8') as f:
                json.dump([], f)
        except Exception as e:
            print(f"Error initializing gallery file: {e}")
        return []
    try:
        with open(GALLERY_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading gallery: {e}")
        return []

def save_gallery(gallery_data):
    kv_saved = False
    if 'KV_URL' in os.environ:
        try:
            import redis
            r = redis.from_url(os.environ['KV_URL'])
            r.set("jnet_gallery", json.dumps(gallery_data, ensure_ascii=False))
            kv_saved = True
        except Exception as e:
            print(f"Error saving gallery to KV: {e}")

    try:
        with open(GALLERY_FILE, 'w', encoding='utf-8') as f:
            json.dump(gallery_data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error saving gallery: {e}")
        return kv_saved

@app.route('/')
def index():
    menu = load_menu()
    # Categorize items
    food_items = [item for item in menu if item.get('category') == 'Food']
    drink_items = [item for item in menu if item.get('category') == 'Drinks']
    gallery_images = load_gallery()
    return render_template('index.html', food_items=food_items, drink_items=drink_items, gallery_images=gallery_images)

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    error = None
    if request.method == 'POST':
        password = request.form.get('password')
        if password == get_admin_password():
            session['logged_in'] = True
            return redirect(url_for('admin'))
        else:
            error = "Incorrect password. Please try again."
    return render_template('login.html', error=error)

@app.route('/admin/logout')
def admin_logout():
    session.pop('logged_in', None)
    return redirect(url_for('index'))

@app.route('/admin')
@login_required
def admin():
    menu = load_menu()
    gallery_images = load_gallery()
    return render_template('admin.html', menu=menu, gallery_images=gallery_images)

@app.route('/admin/add', methods=['POST'])
@login_required
def add_item():
    name = request.form.get('name')
    category = request.form.get('category')
    price_str = request.form.get('price')
    description = request.form.get('description', '')
    image_url = request.form.get('image_url', '')

    # Check for file upload
    if 'image_file' in request.files:
        file = request.files['image_file']
        uploaded_path = save_uploaded_file(file)
        if uploaded_path:
            image_url = uploaded_path

    if not name or not category or not price_str:
        return "Missing required fields", 400

    try:
        price = float(price_str)
    except ValueError:
        return "Invalid price format", 400

    menu = load_menu()
    
    # Generate next sequential ID
    if menu:
        # Filter for numeric IDs and find the max
        numeric_ids = [int(item['id']) for item in menu if item['id'].isdigit()]
        new_id = str(max(numeric_ids) + 1) if numeric_ids else "1"
    else:
        new_id = "1"

    new_item = {
        "id": new_id,
        "name": name,
        "category": category,
        "price": price,
        "description": description,
        "image_url": image_url or "/static/images/macchiato.png"
    }

    menu.append(new_item)
    save_menu(menu)
    return redirect(url_for('admin'))

@app.route('/admin/edit/<item_id>', methods=['POST'])
@login_required
def edit_item(item_id):
    name = request.form.get('name')
    category = request.form.get('category')
    price_str = request.form.get('price')
    description = request.form.get('description', '')
    image_url = request.form.get('image_url', '')

    # Check for file upload
    if 'image_file' in request.files:
        file = request.files['image_file']
        uploaded_path = save_uploaded_file(file)
        if uploaded_path:
            image_url = uploaded_path

    if not name or not category or not price_str:
        return "Missing required fields", 400

    try:
        price = float(price_str)
    except ValueError:
        return "Invalid price format", 400

    menu = load_menu()
    found = False
    for item in menu:
        if item['id'] == item_id:
            item['name'] = name
            item['category'] = category
            item['price'] = price
            item['description'] = description
            item['image_url'] = image_url or item.get('image_url', '/static/images/macchiato.png')
            found = True
            break

    if not found:
        return "Item not found", 404

    save_menu(menu)
    return redirect(url_for('admin'))

@app.route('/admin/delete/<item_id>', methods=['POST'])
@login_required
def delete_item(item_id):
    menu = load_menu()
    
    # Find the item to get the filepath
    filepath_to_delete = None
    vercel_blob_to_delete = None
    for item in menu:
        if item['id'] == item_id:
            image_url = item.get('image_url', '')
            if image_url.startswith('/static/uploads/'):
                filepath_to_delete = os.path.join(os.path.dirname(__file__), image_url.lstrip('/'))
            elif image_url.startswith('https://') and 'public.blob.vercel-storage.com' in image_url:
                vercel_blob_to_delete = image_url
            break
            
    updated_menu = [item for item in menu if item['id'] != item_id]
    
    if len(updated_menu) == len(menu):
        return "Item not found", 404
        
    save_menu(updated_menu)
    
    if filepath_to_delete and os.path.exists(filepath_to_delete):
        try:
            os.remove(filepath_to_delete)
        except Exception as e:
            print(f"Error deleting file {filepath_to_delete}: {e}")

    if vercel_blob_to_delete and 'BLOB_READ_WRITE_TOKEN' in os.environ:
        try:
            import vercel.blob
            vercel.blob.delete(vercel_blob_to_delete)
        except Exception as e:
            print(f"Error deleting Vercel Blob {vercel_blob_to_delete}: {e}")
            
    return redirect(url_for('admin'))

@app.route('/admin/change-password', methods=['POST'])
@login_required
def change_password():
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')

    if not current_password or not new_password or not confirm_password:
        flash("All password fields are required.", "danger")
        return redirect(url_for('admin'))

    if current_password != get_admin_password():
        flash("Incorrect current password.", "danger")
        return redirect(url_for('admin'))

    if new_password != confirm_password:
        flash("New password and confirmation do not match.", "danger")
        return redirect(url_for('admin'))

    if len(new_password) < 4:
        flash("New password must be at least 4 characters long.", "danger")
        return redirect(url_for('admin'))

    if set_admin_password(new_password):
        flash("Password updated successfully!", "success")
    else:
        flash("Failed to update password.", "danger")

    return redirect(url_for('admin'))

@app.route('/admin/gallery/add', methods=['POST'])
@login_required
def add_gallery_item():
    caption = request.form.get('caption', '')
    
    if 'gallery_file' not in request.files:
        flash("No image file provided.", "danger")
        return redirect(url_for('admin'))
        
    file = request.files['gallery_file']
    if file.filename == '':
        flash("Please select an image file to upload.", "danger")
        return redirect(url_for('admin'))

    uploaded_path = save_uploaded_file(file)
    if not uploaded_path:
        flash("Invalid file format or upload failed. Please upload an image (png, jpg, jpeg, gif, webp).", "danger")
        return redirect(url_for('admin'))

    gallery = load_gallery()
    
    # Generate ID
    if gallery:
        numeric_ids = [int(item['id']) for item in gallery if str(item['id']).isdigit()]
        new_id = str(max(numeric_ids) + 1) if numeric_ids else "1"
    else:
        new_id = "1"

    new_item = {
        "id": new_id,
        "image_url": uploaded_path,
        "caption": caption
    }

    gallery.append(new_item)
    save_gallery(gallery)
    flash("Photo successfully uploaded to gallery!", "success")
    return redirect(url_for('admin'))

@app.route('/admin/gallery/delete/<img_id>', methods=['POST'])
@login_required
def delete_gallery_item(img_id):
    gallery = load_gallery()
    
    # Find the item to get the filepath
    filepath_to_delete = None
    vercel_blob_to_delete = None
    for item in gallery:
        if item['id'] == img_id:
            image_url = item.get('image_url', '')
            if image_url.startswith('/static/uploads/'):
                filepath_to_delete = os.path.join(os.path.dirname(__file__), image_url.lstrip('/'))
            elif image_url.startswith('https://') and 'public.blob.vercel-storage.com' in image_url:
                vercel_blob_to_delete = image_url
            break
            
    updated_gallery = [item for item in gallery if item['id'] != img_id]
    
    if len(updated_gallery) == len(gallery):
        flash("Gallery photo not found.", "danger")
        return redirect(url_for('admin'))
        
    save_gallery(updated_gallery)
    
    if filepath_to_delete and os.path.exists(filepath_to_delete):
        try:
            os.remove(filepath_to_delete)
        except Exception as e:
            print(f"Error deleting file {filepath_to_delete}: {e}")

    if vercel_blob_to_delete and 'BLOB_READ_WRITE_TOKEN' in os.environ:
        try:
            import vercel.blob
            vercel.blob.delete(vercel_blob_to_delete)
        except Exception as e:
            print(f"Error deleting Vercel Blob {vercel_blob_to_delete}: {e}")
            
    flash("Gallery photo deleted successfully.", "success")
    return redirect(url_for('admin'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
