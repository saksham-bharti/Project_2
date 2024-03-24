from flask import Flask, render_template, request, send_file
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
import io
import base64
import traceback
from fractions import Fraction

app = Flask(__name__)

# Global variable to store uploaded image data and history of modifications
uploaded_image_data = None
history = []
current_state_index = -1  # Initialize current state index for undo/redo

@app.route('/')
def index():
    return render_template('index.html', uploaded_image=uploaded_image_data)

@app.route('/upload', methods=['POST'])
def upload():
    global uploaded_image_data, history, current_state_index
    
    if 'file' not in request.files:
        return 'No file part'

    file = request.files['file']
    if file.filename == '':
        return 'No selected file'

    try:
        img = Image.open(file)
    except Exception as e:
        return f"Error occurred while opening the image: {e}"

    # Apply filters to the image
    try:
        img = apply_filters(img, request.form)
    except Exception as e:
        traceback.print_exc()  # Print traceback of the exception
        return f"Error occurred while processing image: {e}"

    # Check if the processed image is empty
    if img.size == (0, 0):
        return 'Processed image is empty'

    # Convert the processed image to base64 for display
    processed_img_data = img_to_base64(img)

    # Store uploaded image data to be passed to template
    uploaded_image_data = img_to_base64(Image.open(file))

    # Append the current state to history
    if current_state_index < len(history) - 1:
        # If redo has been performed, truncate the history after the current index
        history = history[:current_state_index + 1]
    history.append(processed_img_data)
    current_state_index += 1

    # Render the template with both uploaded and processed image data
    return render_template('index.html', uploaded_image=uploaded_image_data, processed_image=processed_img_data)

@app.route('/undo')
def undo():
    global current_state_index
    if current_state_index > 0:
        current_state_index -= 1
    return render_template('index.html', uploaded_image=uploaded_image_data, processed_image=history[current_state_index])

@app.route('/redo')
def redo():
    global current_state_index
    if current_state_index < len(history) - 1:
        current_state_index += 1
    return render_template('index.html', uploaded_image=uploaded_image_data, processed_image=history[current_state_index])

@app.route('/download')
def download():
    global history, current_state_index
    if current_state_index >= 0 and current_state_index < len(history):
        processed_img_data = history[current_state_index]
        return send_file(io.BytesIO(base64.b64decode(processed_img_data.split(',')[1])), mimetype='image/jpeg', as_attachment=True)
    else:
        return 'No processed image available for download'

def apply_filters(img, form_data):
    try:
        # Apply rotation filter
        if 'rotate' in form_data and form_data['rotate']:
            angle = int(form_data['rotate'])
            img = img.rotate(angle, expand=True)

        # Apply blur filter
        if 'blur' in form_data and form_data['blur']:
            radius = int(form_data['blur'])
            img = img.filter(ImageFilter.GaussianBlur(radius))

        # Apply crop filter
        crop_ratio = form_data.get('aspect-ratio')
        if crop_ratio == 'custom':
            x = int(form_data.get('custom-x', 0))
            y = int(form_data.get('custom-y', 0))
            img = crop_image(img, x, y)
        else:
            x, y = map(int, crop_ratio.split(':'))
            img = crop_image(img, x, y)

        # Apply color tone filter
        color_tone = form_data.get('color-tone', 'normal')
        if color_tone == 'black-and-white':
            img = img.convert('L')  # Convert to grayscale
        elif color_tone != 'normal':
            try:
                cmap_path = f"cmap/{color_tone}.png"
                with Image.open(cmap_path) as cmap_image:
                    # Resize cmap_image to match img dimensions
                    if img.size != cmap_image.size:
                        cmap_image = cmap_image.resize(img.size, Image.ANTIALIAS)
                    img = Image.blend(img, cmap_image, alpha=0.5)
            except FileNotFoundError:
                pass  # Ignore if the lookup table image is not found
        
        # Add text to the image
        if 'text' in form_data and form_data['text']:
            text = form_data['text']
            x = int(form_data.get('text-x', 0))
            y = int(form_data.get('text-y', 0))
            color = form_data.get('text-color', 'black')
            font_size = int(form_data.get('font-size', 20))
            font_type = form_data.get('font-type', 'arial.ttf')

            # Initialize font object with default style
            font = ImageFont.truetype(font_type, font_size)

            draw = ImageDraw.Draw(img)
            draw.text((x, y), text, fill=color, font=font)

        # Apply adjustments
        img = adjust_image(img, form_data)

    except ValueError as e:
        return f"Error occurred while processing image: {e}"

    return img

def crop_image(img, x_ratio, y_ratio):
    width, height = img.size
    desired_ratio = Fraction(x_ratio, y_ratio)
    current_ratio = Fraction(width, height)

    if current_ratio > desired_ratio:
        # Current image is wider than desired ratio, crop the sides
        new_width = int(height * desired_ratio)
        left = (width - new_width) // 2
        right = width - (width - new_width) // 2
        img = img.crop((left, 0, right, height))
    elif current_ratio < desired_ratio:
        # Current image is taller than desired ratio, crop the top and bottom
        new_height = int(width / desired_ratio)
        top = (height - new_height) // 2
        bottom = height - (height - new_height) // 2
        img = img.crop((0, top, width, bottom))
    
    return img

def adjust_image(img, form_data):

    # Adjust brightness
    brightness = int(form_data.get('brightness', 0))
    img = ImageEnhance.Brightness(img).enhance(1 + brightness / 100)

    return img

def img_to_base64(img):
    # Convert image to RGB mode if it's RGBA
    if img.mode == 'RGBA':
        img = img.convert('RGB')
    img_io = io.BytesIO()
    img.save(img_io, format='JPEG')
    img_io.seek(0)
    img_data = base64.b64encode(img_io.getvalue()).decode()
    return f"data:image/jpeg;base64,{img_data}"

if __name__ == '__main__':
    app.run(debug=True)
