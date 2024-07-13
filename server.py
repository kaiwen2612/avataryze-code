import os
import glob
import shutil
import threading
from os import environ as env
from urllib.parse import quote_plus, urlencode
import datetime
from authlib.integrations.flask_client import OAuth
from dotenv import find_dotenv, load_dotenv
from flask import Flask, redirect, render_template, session, url_for, request, jsonify, flash
from werkzeug.utils import secure_filename
import time

import subprocess, platform
from animate_face import animate_face

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import redis

ENV_FILE = find_dotenv()
if ENV_FILE:
    load_dotenv(ENV_FILE)
    
app = Flask(__name__)
app.debug = True
app.secret_key = env.get("APP_SECRET_KEY")
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['AUDIO_FOLDER'] = 'audio'
app.config['IMAGE_FOLDER'] = 'static/uploads/images'
app.config['VIDEO_FOLDER'] = 'static/uploads/videos'
app.config['AVATAR_FOLDER'] = 'static/avatars'
app.config['ALLOWED_VIDEO_EXTENSIONS'] = {'mp4', 'mov', 'avi'}
app.config['ALLOWED_IMAGE_EXTENSIONS'] = {'png', 'jpg', 'jpeg'}

db = redis.Redis(host='localhost', port=6379, db=0)

oauth = OAuth(app)

oauth.register(
    "auth0",
    client_id=env.get("AUTH0_CLIENT_ID"),
    client_secret=env.get("AUTH0_CLIENT_SECRET"),
    client_kwargs={
        "scope": "openid profile email",
    },
    server_metadata_url=f'https://{env.get("AUTH0_DOMAIN")}/.well-known/openid-configuration'
)

# -----------------------------------------------------------------------------
# home page
# 
# list videos
@app.route('/videolist')
def videolist():
    username = session.get('user').get('userinfo').get('nickname')
    isadmin = session.get('user').get('userinfo').get('admin')
    videos = get_user_videos('{}'.format(username))
    return render_template('video-list.html', videos=videos, isadmin=isadmin)

# home page
@app.route("/")
def home():
    user = session.get("user")
    if (user == None):
        return render_template("index.html")        
    return redirect("/videolist")

def get_user_videos(prefix):
    static_folder = os.path.join(os.getcwd(), 'static/output')
    files = os.listdir(static_folder)
    matching_files = [file for file in files if file.startswith(prefix) 
                      and file.endswith("final.mp4")]
    return matching_files

# -----------------------------------------------------------------------------
# login
# 
@app.route("/login")
def login():
    print(url_for("callback", _external=True))
    return oauth.auth0.authorize_redirect(
        redirect_uri="https://www.avataryze.me/callback"
    )

def generate_unique_filename(username):
    id = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    return f"{username}_{id}"

def allowed_file(filename, filetype):
    if filetype == 'video':
        return '.' in filename and filename.rsplit('.', 1)[1].lower() \
            in app.config['ALLOWED_VIDEO_EXTENSIONS']
    elif filetype == 'image':
        return '.' in filename and filename.rsplit('.', 1)[1].lower() \
            in app.config['ALLOWED_IMAGE_EXTENSIONS']
    else:
        return False


# callback auth
@app.route("/callback", methods=["GET", "POST"])
def callback():
    token = oauth.auth0.authorize_access_token()
    session["user"] = token
    return redirect("/")

#  logout
@app.route("/logout")
def logout():
    session.clear()
    return redirect(
        "https://" + env.get("AUTH0_DOMAIN")
        + "/v2/logout?"
        + urlencode(
            {
                "returnTo": "https://www.avataryze.me",
                "client_id": env.get("AUTH0_CLIENT_ID"),
            },
            quote_via=quote_plus,
        )
    )
# -----------------------------------------------------------------------------
# upload image
@app.route('/uploadavatar', methods=['GET', 'POST'])
def uploadavatar():
    user = session.get('user')
    username = user.get('userinfo').get('nickname')
    email = user.get('userinfo').get('email')  

    if request.method == 'GET':
        return render_template('upload-avatar.html')
    
    if request.method == 'POST':        
        if 'custom-avatar' not in request.files:
            return "No file part"
        
        id = generate_unique_filename(username)

        imgFile = request.files['custom-avatar']
        if imgFile and allowed_file(imgFile.filename,'image'):
            imgFilename = secure_filename(imgFile.filename)
            uploaded_imgfilename = os.path.join(app.config['IMAGE_FOLDER'], 
                                                id + "_" + imgFilename)
            imgFile.save(uploaded_imgfilename)
            db.set(uploaded_imgfilename, email)            
            admin_email = env.get("ADMIN_EMAIL")
            admin_subject = f'Avatar image submitted for your approval'
            admin_body = f'Hi,\n\nAn avatar image has been submitted. Please log in to approve.\n\nBest regards,\nYour Avataryze Team'
            send_email(admin_email, admin_subject, admin_body)        

            return render_template('image-submitted.html')


# -----------------------------------------------------------------------------
# approve images
# 
@app.route('/approveimages', methods=['GET', 'POST'])
def approveimages():
    user = session.get('user')    
    isadmin = user.get('userinfo').get('admin')    
    if isadmin:
        if request.method == 'GET':
            images = get_images_with_prefix(app.config['IMAGE_FOLDER'], "")
            return render_template('approve-images.html', images=images)

        if request.method == 'POST': 
            uploaded_images = request.form.getlist("uploaded_images")
            move_files(uploaded_images, app.config['AVATAR_FOLDER'])
            subject = "Your avatar image has been approved"
            body = "Hi,\n\nThe Avataryze administrator has approved your image. You can now use it to create videos! \n\nBest regards,\nYour Avataryze Team"
            for image in uploaded_images:
                email = db.get(image)
                send_email(email.decode('utf-8'), subject, body)
                db.delete(image)
            return redirect("/approveimages")
    else:
        return redirect("/logout")


# -----------------------------------------------------------------------------
# create video
# 
@app.route('/createvideo', methods=['GET', 'POST'])
def createvideo():
    user = session.get('user')
    username = user.get('userinfo').get('nickname')
    email = user.get('userinfo').get('email')    
    id = generate_unique_filename(username)
    if request.method == 'GET':
            images = get_images_with_prefix(app.config['AVATAR_FOLDER'], username + "_")
            print("createvideo:images:", images)
            return render_template('create-video.html', images=images)
 
    if request.method == 'POST': 
        # Check if the POST request has a file part
        if 'presenterVid' not in request.files:
            return "No file part"

        vidFile = request.files['presenterVid']

        # If the user does not select a file, the browser may send an empty file
        if vidFile.filename == '' or request.form.get('avatar') == None:
            return redirect("/")
        
        # Save the uploaded file to a specific folder (in this case, 'uploads')
        if vidFile and allowed_file(vidFile.filename,'video'):
            vidFilename = secure_filename(vidFile.filename)
            uploaded_vidfile = os.path.join(app.config['VIDEO_FOLDER'], vidFilename)
            vidFile.save(uploaded_vidfile)
            # Extract speech from MP4
            audio_file = os.path.join(app.config['AUDIO_FOLDER'],'{}.wav'.format(id))
            command = '/usr/bin/ffmpeg -i {} -acodec pcm_s16le -ar 44100 \
                -ac 1 {}'.format(uploaded_vidfile, audio_file)
            subprocess.call(command, shell=platform.system() != 'Windows')
            chosen_avatar = request.form.get('avatar')
            request_data = {
                'id': id,
                'uploaded_file': uploaded_vidfile,
                'audio_file': audio_file,
                'chosen_avatar': chosen_avatar
            }
            thread = threading.Thread(target=process_video, args=(request_data,email,username))
            thread.start()	   

        return render_template('video-request-submitted.html',)

def process_video(request_data, email, username):
    t0 = time.time()
    id = request_data['id']
    uploaded_file = request_data['uploaded_file']
    audio_file = request_data['audio_file']
    chosen_avatar = request_data['chosen_avatar']
    print("avatar:", chosen_avatar)
    print("driver:", uploaded_file)
    # Animate avatar
    if chosen_avatar:
        animate_face(id, uploaded_file, chosen_avatar)

    # Combine animated avatar with speech
    animated_file = os.path.join('static', 'output', '{}.mp4'.format(id))
    output_file = os.path.join('static', 'output', '{}_final.mp4'.format(id))
    command = '/usr/bin/ffmpeg -i {} -i {} -c:v copy -map 0:v:0 -map 1:a:0 \
        -shortest {}'.format(animated_file, audio_file, output_file)
    subprocess.call(command, shell=platform.system() != 'Windows')
    
    dur = time.time() - t0
    print(">> duration:", dur)
    delete_video_file(username, animated_file)
    # Send notification email
    subject = "Your Avataryze video is ready!"
    body = f'Hi,\n\nYour Avataryze video is ready! You can proceed to view it in the Video List page.\n\nBest regards,\nYour Avataryze Team'
    send_email(email, subject, body)

# -----------------------------------------------------------------------------
# Delete video
# 

@app.route('/deletevideo/<video_filename>', methods=['GET'])
def deletevideo(video_filename):
    user = session.get('user')
    username = user.get('userinfo').get('nickname')
    delete_video_file(username, video_filename)
    return redirect("/videolist")


# -----------------------------------------------------------------------------
# Delete image
# 

@app.route('/deleteimage/<image_filename>', methods=['GET'])
def deleteimage(image_filename):
    user = session.get('user')    
    isadmin = user.get('userinfo').get('admin')       
    if isadmin:
        delete_image_file(image_filename)
        subject = "Your avatar image has been rejected"
        body = "Hi,\n\nThe Avataryze administrator has rejected your image. You can submit other avatar images. \n\nBest regards,\nYour Avataryze Team"
        full_path = os.path.join('static', 'uploads', 'images', image_filename)
        email = db.get(full_path)
        send_email(email.decode('utf-8'), subject, body)
        db.delete(full_path)

        return redirect("/approveimages")
    
    else:
        return redirect("/logout")

# -----------------------------------------------------------------------------
# Utilities
# 

# delete a file
def delete_video_file(username, filepath):
    # Extract the filename from the filepath
    filename = os.path.basename(filepath)

    # Check if the filename starts with the username followed by an underscore
    if filename.startswith(f"{username}_"):
        # Construct the full path to the file in the static/output directory
        full_path = os.path.join('static', 'output', filename)

        # Check if the file exists before attempting to delete it
        if os.path.exists(full_path):
            os.remove(full_path)
            print(f"File {full_path} deleted successfully.")
        else:
            print(f"File {full_path} does not exist.")
    else:
        print(f"Filename {filename} does not match the username prefix {username}_.")


def delete_image_file(filepath):
    full_path = os.path.join('static', 'uploads', 'images', filepath)
    print(full_path)
    if os.path.exists(full_path):
        os.remove(full_path)
        print(f"File {full_path} deleted successfully.")  
    else:
        print(f"File {full_path} does not exist.")

# send email
def send_email(recipient_email, subject, body):
    with app.app_context():
        sender_email = env.get("EMAIL_SENDER")
        password = env.get("EMAIL_PASSWORD")

        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = recipient_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, password)
        server.send_message(msg)
        server.quit()

# move files in a list to another directoory
def move_files(file_paths, destination_dir):
    # Ensure the destination directory exists
    if not os.path.exists(destination_dir):
        os.makedirs(destination_dir)

    for file_path in file_paths:
        if os.path.isfile(file_path):
            # Move the file to the destination directory
            shutil.move(file_path, destination_dir)
        else:
            print(f"File not found: {file_path}")

# get images with a particular prefix
def get_images_with_prefix(directory, prefix):
    # Define the pattern for image files with the given prefix
    pattern = os.path.join(directory, f"{prefix}*")
    # Get all files matching the pattern
    files = glob.glob(pattern)

    # Filter out non-image files (assuming common image extensions)
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff'}
    images = [file for file in files if os.path.splitext(file)[1].lower() 
              in image_extensions]

    return images

# -----------------------------------------------------------------------------
if __name__ == "__main__":
     app.run(host="0.0.0.0", port=env.get("PORT", 3000))